"""F2-D: bounded source/SQLite failures and measured host-only diagnostics."""
from __future__ import annotations

from pathlib import Path
import math
import socket
import sqlite3
import tempfile
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, PassiveObservationJournal,
    PerceptionEvent, PerceptionSnapshot,
)
from microduck_companion.passive_demo import (
    _fictional_unix_server, _frame, _item,
)
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.passive_resilience import (
    MAX_METRIC_SAMPLES, PassiveCycleLimits, PassiveCycleSupervisor,
)
from microduck_companion.passive_resilience_demo import run_session
from microduck_companion.passive_sources import FixtureUnixReader, PassiveRead

WALL = 1_770_000_000.0


def event(category="ball", *, kind="object_label", mono=100.,
          track="track-fixture", confidence=.96, source="mock"):
    return PerceptionEvent(
        kind, category, source, mono, 1., confidence,
        track_id=track if kind == "object_label" else None,
    )


def receipt(*events, sequence=1, at=100.,
            status="ok", channel="mock_fixture_unix", environment="mock"):
    return PassiveRead(
        status, PerceptionSnapshot(environment, tuple(events), at),
        sequence, channel,
    )


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "memory.sqlite3"
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.learning = PassiveLearning(self.memory)
        self.brain = AutonomyBrain(self.memory)
        self.moment = [100.1]
        self.wall = [WALL]
        self.frames = [receipt(event())]
        self.read_calls = 0
        self.reader = FixtureUnixReader(
            Path(self.folder.name) / "fixture.sock", clock=lambda: self.moment[0],
        )
        self.reader.read = self.fake_read

    def fake_read(self):
        self.read_calls += 1
        if not self.frames:
            return receipt(status="unavailable_or_invalid")
        return self.frames.pop(0)

    def supervisor(self, *, limits=None, perf_counter_ns=None,
                   process_time_ns=None, reader=None, brain=None,
                   journal=None, learning=None):
        extras = {}
        if perf_counter_ns is not None:
            extras["perf_counter_ns"] = perf_counter_ns
        if process_time_ns is not None:
            extras["process_time_ns"] = process_time_ns
        return PassiveCycleSupervisor(
            reader=reader or self.reader, brain=brain or self.brain,
            journal=journal or self.journal, learning=learning or self.learning,
            limits=limits or PassiveCycleLimits(),
            monotonic_s=lambda: self.moment[0],
            wall_epoch_s=lambda: self.wall[0], **extras,
        )

    def test_fresh_observation_is_passive_and_stored_once(self):
        runner = self.supervisor()
        result = runner.run_once()
        self.assertEqual(("ok","observe",1,1,1),
                         (result.status,result.intention,result.source_events,
                          result.stored_observations,result.scored_consequences))
        self.assertFalse(result.executed)
        self.assertEqual(0,result.motor_commands_issued)
        self.assertEqual(1,len(self.journal.recent(now_wall_epoch_s=WALL)))
        self.assertAlmostEqual(.02,self.learning.preference("observe"))
        self.assertEqual(0,self.memory.experience_count())
        m = runner.metrics()
        self.assertEqual(1,m.cycles_attempted)
        self.assertEqual((("ok",1),),m.status_counts)
        self.assertEqual((("observe",1),),m.intention_counts)
        self.assertGreaterEqual(m.p50_elapsed_ms,0)
        self.assertGreaterEqual(m.p95_elapsed_ms,0)
        self.assertGreaterEqual(m.mean_process_cpu_ms,0)
        self.assertGreaterEqual(m.max_elapsed_ms,m.p95_elapsed_ms)
        self.assertIn(result.process_peak_rss_kib,(None,result.process_peak_rss_kib))

    def test_repeat_category_is_not_perpetually_reannounced(self):
        self.frames.append(receipt(event(mono=101.),sequence=2,at=101.))
        runner = self.supervisor()
        first = runner.run_once()
        self.moment[0],self.wall[0] = 101.1,WALL+1
        second = runner.run_once()
        self.assertEqual(("observe","idle"),(first.intention,second.intention))
        self.assertEqual(("ok","ok"),(first.status,second.status))
        self.assertAlmostEqual(.015,self.learning.preference("observe"))
        self.assertEqual(2,runner.metrics().stored_observations)

    def test_missing_source_never_reuses_last_success(self):
        self.frames.append(receipt(event(mono=101.),sequence=2,at=101.,
                                   status="unavailable_or_invalid"))
        runner = self.supervisor()
        runner.run_once()
        before = self.brain.motives.energy
        self.moment[0],self.wall[0] = 101.1,WALL+1
        failed = runner.run_once()
        self.assertEqual(("source_unavailable","idle",0,0,0),
                         (failed.status,failed.intention,failed.source_events,
                          failed.stored_observations,failed.scored_consequences))
        self.assertEqual(before,self.brain.motives.energy)
        self.assertEqual(1,len(self.journal.recent(now_wall_epoch_s=WALL+1)))
        self.assertAlmostEqual(.02,self.learning.preference("observe"))

    def test_invalid_source_is_not_logged(self):
        for invalid in (
            receipt(event(),channel="oem_media_hello_only"),
            receipt(event(),environment="robot"),
            receipt(event(source="sensor")),
            receipt(event(),sequence=None),
            receipt(event(),sequence=-1),
        ):
            with self.subTest(invalid=invalid):
                self.frames = [invalid]
                runner = self.supervisor()
                r=runner.run_once()
                self.assertEqual(("invalid_or_deferred","idle"),
                                 (r.status,r.intention))
                self.assertEqual(0,r.stored_observations)
                self.assertEqual(0,len(self.journal.recent(now_wall_epoch_s=WALL)))
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_stale_and_future_evidence_cannot_be_replayed(self):
        for frame in (
            receipt(event(mono=97.),at=97.),
            receipt(event(mono=102.),at=102.),
            receipt(event(confidence=.2)),
        ):
            self.frames=[frame]
            r=self.supervisor().run_once()
            self.assertEqual("invalid_or_deferred",r.status)
        self.assertEqual(0,len(self.journal.recent(now_wall_epoch_s=WALL)))

    def test_unknown_and_conflict_can_be_stored_but_not_rewarded(self):
        self.frames=[
            receipt(event("unknown")),
            receipt(event("ball",mono=101.),event("toy",mono=101.),
                    sequence=2,at=101.),
        ]
        runner=self.supervisor()
        first=runner.run_once()
        self.moment[0],self.wall[0] = 101.1,WALL+1
        second=runner.run_once()
        self.assertEqual(("ok","ok"),(first.status,second.status))
        # The second unresolved category shares F2-B's 3 s cooldown:
        # it is still journalled, but inspection is not repeated.
        self.assertEqual(("inspect","idle"),
                         (first.intention,second.intention))
        self.assertEqual(2,runner.metrics().scored_consequences)
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_duplicate_fixture_sequence_is_not_scored_twice(self):
        self.frames=[
            receipt(event()),
            receipt(event(mono=101.),sequence=1,at=101.),
        ]
        runner=self.supervisor()
        runner.run_once()
        self.moment[0],self.wall[0] = 101.1,WALL+1
        second=runner.run_once()
        self.assertEqual("invalid_or_deferred",second.status)
        self.assertEqual(1,len(self.learning.history()))
        self.assertAlmostEqual(.02,self.learning.preference("observe"))

    def test_closed_sqlite_fails_closed_before_source_read(self):
        self.memory.close()
        report=self.supervisor().run_once()
        self.assertEqual(("storage_unavailable","idle"),
                         (report.status,report.intention))
        self.assertEqual(0,self.read_calls)
        self.assertEqual(.8,self.brain.motives.energy)

    def test_reader_exception_is_quarantined_without_energy_update(self):
        def fail():
            raise RuntimeError("simulated broken socket")
        self.reader.read=fail
        out=self.supervisor().run_once()
        self.assertEqual(("source_exception","idle"),
                         (out.status,out.intention))
        self.assertEqual(.8,self.brain.motives.energy)
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_cycle_quota_refuses_extra_read(self):
        runner=self.supervisor(limits=PassiveCycleLimits(max_cycles=1))
        self.assertEqual("ok",runner.run_once().status)
        before=self.read_calls
        self.assertEqual("quota_cycles",runner.run_once().status)
        self.assertEqual(before,self.read_calls)
        self.assertEqual(1,runner.metrics().cycles_attempted)

    def test_event_quota_rejects_without_committing(self):
        self.frames=[receipt(event("ball",track="track-a"),
                             event("toy",track="track-b"))]
        runner=self.supervisor(limits=PassiveCycleLimits(max_events=1))
        result=runner.run_once()
        self.assertEqual(("quota_events","idle"),
                         (result.status,result.intention))
        self.assertEqual(0,runner.metrics().source_events_accepted)
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_event_budget_is_cumulative_over_valid_frames(self):
        self.frames=[
            receipt(event()),
            receipt(event("toy",mono=101.),sequence=2,at=101.),
        ]
        runner=self.supervisor(limits=PassiveCycleLimits(max_events=1))
        self.assertEqual("ok",runner.run_once().status)
        self.moment[0],self.wall[0]=101.1,WALL+1
        self.assertEqual("quota_events",runner.run_once().status)
        self.assertEqual(1,runner.metrics().source_events_accepted)
        self.assertEqual(1,len(self.learning.history()))

    def test_soft_source_budget_rejects_before_any_proposal(self):
        perf=iter((0,5_000_000,6_000_000))
        runner=self.supervisor(
            limits=PassiveCycleLimits(max_read_ms=1,max_cycle_ms=50),
            perf_counter_ns=lambda: next(perf),
            process_time_ns=lambda: 0,
        )
        r=runner.run_once()
        self.assertEqual("late_source",r.status)
        self.assertEqual(5.,r.source_ms)
        self.assertEqual(.8,self.brain.motives.energy)
        self.assertEqual(0,len(self.learning.history()))

    def test_soft_cycle_budget_before_commit(self):
        perf=iter((0,1_000_000,100_000_000,110_000_000))
        runner=self.supervisor(
            limits=PassiveCycleLimits(max_read_ms=10,max_cycle_ms=20),
            perf_counter_ns=lambda: next(perf),
            process_time_ns=lambda: 0,
        )
        r=runner.run_once()
        self.assertEqual(("late_before_commit","idle"),
                         (r.status,r.intention))
        self.assertEqual(0,len(self.journal.recent(now_wall_epoch_s=WALL)))
        # Soft budget cannot roll back the already-evaluated RAM intention.
        self.assertAlmostEqual(.785,self.brain.motives.energy)

    def test_late_after_commit_is_reported_not_pretended_undone(self):
        perf=iter((0,1_000_000,2_000_000,100_000_000,110_000_000))
        runner=self.supervisor(
            limits=PassiveCycleLimits(max_read_ms=10,max_cycle_ms=20),
            perf_counter_ns=lambda: next(perf),
            process_time_ns=lambda: 0,
        )
        r=runner.run_once()
        self.assertEqual(("late_after_commit",1,1),
                         (r.status,r.stored_observations,r.scored_consequences))
        self.assertAlmostEqual(.02,self.learning.preference("observe"))

    def test_f2c_unavailable_after_journal_commit_never_fakes_reward(self):
        self.memory.conn.execute("DROP TABLE passive_learning_events")
        r=self.supervisor().run_once()
        self.assertEqual(("storage_unavailable",0),
                         (r.status,r.scored_consequences))
        # Independent F1-C transaction can already be committed.
        self.assertEqual(1,len(self.journal.recent(now_wall_epoch_s=WALL)))
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_recovered_connection_keeps_history_but_never_replays_as_live(self):
        self.supervisor().run_once()
        self.memory.close()
        second_mem=ExperienceMemory(self.db)
        try:
            second_journal=PassiveObservationJournal(second_mem)
            second_learning=PassiveLearning(second_mem)
            second_brain=AutonomyBrain(second_mem)
            self.frames=[receipt(status="unavailable_or_invalid")]
            runner=self.supervisor(brain=second_brain,
                                   journal=second_journal,learning=second_learning)
            result=runner.run_once()
            self.assertEqual(("source_unavailable","idle"),(result.status,result.intention))
            self.assertEqual(1,len(second_journal.recent(now_wall_epoch_s=WALL)))
            self.assertAlmostEqual(.02,second_learning.preference("observe"))
            self.assertEqual(.8,second_brain.motives.energy)
        finally:
            second_mem.close()

    def test_constructor_prohibits_cross_database_mismatch(self):
        other_mem=ExperienceMemory()
        self.addCleanup(other_mem.close)
        other_journal=PassiveObservationJournal(other_mem)
        other_learning=PassiveLearning(other_mem)
        with self.assertRaises(ValueError):
            self.supervisor(journal=other_journal)
        with self.assertRaises(ValueError):
            self.supervisor(learning=other_learning)
        with self.assertRaises(TypeError):
            self.supervisor(reader="not a fixture")
        with self.assertRaises(TypeError):
            self.supervisor(limits="bad limits")

    def test_limits_reject_bool_nan_and_unsafe_large_values(self):
        for args in (
            {"max_cycles":0},{"max_cycles":True},{"max_cycles":513},
            {"max_events":0},{"max_events":True},{"max_events":8193},
            {"max_read_ms":True},{"max_read_ms":float("nan")},
            {"max_read_ms":3001},{"max_cycle_ms":float("inf")},
            {"max_cycle_ms":9999},{"max_read_ms":200,"max_cycle_ms":100},
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                PassiveCycleLimits(**args)

    def test_metrics_window_is_bounded_on_many_failures(self):
        self.frames=[receipt(status="unavailable_or_invalid") for _ in range(70)]
        runner=self.supervisor(limits=PassiveCycleLimits(max_cycles=80))
        for _ in range(70):
            self.assertEqual("source_unavailable",runner.run_once().status)
        stats=runner.metrics()
        self.assertEqual(70,stats.cycles_attempted)
        self.assertEqual(MAX_METRIC_SAMPLES,stats.recent_samples)
        self.assertEqual((("source_unavailable",70),),stats.status_counts)
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_metrics_are_host_process_only_and_nonnegative(self):
        r=self.supervisor().run_once()
        self.assertGreaterEqual(r.source_ms,0)
        self.assertGreaterEqual(r.elapsed_ms,0)
        self.assertGreaterEqual(r.process_cpu_ms,0)
        self.assertTrue(r.process_peak_rss_kib is None
                        or r.process_peak_rss_kib>=0)
        self.assertNotIn("temperature",str(r))
        self.assertNotIn("battery",str(r))


@unittest.skipUnless(hasattr(socket,"AF_UNIX"),"requires Unix sockets")
class SocketAndRestartTests(unittest.TestCase):
    def test_real_unix_fixture_with_source_outage(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"memory.sqlite3"
            sock=Path(folder)/"fixture.sock"
            now=[100.1]
            wall=[WALL]
            replies=(
                _frame(1,100.,_item("ball")),
                b"",
                _frame(3,102.,_item("dog")),
            )
            memory=ExperienceMemory(db)
            try:
                journal=PassiveObservationJournal(memory)
                learning=PassiveLearning(memory)
                reader=FixtureUnixReader(sock,timeout_s=.3,
                                         clock=lambda:now[0])
                with _fictional_unix_server(sock,replies):
                    sup=PassiveCycleSupervisor(
                        reader=reader,brain=AutonomyBrain(memory),
                        journal=journal,learning=learning,
                        monotonic_s=lambda:now[0],
                        wall_epoch_s=lambda:wall[0],
                    )
                    statuses=[]
                    for i,t in enumerate((100.1,101.1,102.1)):
                        now[0],wall[0]=t,WALL+i
                        statuses.append(sup.run_once().status)
                self.assertEqual(["ok","source_unavailable","ok"],statuses)
                self.assertEqual(2,sup.metrics().stored_observations)
                self.assertEqual(0,memory.experience_count())
            finally:
                memory.close()

    def test_two_sessions_same_sqlite_keep_learning_and_hosts_measured(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"state.sqlite3"
            first=run_session(db,session="first")
            second=run_session(db,session="second")
            self.assertEqual(("first","second"),
                             (first["session"],second["session"]))
            self.assertEqual(5,first["metrics"]["stored_observations"])
            self.assertEqual(3,second["metrics"]["stored_observations"])
            self.assertEqual(1,first["source_outages"])
            self.assertEqual(1,second["source_outages"])
            self.assertAlmostEqual(.035,first["bias_observe"])
            self.assertAlmostEqual(.05,second["bias_observe"])
            self.assertAlmostEqual(.02,first["bias_listen"])
            self.assertAlmostEqual(.04,second["bias_listen"])
            self.assertEqual(0,second["motor_commands"])
            self.assertGreaterEqual(second["metrics"]["p95_elapsed_ms"],0.)
            self.assertTrue(second["metrics"]["observed_peak_rss_kib"] is None
                            or second["metrics"]["observed_peak_rss_kib"]>=0)

    def test_second_session_alone_refuses_to_invent_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                run_session(Path(folder)/"new.sqlite3",session="second")

    def test_first_session_repeated_refuses_to_reset_prior_history(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"used.sqlite3"
            run_session(db,session="first")
            with self.assertRaises(RuntimeError):
                run_session(db,session="first")


if __name__ == "__main__":
    unittest.main()
