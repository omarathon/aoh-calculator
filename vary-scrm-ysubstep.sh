#!/bin/bash

TRIES = ("0" "1" "2" "3" "4")

for TRY in "${TRIES[@]}"; do
    echo "Running baseline TRY ${TRY}"
    ./run-small-scratch-scrm.sh '' '' '' &> "vary_scrm_ysubstep/baseline_try_${TRY}.txt"
    echo "done"
done

SCRMS = ("1" "2")
Y_SUBSTEPS = ("1" "2" "4" "8" "16" "32" "64")

for SCRM in "${SCRMS[@]}"; do
    for YSUBSTEP in "${Y_SUBSTEPS[@]}"; do
        for TRY in "${TRIES[@]}"; do
            output_file="vary_scrm_ysubstep/scrm_${SCRM}_yss_${YSUBSTEP}_try_${TRY}.txt"
            echo "Running SCRM ${SCRM} YSUBSTEP ${YSUBSTEP} TRY ${TRY}"
            ./run-small-scratch-scrm.sh '' "${SCRM}" "${YSUBSTEP}" &> "${output_file}"
            echo "done"
        done
    done
done