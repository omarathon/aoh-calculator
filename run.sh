#!/bin/bash
set -euo pipefail

N="${1:-}"

area_path="/maps/omsst2/life-v1/area-per-pixel.tif"
elevation_min_path="/maps/omsst2/life-v1/elevation-min-1k.tif"
elevation_max_path="/maps/omsst2/life-v1/elevation-max-1k.tif"
crosswalk_path="/maps/omsst2/life-v1/crosswalk.csv"

taxas=("AMPHIBIA" "AVES")

species_data_dir="/maps/omsst2/life-v1/species-info"

habitats_current_path="/maps/omsst2/life-v1/habitat_maps/current"
habitats_restore_path="/maps/omsst2/life-v1/habitat_maps/restore"
habitats_arable_path="/maps/omsst2/life-v1/habitat_maps/arable"
habitats_pnv_path="/maps/omsst2/life-v1/habitat_maps/pnv"

output_directory="/maps/omsst2/life-v1/aohs"

echo "$taxas" | while read -r TAXA; do

    species_data_path_current="${species_data_dir}/${TAXA}/current"
    species_data_path_historic="${species_data_dir}/${TAXA}/historic"

    species_files_current=$(find "$species_data_path_current" -name "*.geojson")
    species_files_historic=$(find "$species_data_path_historic" -name "*.geojson")

    total_current=$(echo "$species_files_current" | wc -l)
    total_historic=$(echo "$species_files_historic" | wc -l)

    if [ -n "$N" ] && [ "$N" -lt "$total_current" ]; then
        step=$(awk "BEGIN {print $total_current/$N}")
        sampled=$(echo "$species_files_current" | awk -v step="$step" '
            NR==1 || int((NR-1) % step) == 0 {
                print NR ":" $0
            }')
        species_files_current=$(echo "$sampled" | cut -d: -f2-)
    fi

    if [ -n "$N" ] && [ "$N" -lt "$total_historic" ]; then
        step=$(awk "BEGIN {print $total_historic/$N}")
        sampled=$(echo "$species_files_historic" | awk -v step="$step" '
            NR==1 || int((NR-1) % step) == 0 {
                print NR ":" $0
            }')
        species_files_historic=$(echo "$sampled" | cut -d: -f2-)
    fi

    total_current=$(echo "$species_files_current" | wc -l)
    total_historic=$(echo "$species_files_historic" | wc -l)

    echo "species files current:"
    echo "${species_files_current}"
    echo "species files historic:"
    echo "${species_files_historic}"

    i=0
    start_time=$(date +%s)

    echo "$species_files_current" | while read -r species_file; do
        i=$((i+1))
        species_name=$(basename "$species_file" .geojson)

        now=$(date +%s)
        elapsed=$((now - start_time))
        avg=$((elapsed / i))
        remaining=$(((total_current - i) * avg))

        echo "[$i/$total_current] species=${species_name}, elapsed=${elapsed}s, est_remaining=${remaining}s"

        echo "TAXA=${TAXA}, habitat=current, species=${species_name}..."
        python3 ./aohcalc.py --habitats "$habitats_current_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/current/${TAXA}"

        echo "TAXA=${TAXA}, habitat=restore, species=${species_name}..."
        python3 ./aohcalc.py --habitats "$habitats_restore_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/restore/${TAXA}"

        echo "TAXA=${TAXA}, habitat=arable, species=${species_name}..."
        python3 ./aohcalc.py --habitats "$habitats_arable_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/arable/${TAXA}"

    done

    echo "$species_files_historic" | while read -r species_file; do
        i=$((i+1))
        species_name=$(basename "$species_file" .geojson)

        now=$(date +%s)
        elapsed=$((now - start_time))
        avg=$((elapsed / i))
        remaining=$(((total_historic - i) * avg))

        echo "[$i/$total_historic] species=${species_name}, elapsed=${elapsed}s, est_remaining=${remaining}s"

        echo "TAXA=${TAXA} habitat=pnv, species=${species_name}..."
        python3 ./aohcalc.py --habitats "$habitats_pnv_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/pnv/${TAXA}"

    done

done




