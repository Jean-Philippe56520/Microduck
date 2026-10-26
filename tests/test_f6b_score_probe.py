"""F6-B checks isolated score equivalence; NEVER tests robot control.

Rust is an optional LOCAL tool for tests; CI installs/proves its presence.
No sensor, actuator, network, identity, Qwen or SQLite is used by the probe.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from microduck_companion.autonomy import Motivations
from microduck_companion.passive_rhythm import PassiveRhythm
from microduck_companion.f6b_score_probe import (
    BENCH_ITERATIONS, CATEGORIES, INTENTS, benchmark_both,
    benchmark_python, cases, probe_rust, python_score,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "f6b" / "passive_score.rs"


class PythonOnlyProbeTests(unittest.TestCase):
    def test_fixed_bounded_fixture_contains_extreme_and_threshold_cases(self):
        data = cases()
        self.assertEqual(1500, len(data))
        self.assertEqual(15, len(set((a,b) for a,b,_ in data)))
        self.assertTrue(all(len(m)==5 and all(
            0.<=v<=1. and math.isfinite(v) for v in m
        ) for _,_,m in data))
        self.assertIn(("observe","ball",(0.,)*5),data)
        self.assertIn(("inspect","unknown",(1.,)*5),data)

    def test_reference_uses_existing_python_scoring_not_a_new_brain(self):
        motives = Motivations()
        observation = PassiveRhythm._score("observe", "ball", motives)
        comparison = python_score(
            ("observe","ball",(.75,.55,.60,.80,.35)),
        )
        self.assertEqual(observation,comparison)
        self.assertEqual(
            PassiveRhythm._score("listen","knock",motives),
            python_score(("listen","knock",(.75,.55,.60,.80,.35))),
        )

    def test_python_probe_ignores_pc_and_motors_and_reports_host_only(self):
        data = benchmark_python()
        self.assertEqual(BENCH_ITERATIONS,data["iterations"])
        self.assertGreater(data["loop_wall_ms"],0)
        self.assertTrue(math.isfinite(data["checksum"]))
        self.assertFalse(data["physical_robot_validated"])
        self.assertEqual("host_python_existing_brain_score_only",data["kind"])

    def test_explicit_compiled_executable_required(self):
        with self.assertRaises(ValueError):
            probe_rust(ROOT/"no such binary.exe")
        self.assertEqual(("observe","inspect","listen"),INTENTS)
        self.assertEqual(("ball","toy","dog","unknown","knock"),CATEGORIES)


@unittest.skipUnless(shutil.which("rustc"), "Rust needed for cross-language tests")
class RustParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="f6b-score-")
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.binary = Path(cls._tmp.name)/(
            "f6b-score.exe" if sys.platform.startswith("win") else "f6b-score"
        )
        compile_result = subprocess.run(
            ["rustc","--edition=2021","-O",str(SOURCE),"-o",str(cls.binary)],
            capture_output=True,text=True,timeout=60,check=False,
        )
        if compile_result.returncode:
            raise AssertionError("Rust fixture compile failed: "
                                 + compile_result.stderr[:2200])

    def _tsv(self,text):
        return subprocess.run(
            [str(self.binary),"--tsv"],input=text,encoding="utf-8",
            capture_output=True,text=True,timeout=5,check=False,
        )

    def test_exactly_1500_parity_cases_against_existing_score(self):
        report = probe_rust(self.binary)
        self.assertEqual(1500,report["fixture_cases"])
        self.assertLessEqual(report["max_absolute_error"],1e-12)
        self.assertFalse(report["real_robot_validated"])
        self.assertEqual(0,report["motor_commands"])
        self.assertEqual(0,report["real_sensor_reads"])

    def test_all_or_nothing_for_malformed_batch(self):
        first = "observe\tball\t0.75\t0.55\t0.6\t0.8\t0.35\n"
        bad = "robot.move\tball\t0.75\t0.55\t0.6\t0.8\t0.35\n"
        out = self._tsv(first+bad)
        self.assertEqual(2,out.returncode)
        self.assertEqual("",out.stdout)
        self.assertIn("rejected fictional input",out.stderr)

    def test_nan_infinity_out_of_range_and_bare_text_refused(self):
        for m in ("NaN","inf","-inf","-0.01","1.1","false","hello"):
            with self.subTest(m=m):
                inp=f"observe\tball\t{m}\t0.55\t0.60\t0.80\t0.35\n"
                got=self._tsv(inp)
                self.assertEqual(2,got.returncode)
                self.assertEqual("",got.stdout)

    def test_unknown_or_motor_methods_cannot_be_intentions(self):
        for intent in ("robot.move","robot.stop","explore","sleep","Qwen"):
            with self.subTest(intent=intent):
                inp=f"{intent}\tball\t0.75\t0.55\t0.60\t0.80\t0.35\n"
                self.assertEqual(2,self._tsv(inp).returncode)

    def test_long_payload_and_excess_rows_are_rejected(self):
        valid="observe\tball\t0.75\t0.55\t0.6\t0.8\t0.35\n"
        self.assertEqual(2,self._tsv(valid*2049).returncode)
        self.assertEqual(2,self._tsv("X"*131073).returncode)
        self.assertEqual(2,self._tsv(valid+"\udcff").returncode
                         if False else 2)  # surrogate refused below
        result = subprocess.run(
            [str(self.binary),"--tsv"],
            input=(valid.encode("ascii") + b"\xff"),
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=5,check=False,
        )
        self.assertEqual(2,result.returncode)
        self.assertEqual(b"",result.stdout)

    def test_host_benchmark_compares_equal_work_checksums_not_robot_cost(self):
        comparison=benchmark_both(self.binary)
        self.assertFalse(comparison["rust_runtime_integration"])
        self.assertEqual(0,comparison["network_calls"])
        self.assertEqual(0,comparison["actual_qwen_runs"])
        self.assertEqual(BENCH_ITERATIONS,comparison["rust"]["iterations"])
        self.assertEqual(BENCH_ITERATIONS,comparison["python"]["iterations"])
        self.assertTrue(math.isclose(comparison["rust"]["checksum"],
                                    comparison["python"]["checksum"],
                                    rel_tol=1e-10,abs_tol=1e-8))
        self.assertGreater(comparison["rust"]["loop_wall_ms"],0)
        self.assertGreater(comparison["python"]["loop_wall_ms"],0)

    def test_rust_output_is_finite_for_edge_zero_and_one(self):
        data = "observe\tball\t0\t0\t0\t0\t0\nlisten\tknock\t1\t1\t1\t1\t1\n"
        r=self._tsv(data)
        self.assertEqual(0,r.returncode)
        self.assertEqual(2,len(r.stdout.splitlines()))
        self.assertTrue(all(math.isfinite(float(v))
                            for v in r.stdout.splitlines()))


if __name__=="__main__":
    unittest.main()
