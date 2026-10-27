"""X2-A: simulated telemetry quality and read-only endpoint-role contracts.

Scripted dataclasses only: NOT a real OEM process, MuJoCo run, authenticated
robot, camera, floor clearance, motor execution, or causal experience.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.sim_bridge import (
    SimulatorTelemetry, SimulatorTelemetryAssessment,
)
from microduck_companion.sim_ipc import (
    DepthReading, HealthReading, ReadOnlyUnixRpc, StateReading, TelemetryError,
)
from microduck_companion.sim_passive_cycles import PassiveSimCycleRunner


def receipt(*, battery=80., observed=100., seq=1, control=49.9):
    """Two structurally plausible simulated daemon readings, not sensors."""
    return SimulatorTelemetry(
        HealthReading(True, battery, 50., control, 0, observed),
        StateReading(False, False, control, 0, seq * 1_000_000, observed),
        DepthReading(
            seq, (1200,) * 64, (5,) * 64,
            seq * 1_000_000 + 10_000, observed,
        ),
    )


class SourceAssessmentTests(unittest.TestCase):

    def test_coherent_claim_is_only_a_claim_not_robot_authentication(self):
        sample = receipt()
        assessment = sample.assess(now=100.1)
        self.assertEqual("coherent", assessment.status)
        self.assertEqual("simulator_ipc_unverified", assessment.source)
        self.assertFalse(assessment.physical_robot_verified)
        self.assertFalse(assessment.floor_certified)
        self.assertFalse(assessment.motor_authorized)
        self.assertFalse(assessment.semantic_category_verified)
        self.assertTrue(sample._coherent(100.1, 2.))
        snapshot = sample.to_snapshot(now=100.1)
        self.assertEqual("simulator", snapshot.environment)
        self.assertEqual(["battery_pct"], [e.kind for e in snapshot.events])
        self.assertEqual(80., snapshot.events[0].value)
        self.assertEqual("robotd", snapshot.events[0].source)
        scene = snapshot.to_scene(now=100.1)
        self.assertFalse(scene.floor_clear)
        self.assertFalse(scene.safe_area)
        self.assertFalse(scene.perception_valid)
        memory = ExperienceMemory()
        self.addCleanup(memory.close)
        self.assertEqual(
            "halt", AutonomyBrain(memory).choose_from_snapshot(
                snapshot, now=100.1,
            ).intention,
        )
        self.assertEqual(0, memory.experience_count())

    def test_unknown_battery_remains_missing_without_fake_zero(self):
        sample = receipt(battery=None)
        self.assertEqual("coherent", sample.assess(now=100.1).status)
        self.assertEqual((), sample.to_snapshot(now=100.1).events)

    def test_source_failure_missing_and_invalid_stream_are_distinct(self):
        sample = receipt()
        cases = [
            (replace(sample, errors=("robotd telemetry unavailable",)), "source_error"),
            (replace(sample, health=None), "missing_stream"),
            (replace(sample, state=None), "missing_stream"),
            (replace(sample, depth=None), "missing_stream"),
            (replace(sample, depth="tof spoof"), "invalid_payload"),
            (replace(sample, health=replace(sample.health, battery_pct=True)), "invalid_payload"),
            (replace(sample, health=replace(sample.health, battery_pct=float("nan"))), "invalid_payload"),
            (replace(sample, health=replace(sample.health, target_hz="50")), "invalid_payload"),
            (replace(sample, state=replace(sample.state, missed_ticks=-1)), "invalid_payload"),
            (replace(sample, depth=replace(sample.depth, seq=-1)), "invalid_payload"),
            (replace(sample, depth=replace(sample.depth, distance_mm=(1200,) * 63)), "invalid_payload"),
            (replace(sample, depth=replace(sample.depth, status=(False,) * 64)), "invalid_payload"),
        ]
        for candidate, expected in cases:
            with self.subTest(reason=expected, sample=candidate):
                self.assertEqual(expected, candidate.assess(now=100.1).status)
                self.assertEqual((), candidate.to_snapshot(now=100.1).events)
                self.assertFalse(candidate._coherent(100.1, 2.))

    def test_fall_limp_health_and_slow_control_never_claim_coherence(self):
        sample = receipt(battery=10.)
        cases = [
            (replace(sample, health=replace(sample.health, healthy=False)), "unsafe_state"),
            (replace(sample, state=replace(sample.state, fallen=True)), "unsafe_state"),
            (replace(sample, state=replace(sample.state, limp=True)), "unsafe_state"),
            (replace(sample, state=replace(sample.state, achieved_hz=40.)), "slow_control"),
            (replace(sample, health=replace(sample.health, achieved_hz=40.)), "slow_control"),
            (replace(sample, health=replace(sample.health, target_hz=None)), "slow_control"),
        ]
        for candidate, status in cases:
            with self.subTest(status=status, sample=candidate):
                self.assertEqual(status, candidate.assess(now=100.1).status)
                self.assertEqual((), candidate.to_snapshot(now=100.1).events)

    def test_age_clock_and_cross_daemon_skew_are_classified(self):
        sample = receipt(battery=10.)
        checks = [
            (replace(sample, depth=replace(sample.depth, received_at=100.3)), "future_sample"),
            (replace(sample, depth=replace(sample.depth, received_at=97.)), "stale_sample"),
            (replace(sample, depth=replace(sample.depth, t_ns=3_000_000_000)), "timestamp_skew"),
            (replace(sample, state=replace(sample.state, received_at="now")), "invalid_payload"),
        ]
        for candidate, status in checks:
            with self.subTest(status=status):
                self.assertEqual(status, candidate.assess(now=100.1).status)
                self.assertEqual((), candidate.to_snapshot(now=100.1).events)
        for bad in (-1., float("nan"), float("inf"), True, "100.1"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                sample.assess(now=bad)
        for bad in (0., 9., True, "2", float("inf")):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                sample.assess(now=100.1, max_age_s=bad)

    def test_assessment_cannot_be_forged_into_execution_clearance(self):
        for fields in (
            {"status": "coherent", "source": "physical_robot"},
            {"status": "coherent", "physical_robot_verified": True},
            {"status": "coherent", "floor_certified": True},
            {"status": "coherent", "motor_authorized": True},
            {"status": "coherent", "semantic_category_verified": True},
            {"status": "invalid_new_status"},
            {"status": []},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                SimulatorTelemetryAssessment(**fields)

    def test_existing_p2b_preserves_no_execution_even_if_untrusted(self):
        with tempfile.TemporaryDirectory() as temp:
            memory = ExperienceMemory(Path(temp) / "existing.sqlite3")
            try:
                runner = PassiveSimCycleRunner(memory, session="x2a-no-movement")
                good = runner.step(receipt(observed=100., seq=1), now=100.1)
                self.assertEqual(("coherent", "halt"),
                                 (good.quality, good.plan.intention))
                stale = runner.step(
                    receipt(observed=97., seq=2, battery=10.), now=103.1,
                )
                self.assertEqual(("invalid_or_missing", "halt"),
                                 (stale.quality, stale.plan.intention))
                self.assertEqual({"no_action_executed"},
                                 {x["outcome"] for x in runner.history()})
                self.assertEqual({None}, {x["reward"] for x in runner.history()})
                self.assertEqual({0}, {x["motor_commands"] for x in runner.history()})
                self.assertEqual(0, memory.experience_count())
                self.assertEqual(0., memory.intent_preference("robot", "explore"))
            finally:
                memory.close()


class ExpectedDaemonRoleTests(unittest.TestCase):

    def test_wrong_read_lane_is_denied_before_any_socket_connection(self):
        # These paths do not exist. A wrong lane must be denied before I/O.
        robot = ReadOnlyUnixRpc("/path/does/not/exist", role="robotd")
        tof = ReadOnlyUnixRpc("/path/does/not/exist", role="tofd")
        for client, method, kwargs in (
            (robot, "tof.stream", {}),
            (tof, "robot.health", {}),
            (tof, "robot.subscribe", {"hz": 2}),
            (robot, "robot.move", {}),
            (tof, "robot.stop", {}),
        ):
            with self.subTest(method=method), self.assertRaises(ValueError):
                client.request(method, **kwargs)
        # A permitted lane still requires a real socket (not a free pass).
        with self.assertRaises(TelemetryError):
            robot.request("robot.health")
        with self.assertRaises(TelemetryError):
            tof.request("tof.stream")

    def test_invalid_daemon_role_rejected_instead_of_type_crash(self):
        for role in ("mediad", "robot", "ROBOTD", 1, True, [], {}):
            with self.subTest(role=role), self.assertRaises(ValueError):
                ReadOnlyUnixRpc("/tmp/fiction.sock", role=role)


if __name__ == "__main__":
    unittest.main()
