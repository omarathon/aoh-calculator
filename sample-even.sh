#!/bin/bash
set -euo pipefail

N_AMPH=${1:-30} 
N_AVES=${2:-43}

SCRM="${3:-0}"
YSUBSTEP="${4:-2048}"

data_base="/maps/omsst2/life-v1"
# data_base="/home/omar/eeg/data/life-small"

area_path="${data_base}/area-per-pixel.tif"
elevation_min_path="${data_base}/elevation-min-1k.tif"
elevation_max_path="${data_base}/elevation-max-1k.tif"
crosswalk_path="${data_base}/crosswalk.csv"

taxas=("AMPHIBIA" "AVES")

species_data_dir="${data_base}/species-info"

habitats_current_path="${data_base}/habitat_maps/current"
habitats_restore_path="${data_base}/habitat_maps/restore"
habitats_arable_path="${data_base}/habitat_maps/arable"
habitats_pnv_path="${data_base}/habitat_maps/pnv"

output_directory="${data_base}/aohs"

for TAXA in "${taxas[@]}"; do

    if [ "$TAXA" = "AMPHIBIA" ]; then
        N="$N_AMPH"
    else
        N="$N_AVES"
    fi

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

done




