python3 aohcalc.py --habitats /home/omar/eeg/data/life-small/habitat_maps_q22/pnv --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/life-small/species-info/AVES/historic/22689332_RESIDENT.geojson --output /home/omar/eeg/data/life-small/aohs_quant_base/pnv/AVES

/usr/local/bin/perf stat --no-big-num -e cache-references,cache-misses,L1-dcache-loads,L1-dcache-load-misses,L1-dcache-stores python3 aohcalc.py --habitats /home/omar/eeg/data/life-small/habitat_maps_q22/pnv --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/life-small/species-info/AVES/historic/22689332_RESIDENT.geojson --output /home/omar/eeg/data/life-small/aohs_quant_base/pnv/AVES






# slowest on server....
python3 ./aohcalc.py --scrm 0 --ysubstep 2048 --habitats /scratch/omsst2/life-small/habitat_maps/current --elevation-min /scratch/omsst2/life-small/elevation-min-1k.tif --elevation-max /scratch/omsst2/life-small/elevation-max-1k.tif --crosswalk /scratch/omsst2/life-small/crosswalk.csv --speciesdata /scratch/omsst2/species-info-specific/AVES/current/22706068_BREEDING.geojson --output /scratch/omsst2/aohs_specific_main/current/AVES




# slowest runtime

python3 ./aohcalc.py --scrm 0 --ysubstep 2048 --habitats /home/omar/eeg/data/life-small/habitat_maps_q22/current --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/species-info-specific/species-info-specific/AVES/current/22706068_BREEDING.geojson --output /home/omar/eeg/data/life-specific/aohs_quant_base/current/AVES


# avg runtime

python3 ./aohcalc.py --scrm 0 --ysubstep 2048 --habitats /home/omar/eeg/data/life-small/habitat_maps_q22/restore --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/species-info-specific/species-info-specific/AVES/current/22682298_RESIDENT.geojson --output /home/omar/eeg/data/life-specific/aohs_quant_base/restore/AVES





## local ^ but unquantized

## slowest
python3 ./aohcalc.py --habitats /home/omar/eeg/data/life-small/habitat_maps/current --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/species-info-specific/species-info-specific/AVES/current/22706068_BREEDING.geojson --output /home/omar/eeg/data/life-specific/aohs_base/current/AVES


##avg
python3 ./aohcalc.py --habitats /home/omar/eeg/data/life-small/habitat_maps/restore --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/species-info-specific/species-info-specific/AVES/current/22682298_RESIDENT.geojson --output /home/omar/eeg/data/life-specific/aohs_base/restore/AVES




## local ^ but compressed + quantized

## slowest
python3 ./aohcalc.py --habitats /home/omar/eeg/data/life-small/habitat_maps_q22/current --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k-int32-shift.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k-int32-shift.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/species-info-specific/species-info-specific/AVES/current/22706068_BREEDING.geojson --output /home/omar/eeg/data/life-specific/aohs_quant_opt/current/AVES --ys 2048 --xss 256 --yss 256 --cache-mode 2


## avg
python3 ./aohcalc.py --habitats /home/omar/eeg/data/life-small/habitat_maps_q22/restore --elevation-min /home/omar/eeg/data/life-small/elevation-min-1k-int32-shift.tif --elevation-max /home/omar/eeg/data/life-small/elevation-max-1k-int32-shift.tif --crosswalk /home/omar/eeg/data/life-small/crosswalk.csv --speciesdata /home/omar/eeg/data/species-info-specific/species-info-specific/AVES/current/22682298_RESIDENT.geojson --output /home/omar/eeg/data/life-specific/aohs_quant_opt/restore/AVES --ys 2048 --xss 256 --yss 256 --cache-mode 2