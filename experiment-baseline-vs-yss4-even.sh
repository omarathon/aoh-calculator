#!/bin/bash

TRIES=("0" "1" "2" "3" "4")
# TRIES=("0")

EXP_DIR="exp-baseline-vs-yss4-even"

echo "warming 1"
./run-small-scratch-even.sh "aohs_warm1" '' '' '' '' &> "${EXP_DIR}/warm_1.txt"
echo "warming 2"
./run-small-scratch-even.sh "aohs_warm2" '' '' '' '' &> "${EXP_DIR}/warm_2.txt"
echo "warming 3"
./run-small-scratch-even.sh "aohs_warm3" '' '' '' '' &> "${EXP_DIR}/warm_3.txt"

for TRY in "${TRIES[@]}"; do
    echo "Running baseline TRY ${TRY}"
    ./run-small-scratch-scrm.sh "aohs_baseline_try_${TRY}" '' '' '' '' &> "${EXP_DIR}/baseline_try_${TRY}.txt"
    echo "done"
done

for TRY in "${TRIES[@]}"; do
    SCRM="1"
    YSUBSTEP="4"
    output_file="${EXP_DIR}/scrm_${SCRM}_yss_${YSUBSTEP}_try_${TRY}.txt"
    echo "Running SCRM ${SCRM} YSUBSTEP ${YSUBSTEP} TRY ${TRY}"
    ./run-small-scratch-scrm.sh "aohs_${SCRM}_yss_${YSUBSTEP}_try_${TRY}" '' '' "${SCRM}" "${YSUBSTEP}" &> "${output_file}"
    echo "done"
done
