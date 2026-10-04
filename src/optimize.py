"""Build and validate optimized Delta-table variants from a baseline table.

Examples:
    python src/optimize.py --state MOCK --force
    python src/optimize.py --state S3 --variant opt_b_sorted

The optimizer deliberately never runs VACUUM.  After an overwrite, obsolete
Parquet files may remain on disk, but they are no longer active in the Delta log.
"""
import argparse
import csv
import json
import os
import shutil
import sys
import time

from common import *  # Shared experiment contract and tested Delta helpers.


COST_COLUMNS = [
    "state", "variant", "op", "wall_time_s", "bytes_rewritten",
    "n_files_before", "n_files_after", "n_log_files_before",
    "n_log_files_after", "hardware",
]


def _log_file_count(path):
    return len(os.listdir(os.path.join(path, "_delta_log")))


def _active_file_count(path):
    return len(DeltaTable(path).file_uris())


def _expected_for_state(cfg, state, baseline_path):
    """Load generated expectations, falling back to the deterministic source data.

    MOCK intentionally contains only the first 20,000 logical rows.  If no mock
    state JSON exists, derive its expected values from that actual baseline so the
    smoke test validates the table it is testing rather than the full S1-S4 data.
    """
    state_file = os.path.join(ROOT, cfg["paths"]["results"], f"state_{state}.json")
    if os.path.exists(state_file):
        with open(state_file, encoding="utf-8") as f:
            payload = json.load(f)
        values = payload.get("expected_rows")
        if not isinstance(values, dict):
            raise ValueError(f"{state_file} has no expected_rows object")
        missing = set(cfg["queries"]) - set(values)
        if missing:
            raise ValueError(f"{state_file} is missing expected rows for {sorted(missing)}")
        n_rows = payload.get("n_rows")
        if not isinstance(n_rows, int):
            raise ValueError(f"{state_file} has no integer n_rows")
        return values, n_rows

    data = DeltaTable(baseline_path).to_pyarrow_table() if state == "MOCK" else make_logical_data(cfg)
    return (
        {name: expected_rows(data, query) for name, query in cfg["queries"].items()},
        data.num_rows,
    )


def _validate(cfg, path, n_files_before, expected, expected_n_rows):
    n_files_after = _active_file_count(path)
    if n_files_after != n_files_before:
        raise RuntimeError(f"active file count changed: before={n_files_before}, after={n_files_after}")

    total_rows = DeltaTable(path).to_pyarrow_table().num_rows
    if total_rows != expected_n_rows:
        raise RuntimeError(f"total row mismatch: expected={expected_n_rows}, actual={total_rows}")

    if not has_checkpoint(path):
        raise RuntimeError("checkpoint was not created")

    for name, query in cfg["queries"].items():
        selected, _, _, _ = plan(path, query)
        actual_rows, _ = scan(selected, query)
        if actual_rows != expected[name]:
            raise RuntimeError(
                f"{name} row mismatch: expected={expected[name]}, actual={actual_rows}"
            )


def _write_cost(cfg, row):
    results_dir = os.path.join(ROOT, cfg["paths"]["results"])
    os.makedirs(results_dir, exist_ok=True)
    output = os.path.join(results_dir, f"costs_{row['state']}.csv")
    write_header = not os.path.exists(output) or os.path.getsize(output) == 0
    with open(output, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COST_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def optimize_variant(cfg, state, variant, force):
    baseline = table_path(cfg, state, "baseline")
    target = table_path(cfg, state, variant)
    if not os.path.isdir(baseline):
        raise FileNotFoundError(f"baseline table does not exist: {baseline}")
    if os.path.exists(target):
        if not force:
            raise FileExistsError(f"target exists: {target}; rerun with --force to replace it")
        shutil.rmtree(target)

    # Copying is intentionally outside the optimization timer.
    shutil.copytree(baseline, target)
    n_files_before = _active_file_count(target)
    n_log_files_before = _log_file_count(target)
    expected, expected_n_rows = _expected_for_state(cfg, state, baseline)

    started = time.perf_counter()
    bytes_rewritten = 0
    if variant == "opt_a_checkpoint":
        DeltaTable(target).create_checkpoint()
        operation = "checkpoint"
    elif variant == "opt_b_sorted":
        dt = DeltaTable(target)
        data_sorted = dt.to_pyarrow_table().sort_by("customer_id")
        bytes_rewritten = write_chunks(
            dt, data_sorted, n_files_before, files_per_commit=n_files_before,
            mode="overwrite", prefix="sorted",
        )
        DeltaTable(target).create_checkpoint()
        operation = "sort_rewrite_checkpoint"
    else:
        raise ValueError(f"unsupported optimization variant: {variant}")
    wall_time_s = time.perf_counter() - started

    _validate(cfg, target, n_files_before, expected, expected_n_rows)
    row = {
        "state": state,
        "variant": variant,
        "op": operation,
        "wall_time_s": wall_time_s,
        "bytes_rewritten": bytes_rewritten,
        "n_files_before": n_files_before,
        "n_files_after": _active_file_count(target),
        "n_log_files_before": n_log_files_before,
        "n_log_files_after": _log_file_count(target),
        "hardware": hardware(),
    }
    _write_cost(cfg, row)
    print(json.dumps(row, indent=2))


def parse_args():
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, choices=cfg["states"].keys())
    parser.add_argument(
        "--variant", choices=[v for v in cfg["variants"] if v != "baseline"],
        help="Optimize only this variant (default: all non-baseline variants).",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing target variant.")
    return parser.parse_args(), cfg


def main():
    args, cfg = parse_args()
    variants = [args.variant] if args.variant else [v for v in cfg["variants"] if v != "baseline"]
    for variant in variants:
        optimize_variant(cfg, args.state, variant, args.force)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
