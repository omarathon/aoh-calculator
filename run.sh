#!/bin/bash
set -euo pipefail

N="${1:-}"


species_data_dir="/maps/omsst2/life-v1/species-info"
area_path="/maps/omsst2/life-v1/area-per-pixel.tif"

habitats_current_path="/maps/omsst2/life-v1/habitat_maps/current"
habitats_restore_path="/maps/omsst2/life-v1/habitat_maps/restore"
habitats_arable_path="/maps/omsst2/life-v1/habitat_maps/arable"
habitats_pnv_path="/maps/omsst2/life-v1/habitat_maps/pnv"

elevation_min_path="/maps/omsst2/life-v1/elevation-min-1k.tif"
elevation_max_path="/maps/omsst2/life-v1/elevation-max-1k.tif"
crosswalk_path="/maps/omsst2/life-v1/crosswalk.csv"
output_directory="/maps/omsst2/life-v1/aohs"

species_files=$(find "$species_data_dir" -name "*.geojson")
total=$(echo "$species_files" | wc -l)

# evenly sample N if specified
if [ -n "$N" ] && [ "$N" -lt "$total" ]; then
    step=$(awk "BEGIN {print $total/$N}")
    # select every 'step'-th line and print its index
    sampled=$(echo "$species_files" | awk -v step="$step" '
        NR==1 || int((NR-1) % step) == 0 {
            print NR ":" $0
        }')
    # split into species_files without index for further processing
    species_files=$(echo "$sampled" | cut -d: -f2-)
    echo "Sampled species indexes:"
    echo "$sampled" | cut -d: -f1
    echo "(total: ${total})"
fi

total=$(echo "$species_files" | wc -l)

i=0
start_time=$(date +%s)

echo "Processing $total species files..."

echo "$species_files" | while read -r species_file; do
    i=$((i+1))
    species_name=$(basename "$species_file" .geojson)

    now=$(date +%s)
    elapsed=$((now - start_time))
    avg=$((elapsed / i))
    remaining=$(((total - i) * avg))

    echo "[$i/$total] species=${species_name}, elapsed=${elapsed}s, est_remaining=${remaining}s"

    echo "habitat=current, species=${species_name}..."
    python3 ./aohcalc.py --habitats "$habitats_current_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/current"

    echo "habitat=restore, species=${species_name}..."
    python3 ./aohcalc.py --habitats "$habitats_restore_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/restore"

    echo "habitat=arable, species=${species_name}..."
    python3 ./aohcalc.py --habitats "$habitats_arable_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/arable"

    echo "habitat=pnv, species=${species_name}..."
    python3 ./aohcalc.py --habitats "$habitats_pnv_path" --elevation-min "${elevation_min_path}" --elevation-max "${elevation_max_path}" --area "${area_path}" --crosswalk "$crosswalk_path" --speciesdata "$species_file" --output "${output_directory}/pnv"

done