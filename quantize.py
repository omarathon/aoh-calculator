import os
import numpy as np
import rasterio
from pathlib import Path

# Parameters
INPUT_DIR = "habitat_maps"       # change this to your source dir
OUTPUT_DIR = "habitat_maps_q22"  # change this to your destination dir
SCALE = 2**22

def quantize_raster(infile, outfile):
    with rasterio.open(infile) as src:
        profile = src.profile.copy()
        profile.update(
            dtype=rasterio.int32,
            compress="LZW",
            tiled=False   # match your row-wise compression
        )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(outfile), exist_ok=True)

        with rasterio.open(outfile, "w", **profile) as dst:
            for i in range(1, src.count + 1):
                data = src.read(i, masked=False)
                quantized = np.rint(data * SCALE).astype(np.int32)
                dst.write(quantized, i)

def main():
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)

    for tif_path in input_path.rglob("*.tif"):
        # Relative path inside input_dir
        rel_path = tif_path.relative_to(input_path)

        # Add suffix _q22 before extension
        out_filename = tif_path.stem + "_q22.tif"

        # Build full output path
        out_path = output_path / rel_path.parent / out_filename

        print(f"Processing {tif_path} → {out_path}")
        quantize_raster(str(tif_path), str(out_path))

if __name__ == "__main__":
    main()
