#!/usr/bin/env python3
"""Offline output sanity checker. Usage: python3 check_outputs.py <output_dir> [expected_file ...]

Prints, for every CSV/JSON in the directory: existence, columns/keys, row count,
NaN/inf presence, and non-JSON-safe values. Exit code 1 if any problem is found.
No network, no third-party imports beyond pandas if available.
"""
import json, math, os, sys

def check_json(path, problems):
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        problems.append(f"{path}: invalid JSON ({e})"); return
    def walk(x, trail):
        if isinstance(x, dict):
            for k, v in x.items(): walk(v, trail + [k])
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, trail + [str(i)])
        elif isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            problems.append(f"{path}: NaN/inf at {'.'.join(trail)}")
    walk(data, [])
    keys = list(data.keys()) if isinstance(data, dict) else f"<{type(data).__name__}>"
    print(f"  {os.path.basename(path)}: keys={keys}")

def check_csv(path, problems):
    try:
        import pandas as pd
        df = pd.read_csv(path)
    except ImportError:
        with open(path) as f:
            header = f.readline().strip().split(",")
            n = sum(1 for _ in f)
        print(f"  {os.path.basename(path)}: columns={header} rows={n}")
        if n == 0: problems.append(f"{path}: zero data rows")
        return
    except Exception as e:
        problems.append(f"{path}: unreadable CSV ({e})"); return
    print(f"  {os.path.basename(path)}: columns={list(df.columns)} rows={len(df)}")
    if len(df) == 0: problems.append(f"{path}: zero data rows")
    num = df.select_dtypes("number")
    if num.isna().any().any():
        problems.append(f"{path}: NaN in columns {list(num.columns[num.isna().any()])}")
    if ((num == float('inf')) | (num == float('-inf'))).any().any():
        problems.append(f"{path}: inf values present")

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    out = sys.argv[1]; expected = sys.argv[2:]
    problems = []
    if not os.path.isdir(out):
        print(f"output dir missing: {out}"); sys.exit(1)
    present = sorted(os.listdir(out))
    print(f"files in {out}: {present}")
    for name in expected:
        if name not in present: problems.append(f"missing expected file: {name}")
    for name in present:
        p = os.path.join(out, name)
        if os.path.getsize(p) == 0: problems.append(f"{name}: empty file")
        elif name.endswith(".json"): check_json(p, problems)
        elif name.endswith(".csv"): check_csv(p, problems)
    if problems:
        print("\nPROBLEMS:"); [print(" -", x) for x in problems]; sys.exit(1)
    print("\nOK: no structural problems found")

if __name__ == "__main__":
    main()
