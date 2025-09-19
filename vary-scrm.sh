#!/bin/bash
SCRMS = ("0" "1" "2")
TRIES = ("0" "1" "2" "3" "4")

for SCRM in "${SCRMS[@]}"; do
    for TRY in "${TRIES[@]}"; do
        output_file="vary_scrm/scrm_${SCRM}_try_${TRY}.txt"
        echo "Running SCRM ${SCRM} try ${TRY}"
        ./run-small-scratch-scrm.sh '' "${SCRM}" &> "${output_file}"
    done
done