"""Checkpoint-70 guard: verify results/costs/state files follow the contract.
Usage: python src/check_results.py [--fake]   (exit code 1 if any check fails)"""
import argparse, csv, glob, json, os, sys
from collections import Counter
from common import ROOT, load_config

RES_COLS = ["state","variant","query","mode","run","t_load","t_prune","t_plan","t_scan",
            "n_files_total","files_selected","rows","expected_rows","hardware"]
COST_COLS = ["state","variant","op","wall_time_s","bytes_rewritten","n_files_before","n_files_after",
             "n_log_files_before","n_log_files_after","hardware"]

def read_csv(fp):
    with open(fp, newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)

def check_results(fp, cfg, errs, use_state_expectations=True):
    name = os.path.basename(fp)
    cols, rows = read_csv(fp)
    if cols != RES_COLS:
        errs.append(f"{name}: header {cols} != {RES_COLS}"); return
    states = {r["state"] for r in rows}
    exp_json = {}
    if use_state_expectations:
        for s in states:
            sj = os.path.join(ROOT, cfg["paths"]["results"], f"state_{s}.json")
            if os.path.exists(sj):
                with open(sj) as f:
                    exp_json[s] = json.load(f)["expected_rows"]
    bad_rows = [r for r in rows if r["rows"] != r["expected_rows"]]
    for r in bad_rows[:5]:
        errs.append(f"{name}: rows {r['rows']} != expected {r['expected_rows']} "
                    f"({r['state']} {r['variant']} {r['query']} {r['mode']} run={r['run']})")
    if len(bad_rows) > 5:
        errs.append(f"{name}: ... {len(bad_rows) - 5} more rows != expected_rows")
    for r in rows:
        e = exp_json.get(r["state"], {}).get(r["query"])
        if e is not None and int(r["expected_rows"]) != e:
            errs.append(f"{name}: expected_rows {r['expected_rows']} != state_{r['state']}.json {e} ({r['query']})")
            break
    if any(not r["hardware"] for r in rows):
        errs.append(f"{name}: empty hardware column")
    hws = {r["hardware"] for r in rows}
    if len(hws) > 1:
        errs.append(f"{name}: multiple hardware values in one file: {sorted(hws)}")
    combos = Counter((r["state"], r["variant"], r["query"], r["mode"]) for r in rows)
    for k, n in combos.items():
        if n != cfg["n_runs"]:
            errs.append(f"{name}: {k} has {n} runs, expected {cfg['n_runs']}")
    for s in states:
        for v in cfg["variants"]:
            for q in cfg["queries"]:
                for m in ["cold", "warm"]:
                    if (s, v, q, m) not in combos:
                        errs.append(f"{name}: missing {s} {v} {q} {m}")
    print(f"{name}: {len(rows)} rows, states={sorted(states)}, hardware={sorted(hws)}")

def check_costs(fp, errs):
    name = os.path.basename(fp)
    cols, rows = read_csv(fp)
    if cols != COST_COLS:
        errs.append(f"{name}: header {cols} != {COST_COLS}"); return
    if any(not r["hardware"] for r in rows):
        errs.append(f"{name}: empty hardware column")
    print(f"{name}: {len(rows)} rows")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="check results_fake.csv only (self-test)")
    args = ap.parse_args()
    cfg = load_config()
    rdir = os.path.join(ROOT, cfg["paths"]["results"])
    errs = []
    if args.fake:
        res = [os.path.join(rdir, "results_fake.csv")]
        costs = []
    else:
        res = sorted(glob.glob(os.path.join(rdir, "results_S*.csv")))
        costs = sorted(glob.glob(os.path.join(rdir, "costs_S*.csv")))
        if not res:
            errs.append("no results/results_S*.csv yet")
    for fp in res:
        check_results(fp, cfg, errs, use_state_expectations=not args.fake)
    for fp in costs:
        check_costs(fp, errs)
    if errs:
        print("\nFAIL:"); [print("  -", e) for e in errs]; sys.exit(1)
    print("\nOK")

if __name__ == "__main__":
    main()
