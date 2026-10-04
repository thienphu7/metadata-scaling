"""Measure the shared planning/scan proxy without timing Python startup.

Cold means a fresh Python process, not an empty operating-system page cache.
All timings come from common.plan/common.scan. Diagnostics go to stderr;
the internal --one worker writes exactly one JSON object to stdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator, TextIO

from common import ROOT, hardware, has_checkpoint, load_config, plan, scan, table_path

CSV_COLUMNS = [
    "state", "variant", "query", "mode", "run", "t_load", "t_prune",
    "t_plan", "t_scan", "n_files_total", "files_selected", "rows",
    "expected_rows", "hardware",
]
MEASUREMENT_COLUMNS = [
    "t_load", "t_prune", "t_plan", "t_scan", "n_files_total",
    "files_selected", "rows",
]
MODES = ("cold", "warm")
PROTOCOL_VERSION = 1


class BenchmarkError(RuntimeError):
    """Invalid inputs or a measurement that must not enter the analysis."""


def positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--state", help="MOCK, S1, S2, S3 or S4")
    group.add_argument("--one", nargs=3, metavar=("STATE", "VARIANT", "QUERY"),
                       help=argparse.SUPPRESS)
    parser.add_argument("--variants", nargs="+", help="subset of configured variants")
    parser.add_argument("--queries", nargs="+", help="subset of configured queries")
    parser.add_argument("--runs", type=positive_int, help="default: config n_runs")
    parser.add_argument("--check-only", action="store_true", help="validate inputs without measuring")
    parser.add_argument("--resume", action="store_true",
                        help="append only missing measurements from an interrupted identical run")
    return parser.parse_args(argv)


def select_names(requested: list[str] | None, available: Any, label: str) -> list[str]:
    names = list(available) if requested is None else requested
    if not names or len(set(names)) != len(names):
        raise BenchmarkError(f"{label} must be nonempty and have no duplicates")
    unknown = set(names) - set(available)
    if unknown:
        raise BenchmarkError(f"Unknown {label}: {sorted(unknown)}")
    return names


def measure_once(cfg: dict[str, Any], state: str, variant: str, query: str) -> dict[str, Any]:
    files, n_files, t_load, t_prune = plan(table_path(cfg, state, variant), cfg["queries"][query])
    rows, t_scan = scan(files, cfg["queries"][query])
    return {
        "t_load": t_load, "t_prune": t_prune, "t_plan": t_load + t_prune,
        "t_scan": t_scan, "n_files_total": n_files,
        "files_selected": len(files), "rows": rows,
    }


def validate_measurement(value: dict[str, Any]) -> None:
    if set(value) != set(MEASUREMENT_COLUMNS):
        raise BenchmarkError("Worker returned an unexpected measurement schema")
    for key in ("t_load", "t_prune", "t_plan", "t_scan"):
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0:
            raise BenchmarkError(f"Invalid {key}: {number!r}")
    for key in ("n_files_total", "files_selected", "rows"):
        number = value[key]
        if type(number) is not int or number < 0:
            raise BenchmarkError(f"Invalid {key}: {number!r}")
    if value["files_selected"] > value["n_files_total"]:
        raise BenchmarkError("files_selected exceeds n_files_total")
    if not math.isclose(value["t_plan"], value["t_load"] + value["t_prune"], rel_tol=1e-9, abs_tol=1e-12):
        raise BenchmarkError("t_plan does not equal t_load + t_prune")


def measure_cold(state: str, variant: str, query: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--one", state, variant, query],
        capture_output=True, text=True, check=False,
    )
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr, flush=True)
    if completed.returncode:
        raise BenchmarkError(f"Cold worker failed ({completed.returncode}): {state}/{variant}/{query}")
    lines = completed.stdout.strip().splitlines()
    if len(lines) != 1:
        raise BenchmarkError("Cold worker must emit exactly one JSON line")
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise BenchmarkError("Cold worker emitted invalid JSON") from exc
    if not isinstance(result, dict):
        raise BenchmarkError("Cold worker JSON must be an object")
    validate_measurement(result)
    return result


def check_rows(result: dict[str, Any], expected: int, label: str) -> None:
    if result["rows"] != expected:
        message = f"ROWS MISMATCH {label}: rows={result['rows']}, expected_rows={expected}. Stop and notify the team."
        print(f"\033[31m{message}\033[0m", file=sys.stderr, flush=True)
        raise BenchmarkError(message)


def preflight(cfg: dict[str, Any], state: str, variants: list[str], queries: list[str]) -> dict[str, int]:
    state_file = Path(ROOT) / cfg["paths"]["results"] / f"state_{state}.json"
    if not state_file.is_file():
        owner = "make_mock.py (Phong)" if state == "MOCK" else "gen.py (Hung), run locally for this state"
        raise BenchmarkError(f"Missing {state_file}. Need output from {owner} before benchmarking.")
    try:
        metadata = json.loads(state_file.read_text())
    except json.JSONDecodeError as exc:
        raise BenchmarkError(f"Invalid JSON: {state_file}") from exc
    if not isinstance(metadata, dict):
        raise BenchmarkError(f"State metadata must be a JSON object: {state_file}")
    if metadata.get("state") != state or metadata.get("n_files") != cfg["states"][state]:
        raise BenchmarkError(f"State/file count disagrees with config: {state_file}")
    n_rows = min(20000, cfg["n_rows"]) if state == "MOCK" else cfg["n_rows"]
    if metadata.get("n_rows") != n_rows or metadata.get("has_checkpoint") is not False:
        raise BenchmarkError(f"Invalid baseline n_rows/has_checkpoint: {state_file}")
    answers = metadata.get("expected_rows", {})
    if not isinstance(answers, dict):
        raise BenchmarkError(f"expected_rows must be a JSON object: {state_file}")
    for query in queries:
        if type(answers.get(query)) is not int or not 0 <= answers[query] <= n_rows:
            raise BenchmarkError(f"Missing/invalid independent expected_rows[{query}] in {state_file}")
    for variant in variants:
        path = Path(table_path(cfg, state, variant))
        if not (path / "_delta_log").is_dir():
            owner = "gen.py (Hung)" if variant == "baseline" else "optimize.py (Phu)"
            raise BenchmarkError(f"Missing table {path}. Need {owner} output on this machine.")
        want_checkpoint = variant != "baseline"
        if has_checkpoint(str(path)) != want_checkpoint:
            raise BenchmarkError(f"Checkpoint check failed: {path}; expected checkpoint={want_checkpoint}")
    return {query: answers[query] for query in queries}


def environment_versions() -> dict[str, str]:
    """Enforce the team's pinned packages before starting any measurements."""
    versions: dict[str, str] = {}
    for line in (Path(ROOT) / "requirements.txt").read_text().splitlines():
        requirement = line.split("#", 1)[0].strip()
        if not requirement:
            continue
        name, separator, expected = requirement.partition("==")
        try:
            actual = importlib.metadata.version(name.strip())
        except importlib.metadata.PackageNotFoundError as exc:
            raise BenchmarkError(f"Missing package {name}; use the team environment") from exc
        if separator and actual != expected.strip():
            raise BenchmarkError(f"Package mismatch: {name}=={actual}; requirements specifies {expected.strip()}")
        versions[name] = actual
    return versions


def session_manifest(cfg: dict[str, Any], state: str, variants: list[str], queries: list[str],
                     runs: int, answers: dict[str, int], machine: str, versions: dict[str, str]) -> dict[str, Any]:
    logs = {}
    for variant in variants:
        log_dir = Path(table_path(cfg, state, variant)) / "_delta_log"
        entries = [(entry.name, entry.stat().st_size, entry.stat().st_mtime_ns)
                   for entry in sorted(log_dir.iterdir()) if entry.is_file()]
        logs[variant] = hashlib.sha256(json.dumps(entries).encode()).hexdigest()
    sources = {
        name: hashlib.sha256((Path(ROOT) / "src" / name).read_bytes()).hexdigest()
        for name in ("bench.py", "common.py")
    }
    return {
        "protocol_version": PROTOCOL_VERSION, "state": state, "variants": variants,
        "queries": {name: cfg["queries"][name] for name in queries}, "runs": runs,
        "config": cfg, "expected_rows": answers, "hardware": machine,
        "python": platform.python_version(), "packages": versions, "log_fingerprints": logs,
        "method_sources": sources,
        "cold_definition": "fresh Python process; OS page cache not cleared",
        "warm_definition": "one discarded warm-up per variant/query; reopen DeltaTable every measurement",
    }


@contextmanager
def locked_csv(path: Path) -> Iterator[TextIO]:
    # Advisory lock avoids two local parent processes appending to one CSV.
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", newline="") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BenchmarkError(f"Another benchmark is writing {path}") from exc
        try:
            yield stream
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def durable_flush(stream: TextIO) -> None:
    stream.flush()
    os.fsync(stream.fileno())


def prepare_output(stream: TextIO, path: Path, manifest: dict[str, Any], resume: bool) -> set[tuple[str, str, str, int]]:
    manifest_path = path.with_suffix(".benchmark.json")
    stream.seek(0)
    reader = csv.DictReader(stream)
    done: set[tuple[str, str, str, int]] = set()
    if reader.fieldnames is not None:
        if not resume:
            raise BenchmarkError(f"{path} already exists. Use --resume only for the same interrupted session; no rows overwritten.")
        if reader.fieldnames != CSV_COLUMNS:
            raise BenchmarkError(f"CSV header differs from the agreed schema: {path}")
        if not manifest_path.is_file() or json.loads(manifest_path.read_text()) != manifest:
            raise BenchmarkError("Cannot resume: method, environment, inputs or selected runs changed (or session manifest missing)")
        for row in reader:
            if set(row) != set(CSV_COLUMNS):
                raise BenchmarkError(f"Unexpected extra CSV columns: {path}")
            try:
                key = (row["mode"], row["variant"], row["query"], int(row["run"]))
                result = {name: float(row[name]) if name.startswith("t_") else int(row[name])
                          for name in MEASUREMENT_COLUMNS}
                validate_measurement(result)
                valid = (
                    row["state"] == manifest["state"] and row["hardware"] == manifest["hardware"]
                    and key[0] in MODES and key[1] in manifest["variants"] and key[2] in manifest["queries"]
                    and 0 <= key[3] < manifest["runs"] and key not in done
                    and result["rows"] == int(row["expected_rows"]) == manifest["expected_rows"][key[2]]
                    and result["n_files_total"] == manifest["config"]["states"][manifest["state"]]
                )
            except (ValueError, TypeError, KeyError) as exc:
                raise BenchmarkError(f"Malformed existing CSV row: {path}") from exc
            if not valid:
                raise BenchmarkError(f"Invalid, duplicate or mismatching existing CSV row: {path}")
            done.add(key)
    else:
        # Sidecar records the method; it never contains fabricated measurements.
        temp = manifest_path.with_suffix(".json.tmp")
        with temp.open("w") as manifest_stream:
            json.dump(manifest, manifest_stream, indent=2, allow_nan=False)
            manifest_stream.write("\n")
            durable_flush(manifest_stream)
        temp.replace(manifest_path)
        csv.DictWriter(stream, fieldnames=CSV_COLUMNS).writeheader()
        durable_flush(stream)
    stream.seek(0, os.SEEK_END)
    return done


def run_benchmark(cfg: dict[str, Any], state: str, variants: list[str], queries: list[str],
                  runs: int, answers: dict[str, int], stream: TextIO,
                  done: set[tuple[str, str, str, int]], machine: str) -> None:
    pairs = [(variant, query) for variant in variants for query in queries]
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
    total = len(MODES) * runs * len(pairs)
    durations: dict[tuple[str, str, str], list[float]] = {}
    completed = len(done)

    def validate_counts(result: dict[str, Any], query: str, label: str) -> None:
        check_rows(result, answers[query], label)
        if result["n_files_total"] != cfg["states"][state]:
            raise BenchmarkError(f"Active file count changed: {label}")

    for mode in MODES:
        pending_pairs = [(variant, query) for variant, query in pairs
                         if any((mode, variant, query, run) not in done for run in range(runs))]
        if mode == "warm":
            for variant, query in pending_pairs:
                result = measure_once(cfg, state, variant, query)
                validate_measurement(result)
                try:
                    validate_counts(result, query, f"{state}/{variant}/{query}/warm-up")
                except BenchmarkError:
                    # Warm-up is never mixed with measured rows. Keep failure evidence separately.
                    failure = {"state": state, "variant": variant, "query": query,
                               "mode": "warm-up", "expected_rows": answers[query], **result}
                    print(json.dumps(failure, allow_nan=False), file=sys.stderr, flush=True)
                    raise
        # Run is the outer loop; every round visits all selected variant/query pairs.
        for run in range(runs):
            for variant, query in pairs:
                key = (mode, variant, query, run)
                if key in done:
                    continue
                started = time.perf_counter()
                result = measure_cold(state, variant, query) if mode == "cold" else measure_once(cfg, state, variant, query)
                validate_measurement(result)
                # Persist mismatch evidence BEFORE stopping. Never silently discard it.
                writer.writerow({"state": state, "variant": variant, "query": query,
                                 "mode": mode, "run": run, **result,
                                 "expected_rows": answers[query], "hardware": machine})
                durable_flush(stream)
                validate_counts(result, query, f"{state}/{variant}/{query}/{mode}/run={run}")
                done.add(key)
                completed += 1
                durations.setdefault((mode, variant, query), []).append(time.perf_counter() - started)
                # ETA includes startup and CSV persistence; reported t_plan/t_scan do not.
                all_samples = [sample for samples in durations.values() for sample in samples]
                fallback = sum(all_samples) / len(all_samples)
                remaining = 0.0
                for pending_mode in MODES:
                    for pending_variant, pending_query in pairs:
                        samples = durations.get((pending_mode, pending_variant, pending_query), [])
                        estimate = sum(samples) / len(samples) if samples else fallback
                        count = sum((pending_mode, pending_variant, pending_query, index) not in done for index in range(runs))
                        remaining += estimate * count
                print(f"[{completed}/{total}] {mode} run={run} {variant}/{query} "
                      f"plan={result['t_plan']:.6f}s scan={result['t_scan']:.6f}s "
                      f"files={result['files_selected']}/{result['n_files_total']} "
                      f"ETA ~{remaining / 60:.1f} min (warm-up excluded)", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        cfg = load_config()
        if args.one:
            state, variant, query = args.one
            if state not in cfg["states"]:
                raise BenchmarkError(f"Unknown state: {state}")
            select_names([variant], cfg["variants"], "variants")
            select_names([query], cfg["queries"], "queries")
            result = measure_once(cfg, state, variant, query)
            validate_measurement(result)
            print(json.dumps(result, allow_nan=False), flush=True)
            return 0
        if args.state not in cfg["states"]:
            raise BenchmarkError(f"Unknown state: {args.state}")
        variants = select_names(args.variants, cfg["variants"], "variants")
        queries = select_names(args.queries, cfg["queries"], "queries")
        runs = args.runs if args.runs is not None else cfg["n_runs"]
        if type(runs) is not int or runs < 1:
            raise BenchmarkError("n_runs must be a positive integer")
        if args.state in cfg.get("heldout", []) and runs < 5:
            raise BenchmarkError("Held-out results require at least 5 runs; agree protocol changes with Phong before observing S4")
        versions = environment_versions()
        answers = preflight(cfg, args.state, variants, queries)
        print(f"Preflight OK: {args.state}; {len(variants) * len(queries) * runs * 2} measured rows. "
              "Cold=fresh process, OS cache retained. Warm=reopen DeltaTable each time.", file=sys.stderr, flush=True)
        if args.check_only:
            return 0
        machine = hardware()
        manifest = session_manifest(cfg, args.state, variants, queries, runs, answers, machine, versions)
        path = Path(ROOT) / cfg["paths"]["results"] / f"results_{args.state}.csv"
        with locked_csv(path) as stream:
            done = prepare_output(stream, path, manifest, args.resume)
            run_benchmark(cfg, args.state, variants, queries, runs, answers, stream, done, machine)
        print(f"Finished: {path}", file=sys.stderr, flush=True)
        return 0
    except (BenchmarkError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Benchmark stopped: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; completed CSV rows retained. Resume with the same options and --resume.", file=sys.stderr, flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
