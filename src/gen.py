"""Generate a baseline Delta table for one configured experiment state."""
import argparse
import json
import math
import os
import shutil
import sys
import threading
import time

from common import (
    ROOT,
    DeltaTable,
    create_empty_table,
    expected_rows,
    hardware,
    has_checkpoint,
    load_config,
    make_logical_data,
    plan,
    scan,
    table_path,
    write_chunks,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create the baseline Delta table for an experiment state."
    )
    parser.add_argument("--state", required=True, help="One of the configured states")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and recreate an existing baseline table for this state",
    )
    return parser.parse_args()


def data_for_state(cfg, state):
    data = make_logical_data(cfg)
    return data.slice(0, 20_000) if state == "MOCK" else data


def write_with_progress(dt, data, n_files, files_per_commit):
    """Reuse write_chunks while reporting completed-file milestones every 10%."""
    result, failure = [], []
    table_dir = dt.table_uri.replace("file://", "").rstrip("/")
    started = time.perf_counter()

    def run_write():
        try:
            result.append(write_chunks(dt, data, n_files, files_per_commit))
        except Exception as exc:  # Surface worker failures on the main thread.
            failure.append(exc)

    worker = threading.Thread(target=run_write)
    worker.start()
    milestones = list(range(10, 101, 10))
    next_milestone = 0

    while worker.is_alive():
        completed = len([name for name in os.listdir(table_dir) if name.endswith(".parquet")])
        percent = completed * 100 / n_files
        while next_milestone < len(milestones) and percent >= milestones[next_milestone]:
            elapsed = time.perf_counter() - started
            rate = completed / elapsed if elapsed else 0.0
            print(
                f"{milestones[next_milestone]}% complete: {completed}/{n_files} files "
                f"({rate:.1f} files/s)",
                flush=True,
            )
            next_milestone += 1
        worker.join(0.2)

    if failure:
        raise failure[0]
    elapsed = time.perf_counter() - started
    print(f"100% complete: {n_files}/{n_files} files ({n_files / elapsed:.1f} files/s)")
    return result[0]


def verify_table(path, cfg, state, data, expected):
    n_files = cfg["states"][state]
    files_per_commit = cfg["files_per_commit"]
    table = DeltaTable(path)

    actual_files = len(table.file_uris())
    if actual_files != n_files:
        raise RuntimeError(f"Expected {n_files} data files, found {actual_files}.")

    # Delta versions start at 0.  One initial commit plus N write commits ends at version N.
    expected_version = math.ceil(n_files / files_per_commit)
    if table.version() != expected_version:
        raise RuntimeError(
            f"Expected table version {expected_version}, found {table.version()}."
        )

    if has_checkpoint(path):
        raise RuntimeError("Baseline unexpectedly contains a checkpoint.")

    actual_rows = table.to_pyarrow_table().num_rows
    if actual_rows != data.num_rows:
        raise RuntimeError(f"Expected {data.num_rows} rows, found {actual_rows}.")

    selected, _, _, _ = plan(path, cfg["queries"]["q_main"])
    q_main_rows, _ = scan(selected, cfg["queries"]["q_main"])
    if q_main_rows != expected["q_main"]:
        raise RuntimeError(
            f"q_main correctness check failed: expected {expected['q_main']}, got {q_main_rows}."
        )

    return actual_rows


def main():
    args = parse_args()
    cfg = load_config()
    if args.state not in cfg["states"]:
        choices = ", ".join(cfg["states"])
        raise SystemExit(f"Unknown state {args.state!r}. Choose one of: {choices}.")

    state = args.state
    path = table_path(cfg, state, "baseline")
    if os.path.exists(path):
        if not args.force:
            raise SystemExit(
                f"{path} already exists. Re-run with --force to delete and recreate only this baseline table."
            )
        shutil.rmtree(path)

    data = data_for_state(cfg, state)
    expected = {name: expected_rows(data, query) for name, query in cfg["queries"].items()}
    n_files = cfg["states"][state]

    print(f"Generating {state}: {data.num_rows:,} rows across {n_files:,} files.")
    started = time.perf_counter()
    dt = create_empty_table(path)
    bytes_written = write_with_progress(dt, data, n_files, cfg["files_per_commit"])
    gen_time_s = time.perf_counter() - started
    actual_rows = verify_table(path, cfg, state, data, expected)

    os.makedirs(os.path.join(ROOT, cfg["paths"]["results"]), exist_ok=True)
    output_path = os.path.join(ROOT, cfg["paths"]["results"], f"state_{state}.json")
    record = {
        "state": state,
        "n_files": n_files,
        "n_commits": math.ceil(n_files / cfg["files_per_commit"]),
        "n_rows": actual_rows,
        "gen_time_s": gen_time_s,
        "bytes_written": bytes_written,
        "has_checkpoint": has_checkpoint(path),
        "expected_rows": expected,
        "hardware": hardware(),
    }
    with open(output_path, "w") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")

    print(f"Verified {state}; wrote {output_path}")
    print(f"Generation time: {gen_time_s:.2f}s; data written: {bytes_written:,} bytes")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
