from osgeo import gdal
import numpy as np
import sys

def compute_stats(arr):
    """Return mean, min, max, std_dev for a NumPy array as floats."""
    return {
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "std_dev": float(np.std(arr))
    }

def compute_all_stats(file1, file2):
    # Open datasets
    ds1 = gdal.Open(file1, gdal.GA_ReadOnly)
    ds2 = gdal.Open(file2, gdal.GA_ReadOnly)

    if ds1 is None or ds2 is None:
        raise RuntimeError("Could not open one of the files.")

    # Check dimensions
    if (ds1.RasterXSize != ds2.RasterXSize or
        ds1.RasterYSize != ds2.RasterYSize or
        ds1.RasterCount   != ds2.RasterCount):
        raise ValueError("Input rasters do not have the same dimensions or band count.")

    # Read first band (can be extended to more bands if needed)
    band1 = ds1.GetRasterBand(1).ReadAsArray().astype(np.float32)
    band2 = ds2.GetRasterBand(1).ReadAsArray().astype(np.float32)

    # Compute absolute residuals
    residuals = np.abs(band1 - band2)

    # Collect stats
    return {
        "residuals": compute_stats(residuals),
        "raster1": compute_stats(band1),
        "raster2": compute_stats(band2)
    }

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python residual_stats.py file1.tif file2.tif")
        sys.exit(1)

    file1, file2 = sys.argv[1], sys.argv[2]
    stats = compute_all_stats(file1, file2)

    print("Statistics (scientific notation):")
    print("\nResiduals:")
    for k, v in stats["residuals"].items():
        print(f"{k:>7}: {v:.6e}")

    print("\nRaster 1 values:")
    for k, v in stats["raster1"].items():
        print(f"{k:>7}: {v:.6e}")

    print("\nRaster 2 values:")
    for k, v in stats["raster2"].items():
        print(f"{k:>7}: {v:.6e}")