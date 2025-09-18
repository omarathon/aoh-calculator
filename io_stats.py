import re
import statistics

log_file = "trace_io.txt"

run_pattern = re.compile(r"^TAXA=.*")
total_pattern = re.compile(r"total time (\S+) main calculation (\S+)")
io_pattern = re.compile(r"IO (\S+)")

runs = []
current_io_before = 0.0
current_io_main = 0.0
in_main_calc = False
current_total_time = None
current_main_time = None

with open(log_file) as f:
    for line in f:
        line = line.strip()

        # detect new run
        if run_pattern.match(line):
            # reset state
            current_io_before = 0.0
            current_io_main = 0.0
            in_main_calc = False
            current_total_time = None
            current_main_time = None
            continue

        # detect entering main calculation
        if line.startswith("doing main calculation"):
            in_main_calc = True
            continue

        # detect IO lines
        m = io_pattern.search(line)
        if m:
            val = float(m.group(1))
            if in_main_calc:
                current_io_main += val
            else:
                current_io_before += val
            continue

        # detect run end
        m = total_pattern.search(line)
        if m:
            current_total_time = float(m.group(1))
            current_main_time = float(m.group(2))
            runs.append({
                "total_time": current_total_time,
                "main_time": current_main_time,
                "io_before": current_io_before,
                "io_main": current_io_main
            })

# Now compute stats per run
results = []
io_ratios = []
io_main_ratios = []
for run in runs:
    total_io = run["io_before"] + run["io_main"]
    ratio_total = total_io / run["total_time"] if run["total_time"] > 0 else 0
    ratio_main = run["io_main"] / run["main_time"] if run["main_time"] > 0 else 0
    results.append({
        **run,
        "total_io": total_io,
        "ratio_total": ratio_total,
        "ratio_main": ratio_main
    })
    io_ratios.append(ratio_total)
    io_main_ratios.append(ratio_main)

# Aggregate stats
def summary_stats(values):
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0
    }

agg = {
    "ratio_total": summary_stats(io_ratios),
    "ratio_main": summary_stats(io_main_ratios)
}

# Show results
import pprint
pprint.pprint(results)
print("\nAggregate stats:")
pprint.pprint(agg)
