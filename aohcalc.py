import argparse
import json
import math
import os
import logging
import sys
from pathlib import Path
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
yirgacheffe.constants.VERBOSE_CACHE = False

from memory_profiler import profile

import fiona

CACHE_EXTRA = False

CODEC_ID_UNIFORM = 0
CODEC_ID_BINARY = 6

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')

# def rasterise_species_geojson(
#     species_path: Path,
#     reference_layer: RasterLayer,
#     output_path: Path,
#     burn_value: Union[int, float, str] = 1
# ) -> Path:
#     """
#     Rasterises a species GeoJSON to a GeoTIFF aligned with the reference raster grid,
#     but only covering the bounding box of the species geometry.
#     """
#     vectors = ogr.Open(str(species_path))
#     if vectors is None:
#         raise FileNotFoundError(f"Failed to open {species_path}")
#     layer = vectors.GetLayer()

#     # Use reference projection
#     projection = reference_layer.map_projection
#     abs_xstep, abs_ystep = abs(projection.xstep), abs(projection.ystep)

#     # Get species geometry bounding box
#     layer_extent = layer.GetExtent()  # (minx, maxx, miny, maxy)

#     # Snap bounding box to reference raster grid
#     left = math.floor(layer_extent[0] / abs_xstep) * abs_xstep
#     right = math.ceil(layer_extent[1] / abs_xstep) * abs_xstep
#     bottom = math.floor(layer_extent[2] / abs_ystep) * abs_ystep
#     top = math.ceil(layer_extent[3] / abs_ystep) * abs_ystep

#     width = round((right - left) / abs_xstep)
#     height = round((top - bottom) / abs_ystep)

#     options = ["INTERLEAVE=BAND", "COMPRESS=LZW", f"BLOCKXSIZE={width}", "BLOCKYSIZE=1"]

#     dataset = gdal.GetDriverByName("GTiff").Create(
#         str(output_path),
#         width,
#         height,
#         1,
#         reference_layer.datatype.to_gdal(),
#         options,
#     )
#     dataset.SetProjection(projection.name)
#     dataset.SetGeoTransform([left, projection.xstep, 0.0, top, 0.0, projection.ystep])

#     if isinstance(burn_value, (int, float)):
#         gdal.RasterizeLayer(dataset, [1], layer, burn_values=[burn_value], options=["ALL_TOUCHED=TRUE"])
#     elif isinstance(burn_value, str):
#         gdal.RasterizeLayer(dataset, [1], layer, options=[f"ATTRIBUTE={burn_value}", "ALL_TOUCHED=TRUE"])
#     else:
#         raise ValueError("Burn value must be number or field name")

#     return output_path

def rasterise_species_geojson(
    species_path: Path,
    reference_layer: RasterLayer,
    output_path: Path,
    burn_value: Union[int, float, str] = 1
) -> Path:
    """
    Rasterises a species GeoJSON to a GeoTIFF aligned with the full reference raster grid.
    """
    vectors = ogr.Open(str(species_path))
    if vectors is None:
        raise FileNotFoundError(f"Failed to open {species_path}")
    layer = vectors.GetLayer()

    projection = reference_layer.map_projection
    area = reference_layer.area
    abs_xstep, abs_ystep = abs(projection.xstep), abs(projection.ystep)

    width = round((area.right - area.left) / abs_xstep)
    height = round((area.top - area.bottom) / abs_ystep)

    # options = [
    #     "INTERLEAVE=BAND",
    #     "COMPRESS=LZW",
    #     "PREDICTOR=2",   # improves LZW compression for integer rasters
    #     # f"BLOCKXSIZE={width}",
    #     # "BLOCKYSIZE=1",
    #     "SPARSE_OK=TRUE",
    #     "BLOCKXSIZE=512",
    #     "BLOCKYSIZE=1"
    # ]

    # dataset = gdal.GetDriverByName("GTiff").Create(
    #     str(output_path),
    #     width,
    #     height,
    #     1,
    #     reference_layer.datatype.to_gdal(),
    #     options,
    # )

    # options = [
    #     "NBITS=1",        # store as 1-bit
    #     "TILED=YES",      # better for IO
    #     "SPARSE_OK=TRUE", # avoids writing big empty tiles
    # ]
    # dataset = gdal.GetDriverByName("GTiff").Create(
    #     str(output_path),
    #     width,
    #     height,
    #     1,
    #     gdal.GDT_Byte,
    #     options,
    # )

    options = [
        "TILED=YES",
        "BLOCKXSIZE=16",
        "BLOCKYSIZE=16",
        "INTERLEAVE=BAND",
        "SPARSE_OK=TRUE",
    ]
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(output_path),
        width,
        height,
        1,
        gdal.GDT_Byte,   # 1 byte per pixel, no compression
        options,
    )

    # Mark background as nodata
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(0)
    
    dataset.SetProjection(projection.name)
    dataset.SetGeoTransform([
        area.left, projection.xstep, 0.0,
        area.top, 0.0, projection.ystep
    ])

    if isinstance(burn_value, (int, float)):
        gdal.RasterizeLayer(dataset, [1], layer, burn_values=[burn_value], options=["ALL_TOUCHED=TRUE"])
    elif isinstance(burn_value, str):
        gdal.RasterizeLayer(dataset, [1], layer, options=[f"ATTRIBUTE={burn_value}", "ALL_TOUCHED=TRUE"])
    else:
        raise ValueError("Burn value must be number or field name")

    dataset.FlushCache()
    dataset = None  # close and write to disk

    return output_path



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
    yss: Optional[int]
) -> None:
    global CODEC_ID_UNIFORM
    global CODEC_ID_BINARY

    cache_mode_parsed = int(cache_mode) if cache_mode else 0
    ystep_parsed = int(ystep) if ystep else 2048
    xss_parsed = int(xss) if xss else 256
    yss_parsed = int(yss) if yss else 256

    print(f"cache_mode_parsed={cache_mode_parsed}\nystep_parsed={ystep_parsed}\nxss_parsed={xss_parsed}\nyss_parsed={yss_parsed}")

    yirgacheffe.constants.YSTEP = ystep_parsed
    yirgacheffe.constants.SUB_BLOCK_WIDTH = xss_parsed
    yirgacheffe.constants.SUB_BLOCK_HEIGHT = yss_parsed

    if cache_mode_parsed == 1:
        CODEC_ID_UNIFORM = -1
        CODEC_ID_BINARY = -1
        # CODEC_ID_UNIFORM = 99
        # CODEC_ID_BINARY = 99

    if cache_mode_parsed > 0:
        gdal.SetCacheMax(1 * 1024 * 1024) # (mostly) disable gdal cache in favor of custom

    os.makedirs(output_directory_path, exist_ok=True)

    crosswalk_table = load_crosswalk_table(crosswalk_path)

    os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
    try:
        with fiona.open(species_data_path) as src:
            feature = next(iter(src))  # assume one feature per file
            props = dict(feature["properties"])
    except Exception as e:
        logger.error("Failed to read %s: %s", species_data_path, e)
        sys.exit(1)

    manifest = props.copy()

    species_id = props.get("id_no")
    seasonality = props.get("season")
    if seasonality:
        result_filename = output_directory_path / f"{species_id}_{seasonality}.tif"
        manifest_filename = output_directory_path / f"{species_id}_{seasonality}.json"
    else:
        result_filename = output_directory_path / f"{species_id}.tif"
        manifest_filename = output_directory_path / f"{species_id}.json"

    try:
        elevation_lower = int(math.floor(float(props.get("elevation_lower", 0))))
        elevation_upper = int(math.ceil(float(props.get("elevation_upper", 0))))
        raw_habitats = set(props.get("full_habitat_code", "").split("|"))
    except (AttributeError, TypeError, ValueError):
        logger.error("Species data missing one or more needed attributes: %s", props)
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

    ideal_habitat_map_files = [habitat_path / f"lcc_{x}_q22.tif" for x in habitat_list]
    habitat_map_files = [x for x in ideal_habitat_map_files if x.exists()]
    if force_habitat and len(habitat_map_files) == 0:
        logger.error("No matching habitat layers found for %s_%s in %s: %s",
                     species_id, seasonality, habitat_path, habitat_list)
        manifest["error"] = "No matching habitat layers found"
        with open(manifest_filename, 'w', encoding="utf-8") as f:
            json.dump(manifest, f)
        sys.exit()

    habitat_maps = [RasterLayer.layer_from_file(x) for x in habitat_map_files]

    min_elevation_map = RasterLayer.layer_from_file(min_elevation_path)
    max_elevation_map = RasterLayer.layer_from_file(max_elevation_path)
    if cache_mode_parsed > 0:
        min_elevation_map.compress = True
        min_elevation_map.codec_id = CODEC_ID_UNIFORM

        max_elevation_map.compress = True
        max_elevation_map.codec_id = CODEC_ID_UNIFORM

        for map in habitat_maps:
            map.compress = True
            map.codec_id = CODEC_ID_UNIFORM

    # (min_elevation_map <= 0).sum()
    # (max_elevation_map <= 0).sum()

    # species_raster_path = species_data_path.with_suffix(".tif")

    # if not species_raster_path.exists(): # only rasterise if not already done
    #     print(f"rasterising species geojson {species_data_path}")
    #     rasterise_species_geojson(
    #         species_data_path,
    #         min_elevation_map,
    #         species_raster_path,
    #         burn_value=1
    #     )

    # range_map = RasterLayer.layer_from_file(species_raster_path)

    range_map = VectorLayer.layer_from_file_like(
        species_data_path,
        min_elevation_map
    )

    if cache_mode_parsed > 0:
        range_map.compress = True
        range_map.codec_id = CODEC_ID_BINARY
        
    area_map = ConstantLayer(1.0)
    if area_path:
        try:
            area_map = UniformAreaLayer.layer_from_file(area_path)
        except ValueError:
            area_map = RasterLayer.layer_from_file(area_path)


    layers = habitat_maps + [min_elevation_map, max_elevation_map, range_map, area_map]
    try:
        intersection = RasterLayer.find_intersection(layers)
    except ValueError:
        logger.warning("Failed to find intersection for %s: %s",  species_data_path, range_map.area)

        result = RasterLayer.empty_raster_layer_like(
            area_map,
            filename=result_filename,
            compress=True,
        )
        with alive_bar(manual=True) as bar:
            range_total = range_map.save(result, and_sum=True, callback=bar)

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

    range_total = range_map.sum()

    # Habitat evaluation. In the IUCN Redlist Technical Working Group recommendations, if there are no defined
    # habitats, then we revert to range. If the area of the habitat map filtered by species habitat is zero then we
    # similarly revert to range as the assumption is that there is an error in the habitat coding.
    #
    # However, for methodologies, such as the LIFE biodiversity metric by Eyres et al, where you want to do
    # land use change impact scenarios, this rule doesn't work, as it treats extinction due to land use change as
    # then actually filling the range. This we have the force_habitat flag for this use case.
    if habitat_maps or force_habitat:
        combined_habitat = habitat_maps[0]
        for map_layer in habitat_maps[1:]:
            combined_habitat = combined_habitat + map_layer
        combined_habitat = combined_habitat.clip(max=1.0)
        filtered_by_habtitat = range_map * combined_habitat
        if cache_mode_parsed > 0 and CACHE_EXTRA:
            filtered_by_habtitat.compress = True
            filtered_by_habtitat.codec_id = CODEC_ID_UNIFORM
        if filtered_by_habtitat.sum() == 0:
            if force_habitat:
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
                filtered_by_habtitat = range_map
    else:
        filtered_by_habtitat = range_map

    # Elevation evaluation. As per the IUCN Redlist Technical Working Group recommendations, if the elevation
    # filtering of the DEM returns zero, then we ignore this layer on the assumption that there is error in the
    # elevation data. This aligns with the data hygine practices recommended by Busana et al, as implemented
    # in cleaning.py, where any bad values for elevation cause us assume the entire range is valid.
    hab_only_total = filtered_by_habtitat.sum()

    filtered_elevation = (min_elevation_map <= elevation_upper) & (max_elevation_map >= elevation_lower)
    if cache_mode_parsed > 0 and CACHE_EXTRA:
        filtered_elevation.compress = True
        filtered_elevation.codec_id = CODEC_ID_BINARY

    # wtf = (min_elevation_map <= elevation_upper).sum()
    # (min_elevation_map <= 0).sum()
    # (max_elevation_map <= 0).sum()
    dem_only_total = (filtered_elevation * range_map).sum()

    filtered_by_both = filtered_elevation * filtered_by_habtitat
    if cache_mode_parsed > 0 and CACHE_EXTRA:
        filtered_by_both.compress = True
        filtered_by_both.codec_id = CODEC_ID_UNIFORM
    if filtered_by_both.sum() == 0:
        filtered_by_both = filtered_by_habtitat

    # calc = filtered_by_both * area_map

    with RasterLayer.empty_raster_layer_like(
        min_elevation_map,
        filename=result_filename,
        compress=True,
        datatype=gdal.GDT_Int32
    ) as aoh_raster:
        with alive_bar(manual=True) as bar:
            aoh_total = filtered_by_both.save(aoh_raster, and_sum=True, callback=bar)

    manifest.update({
        'range_total': range_total,
        'hab_total': hab_only_total,
        'dem_total': dem_only_total,
        'aoh_total': aoh_total,
        'prevalence': (aoh_total / range_total) if range_total else 0,
    })
    with open(manifest_filename, 'w', encoding="utf-8") as f:
        json.dump(manifest, f)

    print(f"T_CALC={yirgacheffe.constants.TIME_SPENT_CALCULATING}\nT_LOAD={yirgacheffe.constants.TIME_SPENT_LOADING}\nT_WRITE={yirgacheffe.constants.TIME_SPENT_WRITING}")


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
        args.yss
    )

if __name__ == "__main__":
    main()
