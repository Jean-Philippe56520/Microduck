"""F6-C: opt-in window quotas, overload backoff and full F2-D fail-closed I/O.

All source observations are PUBLIC fictional categories. No OEM services,
image, voice, real sensor, person, Ollama, network or motor is accessed.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import math
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.offline_resource_budget import (
    OfflineBudgetLimits, OfflineResourceGate,
)
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_resilience import (
    PassiveCycleLimits, PassiveCycleSupervisor,
)
from microduck_companion.passive_sources import FixtureUnixReader, PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_780_000_000.0


def fake_read(category: str, *, monotonic: float,
              sequence: int, kind: str = "object_label",
              status: str = "ok") -> PassiveRead:
    evt = PerceptionEvent(
        kind, category, "mock", monotonic - .1, 1., .95,
        track_id=(f"track-fixture-{sequence}" if kind == "object_label"
                  else None),
    )
    return PassiveRead(
        status, PerceptionSnapshot("mock", (evt,), monotonic - .1),
        sequence, "mock_fixture_unix",
    )


class LimitsTests(unittest.TestCase):
    def test_initial_defaults_are_soft_policy_not_robot_limits(self):
        limits = OfflineBudgetLimits()
        self.assertEqual(10., limits.window_s)
        self.assertEqual(.5, limits.min_cycle_gap_s)
        self.assertEqual(8, limits.max_window_cycles)
        self.assertEqual(32, limits.max_window_events)
        self.assertIsNone(limits.max_cycle_cpu_ms)
        self.assertIsNone(limits.max_process_peak_rss_kib)

    def test_wrong_limits_rejected(self):
        samples = (
            {"window_s": True}, {"window_s": 0},
            {"window_s": math.nan}, {"window_s": math.inf},
            {"cooldown_s": -1}, {"cooldown_s": float("inf")},
            {"min_cycle_gap_s": -1}, {"min_cycle_gap_s": 11},
            {"max_window_cycles": 0}, {"max_window_cycles": True},
            {"max_window_events": 0}, {"max_window_events": 10000},
            {"max_cycle_cpu_ms": 0}, {"max_cycle_cpu_ms": math.nan},
            {"max_process_peak_rss_kib": 0},
            {"max_process_peak_rss_kib": 2.5},
            {"max_process_peak_rss_kib": True},
        )
        for change in samples:
            with self.subTest(change=change), self.assertRaises(ValueError):
                OfflineBudgetLimits(**change)

    def test_rate_and_event_limits_are_exact_with_rolling_expiry(self):
        gate = OfflineResourceGate(OfflineBudgetLimits(
            window_s=2., min_cycle_gap_s=.5,
            max_window_cycles=2, max_window_events=2,
        ))
        self.assertIsNone(gate.admit_cycle(100.))
        self.assertIsNone(gate.admit_events(2))
        self.assertEqual("budget_cycle_inflight", gate.admit_cycle(100.1))
        # A controlled report closes the first reservation.
        from microduck_companion.passive_resilience import PassiveCycleReport
        def rep():
            return PassiveCycleReport(
                "ok", "observe", "fixture", 2, 1, 1, .1, .3, .2, 1000,
            )
        gate.report(rep(), now_monotonic_s=100.1)
        self.assertEqual("budget_cycle_gap", gate.admit_cycle(100.2))
        self.assertIsNone(gate.admit_cycle(100.6))
        self.assertEqual("budget_window_events", gate.admit_events(1))
        gate.report(rep(), now_monotonic_s=100.7)
        self.assertEqual("budget_window_cycles", gate.admit_cycle(101.2))
        self.assertIsNone(gate.admit_cycle(102.1))
        self.assertIsNone(gate.admit_events(2))
        gate.report(rep(), now_monotonic_s=102.2)
        snap = gate.snapshot()
        self.assertEqual(2, snap.admitted_events_in_window)
        self.assertEqual(2, snap.admitted_cycles_in_window)
        self.assertFalse(snap.pending_cycle)
        self.assertEqual(0, snap.motor_commands)
        self.assertEqual(0, snap.pc_queries)

    def test_invalid_or_excessive_events_never_count_as_admitted(self):
        for bad in (65, -1, "2", None, True, 3.0):
            gate = OfflineResourceGate()
            self.assertIsNone(gate.admit_cycle(100.))
            self.assertEqual("budget_invalid_events",gate.admit_events(bad))
            self.assertEqual(0,gate.snapshot().admitted_events_in_window)

    def test_rollback_is_latched_not_a_quota_reset(self):
        gate = OfflineResourceGate()
        self.assertIsNone(gate.admit_cycle(100.))
        self.assertEqual("budget_clock_reset",gate.admit_cycle(99.))
        self.assertEqual("budget_clock_reset",gate.admit_cycle(300.))
        self.assertEqual("budget_clock_reset",
                         gate.snapshot().latched_resource_failure)

    def test_bad_clock_refuses_without_crashing(self):
        for bad in (float("nan"), float("inf"), -1, True, None):
            with self.subTest(bad=bad):
                gate = OfflineResourceGate()
                self.assertEqual("budget_invalid_clock",
                                 gate.admit_cycle(bad))
                self.assertFalse(gate.snapshot().pending_cycle)

    def test_gate_state_is_bounded_after_many_cycles(self):
        gate = OfflineResourceGate(OfflineBudgetLimits(
            window_s=1., min_cycle_gap_s=0.,
            max_window_cycles=2, max_window_events=64,
        ))
        from microduck_companion.passive_resilience import PassiveCycleReport
        rep = PassiveCycleReport("ok", "idle", "quiet",
                                 0, 0, 0, 0., .1, .1, 1000)
        for i in range(100):
            now = 100. + i
            self.assertIsNone(gate.admit_cycle(now))
            self.assertIsNone(gate.admit_events(1))
            gate.report(rep, now_monotonic_s=now+.01)
            self.assertLessEqual(gate.snapshot().admitted_cycles_in_window,2)
            self.assertLessEqual(gate.snapshot().admitted_events_in_window,2)


class SupervisorGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory = ExperienceMemory(Path(self.tmp.name)/"fictional.sqlite3")
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.learning = PassiveLearning(self.memory)
        self.brain = AutonomyBrain(self.memory)
        self.monotonic = [100.1]
        self.wall = [WALL]
        self.frames = []
        self.reads = 0
        self.reader = FixtureUnixReader(
            Path(self.tmp.name)/"not-a-real-oem.sock",
            clock=lambda: self.monotonic[0],
        )
        self.reader.read = self.read_fixture
        self.gate = OfflineResourceGate()
        self.cpu_ns = [0]

    def read_fixture(self):
        self.reads += 1
        if self.frames:
            return self.frames.pop(0)
        return PassiveRead("unavailable_or_invalid",None,0,"mock_fixture_unix")

    def add(self, name="ball", *, at=100.1, seq=1, kind="object_label"):
        self.frames.append(fake_read(
            name,monotonic=at,sequence=seq,kind=kind,
        ))

    def supervisor(self, *, limits=None, gate=None, cpu_ns=None,
                   perf_counter_ns=None):
        return PassiveCycleSupervisor(
            reader=self.reader, brain=self.brain,
            journal=self.journal,learning=self.learning,
            limits=limits if limits is not None
            else PassiveCycleLimits(max_cycles=16,max_events=128),
            resource_gate=gate if gate is not None else self.gate,
            monotonic_s=lambda: self.monotonic[0],
            wall_epoch_s=lambda: self.wall[0],
            process_time_ns=cpu_ns if cpu_ns is not None
                else (lambda: self.cpu_ns[0]),
            **({"perf_counter_ns":perf_counter_ns}
               if perf_counter_ns is not None else {}),
        )

    def test_admission_rejection_does_not_read_or_write(self):
        self.gate = OfflineResourceGate(OfflineBudgetLimits(
            min_cycle_gap_s=.5,
        ))
        self.add()
        self.add("toy",at=100.2,seq=2)
        runner = self.supervisor()
        first = runner.run_once()
        self.assertEqual("ok",first.status)
        self.assertEqual(1,self.reads)
        self.monotonic[0]=100.2
        self.wall[0]+=1
        denied=runner.run_once()
        self.assertEqual("budget_cycle_gap",denied.status)
        self.assertEqual("idle",denied.intention)
        self.assertEqual(0,denied.motor_commands_issued)
        self.assertFalse(denied.executed)
        self.assertEqual(1,self.reads)
        self.assertEqual(1,runner.metrics().cycles_attempted)
        self.assertEqual(1,self.journal.category_count(
            "object_label","ball",now_wall_epoch_s=self.wall[0]))

    def test_event_window_drops_entire_overflow_before_memory(self):
        self.gate=OfflineResourceGate(OfflineBudgetLimits(
            max_window_events=1,min_cycle_gap_s=.5,
        ))
        self.add("ball",at=100.1,seq=1)
        self.add("toy",at=100.7,seq=2)
        runner=self.supervisor()
        self.assertEqual("ok",runner.run_once().status)
        prior=self.brain.motives.energy
        self.monotonic[0]=100.7
        self.wall[0]+=1
        result=runner.run_once()
        self.assertEqual(("budget_window_events","idle",0,0),
                         (result.status,result.intention,
                          result.stored_observations,result.scored_consequences))
        self.assertEqual(prior,self.brain.motives.energy)
        self.assertEqual(2,self.reads)
        self.assertEqual(1,len(self.journal.recent(
            now_wall_epoch_s=self.wall[0])))
        self.assertEqual(1,self.gate.snapshot().admitted_events_in_window)

    def test_window_cycle_quota_checked_before_source_read(self):
        self.gate=OfflineResourceGate(OfflineBudgetLimits(
            max_window_cycles=2,max_window_events=10,
        ))
        self.add(at=100.1)
        self.add("toy",at=100.7,seq=2)
        self.add("dog",at=101.3,seq=3)
        runner=self.supervisor()
        self.assertEqual("ok",runner.run_once().status)
        self.monotonic[0]=100.7
        self.wall[0]+=1
        self.assertEqual("ok",runner.run_once().status)
        self.monotonic[0]=101.3
        self.wall[0]+=1
        self.assertEqual("budget_window_cycles",runner.run_once().status)
        self.assertEqual(2,self.reads)
        self.assertEqual(2,runner.metrics().cycles_attempted)

    def test_clock_rollback_blocks_without_reading_old_frame(self):
        self.add(at=100.1)
        self.add(at=100.2,seq=2)
        runner=self.supervisor()
        self.assertEqual("ok",runner.run_once().status)
        self.monotonic[0]=99.
        self.assertEqual("budget_clock_reset",runner.run_once().status)
        self.monotonic[0]=200.
        self.assertEqual("budget_clock_reset",runner.run_once().status)
        self.assertEqual(1,self.reads)

    def test_over_budget_cpu_triggers_future_cooldown(self):
        self.add()
        self.add("toy",at=101.,seq=2)
        self.gate=OfflineResourceGate(OfflineBudgetLimits(
            max_cycle_cpu_ms=1.,cooldown_s=2.,min_cycle_gap_s=.5,
        ))
        self.cpu_ns=[0]
        def process_time():
            self.cpu_ns[0]+=2_000_000
            return self.cpu_ns[0]
        runner=self.supervisor(cpu_ns=process_time)
        self.assertEqual("ok",runner.run_once().status)
        self.monotonic[0]=101.
        self.assertEqual("budget_cooldown",runner.run_once().status)
        self.assertEqual(1,self.reads)
        self.monotonic[0]=102.2
        self.wall[0]+=1
        self.assertEqual("ok",runner.run_once().status)
        self.assertEqual(2,self.reads)

    def test_missing_rss_with_configured_limit_latches(self):
        self.add()
        self.add("toy",at=101.,seq=2)
        self.gate=OfflineResourceGate(OfflineBudgetLimits(
            max_process_peak_rss_kib=500,
        ))
        runner=self.supervisor()
        with patch("microduck_companion.passive_resilience._peak_rss_kib",
                   return_value=None):
            self.assertEqual("ok",runner.run_once().status)
            self.monotonic[0]=101.
            self.assertEqual("budget_missing_rss",runner.run_once().status)
        self.assertEqual(1,self.reads)
        self.assertEqual("budget_missing_rss",
                         self.gate.snapshot().latched_resource_failure)

    def test_high_process_rss_latches_without_memory_replay(self):
        self.add()
        self.add("toy",at=101.,seq=2)
        self.gate=OfflineResourceGate(OfflineBudgetLimits(
            max_process_peak_rss_kib=500,
        ))
        runner=self.supervisor()
        with patch("microduck_companion.passive_resilience._peak_rss_kib",
                   return_value=1234):
            self.assertEqual("ok",runner.run_once().status)
            self.monotonic[0]=101.
            self.assertEqual("budget_rss_limit",runner.run_once().status)
        self.assertEqual(1,self.reads)
        self.assertEqual(1,len(self.journal.recent(
            now_wall_epoch_s=WALL+1)))

    def test_source_latency_opens_cooldown_without_sqlite_commit(self):
        self.add()
        self.add("toy",at=101.,seq=2)
        ticks=[0]
        def perf():
            ticks[0]+=20_000_000
            return ticks[0]
        runner=self.supervisor(
            limits=PassiveCycleLimits(max_cycles=3,max_events=3,
                                      max_read_ms=10.,max_cycle_ms=50.),
            perf_counter_ns=perf,
        )
        self.assertEqual("late_source",runner.run_once().status)
        self.monotonic[0]=101.
        self.assertEqual("budget_cooldown",runner.run_once().status)
        self.assertEqual(1,self.reads)
        self.assertEqual(0,len(self.journal.recent(now_wall_epoch_s=WALL)))

    def test_unknown_rss_allowed_without_rss_threshold(self):
        self.add()
        runner=self.supervisor()
        with patch("microduck_companion.passive_resilience._peak_rss_kib",
                   return_value=None):
            self.assertEqual("ok",runner.run_once().status)
        self.assertIsNone(self.gate.snapshot().latched_resource_failure)

    def test_failed_source_consumes_slot_but_no_observation(self):
        runner=self.supervisor()
        r=runner.run_once()
        self.assertEqual("source_unavailable",r.status)
        self.assertEqual(1,runner.metrics().cycles_attempted)
        self.assertEqual(0,self.gate.snapshot().admitted_events_in_window)
        self.assertFalse(self.gate.snapshot().pending_cycle)
        self.assertEqual(0,self.memory.experience_count())

    def test_f2d_without_gate_retains_backward_compatible_behavior(self):
        self.add()
        runner=PassiveCycleSupervisor(
            reader=self.reader, brain=self.brain,
            journal=self.journal,learning=self.learning,
            monotonic_s=lambda:self.monotonic[0],
            wall_epoch_s=lambda:self.wall[0],
        )
        self.assertEqual("ok",runner.run_once().status)
        self.assertEqual(1,self.reads)
        self.assertEqual(0,self.gate.snapshot().admitted_cycles_in_window)

    def test_wrong_gate_type_rejected(self):
        with self.assertRaises(TypeError):
            PassiveCycleSupervisor(
                reader=self.reader,brain=self.brain,
                journal=self.journal,learning=self.learning,
                resource_gate=object(),
            )


if __name__ == "__main__":
    unittest.main()
