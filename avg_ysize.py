#!/usr/bin/env python3
import re
import sys
import statistics

def analyze_log(path):
    values = []
    pattern = re.compile(r"TRACE ysize (\d+)")
    with open(path) as f:
        for line in f:
            m = pattern.search(line)
            if m:
                values.append(int(m.group(1)))

    if not values:
        print("No ysize entries found.")
        return

    mean = statistics.mean(values)
    stdev = statistics.stdev(values)  # sample standard deviation
    print(f"Count: {len(values)}")
    print(f"Mean: {mean:.2f}")
    print(f"Sample StdDev: {stdev:.2f}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <logfile>")
        sys.exit(1)
    analyze_log(sys.argv[1])