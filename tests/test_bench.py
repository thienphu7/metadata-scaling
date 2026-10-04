"""Contract checks; synthetic timings here are test fixtures, never research results."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import bench


def measurement(rows=7):
    return {"t_load": 0.02, "t_prune": 0.01, "t_plan": 0.03,
            "t_scan": 0.04, "n_files_total": 20, "files_selected": 2, "rows": rows}


class BenchmarkContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cfg = {"seed": 42, "n_rows": 1000000, "states": {"MOCK": 20},
                    "variants": ["baseline", "opt_a_checkpoint"],
                    "queries": {"q_main": {"column": "customer_id", "low": 1000, "high": 1050}},
                    "paths": {"tables": "data/tables", "results": "results"}}
        self.manifest = {"state": "MOCK", "variants": self.cfg["variants"],
                         "queries": self.cfg["queries"], "runs": 2, "config": self.cfg,
                         "expected_rows": {"q_main": 7}, "hardware": "TEST"}

    def run_fixture(self, stream, done=None):
        bench.run_benchmark(self.cfg, "MOCK", self.cfg["variants"], ["q_main"], 2,
                            {"q_main": 7}, stream, set() if done is None else done, "TEST")

    def read_rows(self, path):
        with path.open(newline="") as stream:
            return list(csv.DictReader(stream))

    def test_measurement_uses_shared_plan_scan_and_sums_timings(self):
        with patch.object(bench, "plan", return_value=(["a", "b"], 20, 0.02, 0.01)) as planner, \
             patch.object(bench, "scan", return_value=(7, 0.04)) as scanner:
            result = bench.measure_once(self.cfg, "MOCK", "baseline", "q_main")
        self.assertEqual(result, measurement())
        planner.assert_called_once()
        scanner.assert_called_once_with(["a", "b"], self.cfg["queries"]["q_main"])

    def test_real_subprocess_worker_emits_only_one_json_line(self):
        # Run the actual worker code with an isolated shared-helper fixture.
        source = Path(bench.__file__)
        worker = self.root / "bench.py"
        shutil.copyfile(source, worker)
        (self.root / "common.py").write_text(
            "ROOT = '.'\n"
            "def load_config():\n"
            "    return {'states': {'MOCK': 20}, 'variants': ['baseline'], "
            "'queries': {'q_main': {'column': 'x'}}, 'paths': {}}\n"
            "def table_path(*args): return '/fixture'\n"
            "def plan(*args): return ['a', 'b'], 20, 0.02, 0.01\n"
            "def scan(*args): return 7, 0.04\n"
            "def hardware(): return 'TEST'\n"
            "def has_checkpoint(*args): return False\n"
        )
        with patch.object(bench, "__file__", str(worker)):
            self.assertEqual(bench.measure_cold("MOCK", "baseline", "q_main"), measurement())

    def test_round_robin_and_one_warmup_per_pair(self):
        calls = []

        def cold(state, variant, query):
            calls.append(("cold", variant))
            return measurement()

        def warm(cfg, state, variant, query):
            calls.append(("warm", variant))
            return measurement()

        path = self.root / "results_MOCK.csv"
        with path.open("w+", newline="") as stream, redirect_stderr(io.StringIO()), \
             patch.object(bench, "measure_cold", side_effect=cold), \
             patch.object(bench, "measure_once", side_effect=warm):
            csv.DictWriter(stream, fieldnames=bench.CSV_COLUMNS).writeheader()
            self.run_fixture(stream)
        self.assertEqual(calls[:4], [("cold", name) for name in self.cfg["variants"]] * 2)
        self.assertEqual(calls[4:], [("warm", name) for name in self.cfg["variants"]] * 3)
        rows = self.read_rows(path)
        self.assertEqual(len(rows), 8)
        self.assertEqual([(row["mode"], int(row["run"]), row["variant"]) for row in rows],
                         [(mode, run, variant) for mode in bench.MODES for run in range(2)
                          for variant in self.cfg["variants"]])

    def test_mismatch_is_persisted_and_stops_before_next_measurement(self):
        path = self.root / "results_MOCK.csv"
        stderr = io.StringIO()
        with path.open("w+", newline="") as stream, redirect_stderr(stderr), \
             patch.object(bench, "measure_cold", return_value=measurement(8)) as cold:
            csv.DictWriter(stream, fieldnames=bench.CSV_COLUMNS).writeheader()
            with self.assertRaises(bench.BenchmarkError):
                self.run_fixture(stream)
        self.assertEqual(cold.call_count, 1)
        rows = self.read_rows(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["rows"], rows[0]["expected_rows"]), ("8", "7"))
        self.assertIn("ROWS MISMATCH", stderr.getvalue())

    def test_interrupted_session_resumes_missing_rows_without_duplicates(self):
        path = self.root / "results_MOCK.csv"
        with bench.locked_csv(path) as stream, redirect_stderr(io.StringIO()), \
             patch.object(bench, "measure_cold", side_effect=[measurement(), KeyboardInterrupt()]):
            done = bench.prepare_output(stream, path, self.manifest, False)
            with self.assertRaises(KeyboardInterrupt):
                self.run_fixture(stream, done)
        self.assertEqual(len(self.read_rows(path)), 1)
        with bench.locked_csv(path) as stream, redirect_stderr(io.StringIO()), \
             patch.object(bench, "measure_cold", return_value=measurement()) as cold, \
             patch.object(bench, "measure_once", return_value=measurement()) as warm:
            done = bench.prepare_output(stream, path, self.manifest, True)
            self.run_fixture(stream, done)
        rows = self.read_rows(path)
        self.assertEqual(len(rows), 8)
        self.assertEqual(cold.call_count, 3)
        self.assertEqual(warm.call_count, 6)
        self.assertEqual(len({(row["mode"], row["variant"], row["query"], row["run"]) for row in rows}), 8)

    def test_resume_rejects_changed_method_and_plain_rerun(self):
        path = self.root / "results_MOCK.csv"
        with bench.locked_csv(path) as stream:
            bench.prepare_output(stream, path, self.manifest, False)
        with bench.locked_csv(path) as stream:
            with self.assertRaises(bench.BenchmarkError):
                bench.prepare_output(stream, path, self.manifest, False)
        with bench.locked_csv(path) as stream:
            with self.assertRaises(bench.BenchmarkError):
                bench.prepare_output(stream, path, {**self.manifest, "runs": 3}, True)

    def test_preflight_requires_independent_answers_and_checkpoint_state(self):
        state_path = self.root / "results" / "state_MOCK.json"
        state_path.parent.mkdir()
        metadata = {"state": "MOCK", "n_files": 20, "n_rows": 20000,
                    "has_checkpoint": False, "expected_rows": {"q_main": 7}}
        state_path.write_text(json.dumps(metadata))
        for variant in self.cfg["variants"]:
            (self.root / "data/tables/MOCK" / variant / "_delta_log").mkdir(parents=True)
        path_builder = lambda cfg, state, variant: str(self.root / "data/tables" / state / variant)
        with patch.object(bench, "ROOT", str(self.root)), \
             patch.object(bench, "table_path", side_effect=path_builder), \
             patch.object(bench, "has_checkpoint", side_effect=lambda path: "opt_a_checkpoint" in path):
            self.assertEqual(bench.preflight(self.cfg, "MOCK", self.cfg["variants"], ["q_main"]), {"q_main": 7})
            metadata["expected_rows"] = {}
            state_path.write_text(json.dumps(metadata))
            with self.assertRaises(bench.BenchmarkError):
                bench.preflight(self.cfg, "MOCK", self.cfg["variants"], ["q_main"])
            metadata["expected_rows"] = {"q_main": 7}
            state_path.write_text(json.dumps(metadata))
            with patch.object(bench, "has_checkpoint", return_value=True):
                with self.assertRaises(bench.BenchmarkError):
                    bench.preflight(self.cfg, "MOCK", self.cfg["variants"], ["q_main"])

    def test_package_versions_must_match_requirements(self):
        (self.root / "requirements.txt").write_text("pyarrow==25.0.1\n")
        with patch.object(bench, "ROOT", str(self.root)), \
             patch.object(bench.importlib.metadata, "version", return_value="24.0.0"):
            with self.assertRaises(bench.BenchmarkError):
                bench.environment_versions()

    def test_rejects_nan_and_invalid_plan_sum(self):
        with self.assertRaises(bench.BenchmarkError):
            bench.validate_measurement({**measurement(), "t_plan": float("nan")})
        with self.assertRaises(bench.BenchmarkError):
            bench.validate_measurement({**measurement(), "t_plan": 1.0})


if __name__ == "__main__":
    unittest.main()
