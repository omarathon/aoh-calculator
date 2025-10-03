import argparse
import json
import math
import os
import logging
import sys
from pathlib import Path
import time
from typing import Dict, List, Optional, Set

# import pyshark # pylint: disable=W0611
import numpy as np
import pandas as pd
import yirgacheffe.operators as yo # type: ignore
from yirgacheffe.layers import RasterLayer, VectorLayer, ConstantLayer, UniformAreaLayer # type: ignore
from geopandas import gpd # type: ignore
from alive_progress import alive_bar # type: ignore
from osgeo import gdal # type: ignore
gdal.UseExceptions()

from osgeo import ogr
from typing import Union 

import yirgacheffe # pylint: disable=C0412,C0413

import codec

yirgacheffe.constants.DEBUG_DIMENSIONS = True

ELEVATION_MAX_MIN = -415
ELEVATION_MIN_MIN = -599

# // benefit from morton: 2, 3, 4, 6, 100-103, 7, 8, 10, 11, 12, 200-202
# // 2: fastpfor_simdpfor
# // 4: rle
# // 4: rle + simdcomp
# // 6: rle + fastpfor_bitpack
# // 100-103: bad
# // 7: turbopfor256
# // 8: delta+turbopfor256
# // 10: delta+turbopack256
# // 11: turborle
# // 12: turbopfor
# // 200: delta
# // 201: delta+fastpfor_bitpack
# // 202: delta+simdcomp

# CACHE_EXTRA = False

# CODEC_ID_UNIFORM = 0
# CODEC_ID_BINARY = 6

# CODEC_ID_HABITAT = 0       # 1 seems best - 15s runtime, 1.46B. 6 also good.
# CODEC_ID_ELEVATION = 0     # 1 seems best - 15s runtime, 1.46B. 6 also good.
# CODEC_ID_BINARY = 0           # 0 seems best - 15s runtime, 1.46B. very simimilar to 1 - slightly longer runtime (15s round) but 1.5B usage. 6 is also good - similar.

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

def load_crosswalk_table(table_file_name: Path) -> Dict[str,List[int]]:
    rawdata = pd.read_csv(table_file_name)
    result : Dict[str,List[int]] = {}
    for _, row in rawdata.iterrows():
        code = str(row.code)
        try:
            result[code].append(int(row.value))
        except KeyError:
            result[code] = [int(row.value)]
    return result

def crosswalk_habitats(crosswalk_table: Dict[str, List[int]], raw_habitats: Set[str]) -> Set[int]:
    result = set()
    for habitat in raw_habitats:
        try:
            crosswalked_habatit = crosswalk_table[habitat]
        except KeyError:
            continue
        result |= set(crosswalked_habatit)
    return result

# @profile
def aohcalc(
    habitat_path: Path,
    min_elevation_path: Path,
    max_elevation_path: Path,
    area_path: Optional[Path],
    crosswalk_path: Path,
    species_data_path: Path,
    force_habitat: bool,
    output_directory_path: Path,
    cache_mode: Optional[int],
    ystep: Optional[int],
    xss: Optional[int],
    yss: Optional[int],
    codec_habitat: Optional[int],
    codec_el: Optional[int],
    codec_range: Optional[int],
    gdal_cache_max_mb: Optional[int],
    morton_mode: Optional[int],
    quant: int
) -> None:
    
    cache_mode_parsed = int(cache_mode) if cache_mode else 0
    ystep_parsed = int(ystep) if ystep else 2048
    xss_parsed = int(xss) if xss else 256
    yss_parsed = int(yss) if yss else 256

    codec_habitat_parsed = int(codec_habitat) if codec_habitat else 0
    codec_el_parsed = int(codec_el) if codec_el else 0
    codec_range_parsed = int(codec_range) if codec_range else 0

    morton_mode_parsed = int(morton_mode) if morton_mode else 0

    print(f"cache_mode_parsed={cache_mode_parsed}\nystep_parsed={ystep_parsed}\nxss_parsed={xss_parsed}\nyss_parsed={yss_parsed}")
    print(f"codec_habitat_parsed={codec_habitat_parsed}\ncodec_el_parsed={codec_el_parsed}\ncodec_range_parsed={codec_range_parsed}")
    print(f"quant={quant}")

    print(f"gdal_cache_max_mb={gdal_cache_max_mb}\nmorton_mode_parsed={morton_mode_parsed}")

    yirgacheffe.constants.YSTEP = ystep_parsed
    yirgacheffe.constants.SUB_BLOCK_WIDTH = xss_parsed
    yirgacheffe.constants.SUB_BLOCK_HEIGHT = yss_parsed

    if gdal_cache_max_mb:
        gdal.SetCacheMax(int(gdal_cache_max_mb) * 1024 * 1024)

    os.makedirs(output_directory_path, exist_ok=True)

    crosswalk_table = load_crosswalk_table(crosswalk_path)

    os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
    try:
        filtered_species_info = gpd.read_file(species_data_path)
    except: # pylint:disable=W0702
        logger.error("Failed to read %s", species_data_path)
        sys.exit(1)
    assert filtered_species_info.shape[0] == 1

    # We drop the geometry as that's a lot of data, more than the raster often
    species_info = filtered_species_info.drop('geometry', axis=1)
    manifest = {k: v[0] for (k, v) in species_info.items()}

    species_id = filtered_species_info.id_no.values[0]
    try:
        seasonality = filtered_species_info.season.values[0]
        result_filename = output_directory_path / f"{species_id}_{seasonality}.tif"
        manifest_filename = output_directory_path / f"{species_id}_{seasonality}.json"
    except AttributeError:
        seasonality = None
        result_filename = output_directory_path / f"{species_id}.tif"
        manifest_filename = output_directory_path / f"{species_id}.json"

    try:
        elevation_lower = math.floor(float(filtered_species_info.elevation_lower.values[0]))
        elevation_upper = math.ceil(float(filtered_species_info.elevation_upper.values[0]))
        raw_habitats = set(filtered_species_info.full_habitat_code.values[0].split('|'))
    except (AttributeError, TypeError):
        logger.error("Species data missing one or more needed attributes: %s", filtered_species_info)
        manifest["error"] = "Species data missing one or more needed attributes"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        sys.exit()

    habitat_list = crosswalk_habitats(crosswalk_table, raw_habitats)
    if force_habitat and len(habitat_list) == 0:
        logger.error("No habitats found in crosswalk! %s_%s had %s", species_id, seasonality, raw_habitats)
        manifest["error"] = "No habitats found in crosswalk"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        sys.exit()

    ideal_habitat_map_files = [habitat_path / f"lcc_{x}_q{quant}.tif" for x in habitat_list]
    habitat_map_files = [x for x in ideal_habitat_map_files if x.exists()]
    if force_habitat and len(habitat_map_files) == 0:
        logger.error("No matching habitat layers found for %s_%s in %s: %s",
                     species_id, seasonality, habitat_path, habitat_list)
        manifest["error"] = "No matching habitat layers found"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        sys.exit()

    t0 = time.time()

    habitat_maps = [RasterLayer.layer_from_file(x) for x in habitat_map_files]

    min_elevation_map = RasterLayer.layer_from_file(min_elevation_path)
    max_elevation_map = RasterLayer.layer_from_file(max_elevation_path)
    if cache_mode_parsed > 0:
        min_elevation_map.enable_cache(codec_el_parsed, morton_mode_parsed)
        max_elevation_map.enable_cache(codec_el_parsed, morton_mode_parsed)
        for map in habitat_maps:
            map.enable_cache(codec_habitat_parsed, morton_mode_parsed)

    range_map_unstaged = VectorLayer.layer_from_file_like(
        species_data_path,
        min_elevation_map,
        datatype=gdal.GDT_Int32
    )
    range_map_staged = VectorLayer.layer_from_file_like(
        species_data_path,
        min_elevation_map,
        datatype=gdal.GDT_Int32
    )

    if cache_mode_parsed > 0:
        range_map_staged.enable_cache(codec_range_parsed, morton_mode_parsed)
        
    area_map = ConstantLayer(1.0)
    if area_path:
        try:
            area_map = UniformAreaLayer.layer_from_file(area_path)
        except ValueError:
            area_map = RasterLayer.layer_from_file(area_path)

    layers = habitat_maps + [min_elevation_map, max_elevation_map, range_map_staged, area_map]
    try:
        intersection = RasterLayer.find_intersection(layers)
    except ValueError:
        logger.warning("Failed to find intersection for %s: %s",  species_data_path, range_map_staged.area)

        result = RasterLayer.empty_raster_layer_like(
            area_map,
            filename=result_filename,
            compress=True,
        )
        with alive_bar(manual=True) as bar:
            range_total = range_map_unstaged.save(result, and_sum=True, callback=bar, do_subchunk=False)

        manifest.update({
            'range_total': range_total,
            'hab_total': 0,
            'dem_total': 0,
            'aoh_total': range_total,
            'prevalence': 1.0,
            'error': 'Failed to find intersection'
        })
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        return

    for layer in layers:
        layer.set_window_for_intersection(intersection)

    def print_cache_sizes():
        sizes = [ \
            ("min_elevation_map", min_elevation_map.size_bytes_cached()), \
            ("max_elevation_map", max_elevation_map.size_bytes_cached()), \
            ("range_map", range_map_staged.size_bytes_cached())  \
        ]
        total = min_elevation_map.size_bytes_cached() + max_elevation_map.size_bytes_cached() + range_map_staged.size_bytes_cached()
        habitat_map_total = 0
        for i in range(0, len(habitat_maps)):
            sizes.append((f"habitat_map_{i}", habitat_maps[i].size_bytes_cached()))
            total += habitat_maps[i].size_bytes_cached()
            habitat_map_total += habitat_maps[i].size_bytes_cached()
        sizes.append(("habitat_map_total", habitat_map_total))
        sizes.append(("total", total))
        for item, size in sizes:
            size_mb = size / (1024 * 1024)
            print(f"{item} = {size} B ({size_mb:.3f} MB)")

    if (cache_mode_parsed > 0):
        print("Staging...")
        min_elevation_map.stage()
        max_elevation_map.stage()
        range_map_staged.stage(area=intersection)
        for map in habitat_maps:
            map.stage()

        print(f"Cache sizes after staging:")
        print_cache_sizes()
        print("")

    range_total = range_map_unstaged.sum(do_subchunk = False)

    # Habitat evaluation. In the IUCN Redlist Technical Working Group recommendations, if there are no defined
    # habitats, then we revert to range. If the area of the habitat map filtered by species habitat is zero then we
    # similarly revert to range as the assumption is that there is an error in the habitat coding.
    #
    # However, for methodologies, such as the LIFE biodiversity metric by Eyres et al, where you want to do
    # land use change impact scenarios, this rule doesn't work, as it treats extinction due to land use change as
    # then actually filling the range. This we have the force_habitat flag for this use case.

    filtered_by_habtitat_is_range = False

    if habitat_maps or force_habitat:
        combined_habitat = habitat_maps[0]
        i = 1
        for map_layer in habitat_maps[1:]:
            i += 1
            combined_habitat = (combined_habitat + map_layer).clip(max=2 ** quant)
        filtered_by_habtitat = range_map_staged * combined_habitat
        if filtered_by_habtitat.sum() == 0:
            if force_habitat:
                print("WARNING: filtered_by_habtitat.sum() == 0 && force_habitat")
                manifest.update({
                    'range_total': range_total,
                    'hab_total': 0,
                    'dem_total': 0,
                    'aoh_total': 0,
                    'prevalence': 0,
                    'error': 'No habitat found and --force-habitat specified'
                })
                with open(manifest_filename, 'w', encoding="utf-8") as f:
                    json.dump(manifest, f)
                return
            else:
                print("WARNING: filtered_by_habtitat.sum() == 0 && !force_habitat. Using range for filtered_by_habtitat.")
                filtered_by_habtitat_is_range = True
                # filtered_by_habtitat = range_map * (2 ** quant)
    else:
        print("WARNING: !(habitat_maps or force_habitat). Using range for filtered_by_habtitat.")
        filtered_by_habtitat_is_range = True
        # filtered_by_habtitat = range_map * (2 ** quant)

    # Elevation evaluation. As per the IUCN Redlist Technical Working Group recommendations, if the elevation
    # filtering of the DEM returns zero, then we ignore this layer on the assumption that there is error in the
    # elevation data. This aligns with the data hygine practices recommended by Busana et al, as implemented
    # in cleaning.py, where any bad values for elevation cause us assume the entire range is valid.
    hab_only_total = filtered_by_habtitat.sum() / (2 ** quant) if not filtered_by_habtitat_is_range else range_total

    filtered_elevation = (min_elevation_map <= (elevation_upper + abs(ELEVATION_MIN_MIN))) & (max_elevation_map >= (elevation_lower + abs(ELEVATION_MAX_MIN)))
    
    dem_only_total = (filtered_elevation * range_map_staged).sum()

    filtered_by_both = filtered_elevation
    if not filtered_by_habtitat_is_range: filtered_by_both *= filtered_by_habtitat 

    if filtered_by_both.sum() == 0:
        filtered_by_both = filtered_by_habtitat if not filtered_by_habtitat_is_range else (range_map_unstaged * (2 ** quant))

    with RasterLayer.empty_raster_layer_like(
        min_elevation_map,
        filename=result_filename,
        compress=True,
        datatype=gdal.GDT_Int32
    ) as aoh_raster:
        with alive_bar(manual=True) as bar:
            aoh_total = filtered_by_both.save(
                aoh_raster, 
                and_sum=True, 
                callback=bar,
                do_subchunk = (not filtered_by_habtitat_is_range)
            ) / (2 ** quant)

    t1 = time.time()

    print(f"total time {(t1 - t0) * 1000}")

    manifest.update({
        'range_total': range_total,
        'hab_total': hab_only_total,
        'dem_total': dem_only_total,
        'aoh_total': aoh_total,
        'prevalence': (aoh_total / range_total) if range_total else 0,
    })
    with open(manifest_filename, 'w', encoding="utf-8") as f:
        json.dump(manifest, f)

    print(f"Metrics:")
    print(f"TIME_SPENT_PREPROCESSING={yirgacheffe.metrics.TIME_SPENT_PREPROCESSING}")
    print(f"TIME_SPENT_CALCULATING={yirgacheffe.metrics.TIME_SPENT_CALCULATING}")
    print(f"TIME_SPENT_LOADING={yirgacheffe.metrics.TIME_SPENT_LOADING}")
    print(f"TIME_SPENT_WRITING={yirgacheffe.metrics.TIME_SPENT_WRITING}")
    print(f"TIME_SPENT_COMPRESSING={yirgacheffe.metrics.TIME_SPENT_COMPRESSING}")
    print(f"TIME_SPENT_DECOMPRESSING={yirgacheffe.metrics.TIME_SPENT_DECOMPRESSING}")

    TIME_SPENT_ARITHMETIC = \
        yirgacheffe.metrics.TIME_SPENT_CALCULATING - yirgacheffe.metrics.TIME_SPENT_WRITING - yirgacheffe.metrics.TIME_SPENT_DECOMPRESSING
    
    NON_IO_TIME_SPENT = yirgacheffe.metrics.TIME_SPENT_PREPROCESSING + yirgacheffe.metrics.TIME_SPENT_CALCULATING - yirgacheffe.metrics.TIME_SPENT_LOADING - yirgacheffe.metrics.TIME_SPENT_WRITING

    NON_IO_TIME_SPENT_PROJECTED_WITH_FUSE = NON_IO_TIME_SPENT
    if cache_mode_parsed == 2:
        NON_IO_TIME_SPENT_PROJECTED_WITH_FUSE -= TIME_SPENT_ARITHMETIC

    print(f"\nTIME_SPENT_ARITHMETIC={TIME_SPENT_ARITHMETIC}")
    print(f"NON_IO_TIME_SPENT={NON_IO_TIME_SPENT}")
    print(f"NON_IO_TIME_SPENT_PROJECTED_WITH_FUSE={NON_IO_TIME_SPENT_PROJECTED_WITH_FUSE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")
    parser.add_argument(
        '--habitats',
        type=Path,
        help="Directory of habitat rasters, one per habitat class.",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        '--elevation-min',
        type=Path,
        help="Minimum elevation raster.",
        required=True,
        dest="min_elevation_path",
    )
    parser.add_argument(
        '--elevation-max',
        type=Path,
        help="Maximum elevation raster",
        required=True,
        dest="max_elevation_path",
    )
    parser.add_argument(
        '--area',
        type=Path,
        help="Optional area per pixel raster. Can be 1xheight.",
        required=False,
        dest="area_path",
    )
    parser.add_argument(
        '--crosswalk',
        type=str,
        help="Path of habitat crosswalk table.",
        required=True,
        dest="crosswalk_path",
    )
    parser.add_argument(
        '--speciesdata',
        type=Path,
        help="Single species/seasonality geojson.",
        required=True,
        dest="species_data_path"
    )
    parser.add_argument(
        '--force-habitat',
        help="If set, don't treat an empty habitat layer layer as per IRTWG.",
        dest="force_habitat",
        action='store_true',
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Directory where area geotiffs should be stored.',
        required=True,
        dest='output_path',
    )
    parser.add_argument(
        '--cache-mode',
        type=int,
        help='',
        required=False,
        dest='cache_mode',
    )
    parser.add_argument(
        '--ys',
        type=int,
        help='',
        required=False,
        dest='ystep',
    )
    parser.add_argument(
        '--xss',
        type=int,
        help='',
        required=False,
        dest='xss',
    )
    parser.add_argument(
        '--yss',
        type=int,
        help='',
        required=False,
        dest='yss',
    )
    parser.add_argument(
        '--codec-habitat',
        type=int,
        help='',
        required=False,
        dest='codec_habitat',
    )
    parser.add_argument(
        '--codec-elevation',
        type=int,
        help='',
        required=False,
        dest='codec_elevation',
    )
    parser.add_argument(
        '--codec-range',
        type=int,
        help='',
        required=False,
        dest='codec_range',
    )
    parser.add_argument(
        '--gdal-cache-max-mb',
        type=int,
        help='',
        required=False,
        dest='gdal_cache_max_mb',
    )
    parser.add_argument(
        '--morton-mode',
        type=int,
        help='',
        required=False,
        dest='morton_mode',
    )
    parser.add_argument(
        '--quant',
        type=int,
        help='',
        required=True,
        dest='quant',
    )
    args = parser.parse_args()

    aohcalc(
        args.habitat_path,
        args.min_elevation_path,
        args.max_elevation_path,
        args.area_path,
        args.crosswalk_path,
        args.species_data_path,
        args.force_habitat,
        args.output_path,
        args.cache_mode,
        args.ystep,
        args.xss,
        args.yss,
        args.codec_habitat,
        args.codec_elevation,
        args.codec_range,
        args.gdal_cache_max_mb,
        args.morton_mode,
        args.quant
    )

if __name__ == "__main__":
    main()
