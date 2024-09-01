import argparse
import os
import sys
from typing import Dict, List

import pyshark # pylint: disable=W0611
import numpy as np
import pandas as pd
from geopandas import gpd
from yirgacheffe.layers import RasterLayer, VectorLayer
from alive_progress import alive_bar

import time

def load_crosswalk_table(table_file_name: str) -> Dict[str,int]:
    rawdata = pd.read_csv(table_file_name)
    result = {}
    for _, row in rawdata.iterrows():
        try:
            result[row.code].append(int(row.value))
        except KeyError:
            result[row.code] = [int(row.value)]
    return result

def crosswalk_habitats(crosswalk_table: Dict[str, int], raw_habitats: List) -> List:
    result = []
    for habitat in raw_habitats:
        try:
            hab = float(habitat)
        except ValueError:
            continue
        try:
            crosswalked_habatit = crosswalk_table[hab]
        except KeyError:
            continue
        result += crosswalked_habatit
    return result

def aohcalc(
    habitat_path: str,
    elevation_path: str,
    crosswalk_path: str,
    species_data_path: str,
    output_directory_path: str,
) -> None:
    os.makedirs(output_directory_path, exist_ok=True)

    start_time = time.perf_counter_ns()
    crosswalk_table = load_crosswalk_table(crosswalk_path)
    print(f"Crosswalk table loaded in {time.perf_counter_ns() - start_time} ns")

    start_time = time.perf_counter_ns()
    filtered_species_info = gpd.read_file(species_data_path)
    print(f"Species data loaded in {time.perf_counter_ns() - start_time} ns")
    assert filtered_species_info.shape[0] == 1

    try:
        elevation_lower = int(float(filtered_species_info.elevation_lower.values[0]))
        elevation_upper = int(float(filtered_species_info.elevation_upper.values[0]))
        raw_habitats = filtered_species_info.full_habitat_code.values[0].split('|')
    except (AttributeError, TypeError):
        print(f"Species data missing one or more needed attributes: {filtered_species_info}", file=sys.stderr)
        sys.exit()

    start_time = time.perf_counter_ns()
    habitat_list = crosswalk_habitats(crosswalk_table, raw_habitats)
    print(f"Habitat list crosswalked in {time.perf_counter_ns() - start_time} ns")

    species_id = filtered_species_info.id_no.values[0]
    seasonality = filtered_species_info.seasonal.values[0]
    if len(habitat_list) == 0:
        print(f"No habitat for {species_id} {seasonality}")
        return

    start_time = time.perf_counter_ns()
    habitat_map = RasterLayer.layer_from_file(habitat_path)
    elevation_map = RasterLayer.layer_from_file(elevation_path)
    range_map = VectorLayer.layer_from_file_like(
        species_data_path,
        f'id_no = {species_id} AND seasonal = {seasonality}',
        habitat_map
    )
    print(f"Maps loaded in {time.perf_counter_ns() - start_time} ns")

    layers = [habitat_map, elevation_map, range_map]

    start_time = time.perf_counter_ns()
    intersection = RasterLayer.find_intersection(layers)
    print(f"Intersection found in {time.perf_counter_ns() - start_time} ns")

    for layer in layers:
        layer.set_window_for_intersection(intersection)

    result_filename = os.path.join(output_directory_path, f"{species_id}_{seasonality}.tif")
    result = RasterLayer.empty_raster_layer_like(
        habitat_map,
        filename=result_filename,
        compress=True,
        nodata=2,
        nbits=2
    )

    try:
        start_time = time.perf_counter_ns()
        filtered_habtitat = habitat_map.numpy_apply(lambda chunk: np.isin(chunk, habitat_list))
        print(f"Filtered habitat map in {time.perf_counter_ns() - start_time} ns")
    except ValueError:
        print(habitat_list)
        assert False

    start_time = time.perf_counter_ns()
    filtered_elevation = elevation_map.numpy_apply(
        lambda chunk: np.logical_and(chunk >= elevation_lower, chunk <= elevation_upper)
    )
    print(f"Filtered elevation map in {time.perf_counter_ns() - start_time} ns")

    start_time = time.perf_counter_ns()
    calc = filtered_habtitat * filtered_elevation * range_map
    calc = calc + (range_map.numpy_apply(lambda chunk: (1 - chunk)) * 2)
    print(f"Calculation completed in {time.perf_counter_ns() - start_time} ns")

    with alive_bar(manual=True) as bar:
        calc.save(result, callback=bar)

def main() -> None:
    parser = argparse.ArgumentParser(description="Area of habitat calculator.")
    parser.add_argument(
        '--habitat',
        type=str,
        help="habitat raster",
        required=True,
        dest="habitat_path"
    )
    parser.add_argument(
        '--elevation',
        type=str,
        help="elevation raster",
        required=True,
        dest="elevation_path",
    )
    parser.add_argument(
        '--crosswalk',
        type=str,
        help="habitat crosswalk table path",
        required=True,
        dest="crosswalk_path",
    )
    parser.add_argument(
        '--speciesdata',
        type=str,
        help="Single species/seasonality geojson",
        required=True,
        dest="species_data_path"
    )
    parser.add_argument(
        '--output_directory',
        type=str,
        help='directory where area geotiffs should be stored',
        required=True,
        dest='output_path',
    )
    args = parser.parse_args()

    aohcalc(
        args.habitat_path,
        args.elevation_path,
        args.crosswalk_path,
        args.species_data_path,
        args.output_path
    )

if __name__ == "__main__":
    main()
