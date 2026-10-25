"""F2-C: mock-only, correctable category outcomes; NO executed actions."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, Motivations,
    PassiveObservationJournal, PerceptionEvent, PerceptionSnapshot,
)
from microduck_companion.passive_learning import (
    MAX_ATTENTION_BIAS, PassiveLearning,
)
from microduck_companion.passive_sources import PassiveRead

WALL = 1_770_000_000.0


def event(category="ball", *, kind="object_label", mono=100.,
          track="track-fixture", source="mock", confidence=.96):
    return PerceptionEvent(
        kind, category, source, mono, 1.0, confidence,
        track_id=track if kind == "object_label" else None,
    )


def read(*events, seq=1, at=100., channel="mock_fixture_unix",
         env="mock", status="ok"):
    return PassiveRead(
        status, PerceptionSnapshot(env, tuple(events), at),
        seq, channel,
    )


class LearningTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / "memory.sqlite3"
        self.mem = ExperienceMemory(self.db)
        self.addCleanup(self.mem.close)
        self.journal = PassiveObservationJournal(self.mem)
        self.learning = PassiveLearning(self.mem)

    def write(self, category="ball", *, seq=1, mono=100., wall=WALL,
              kind="object_label", confidence=.96):
        r = read(event(category,kind=kind,mono=mono,confidence=confidence),
                 seq=seq,at=mono)
        inserted = self.journal.append(
            r,now_monotonic_s=mono+.1,now_wall_epoch_s=wall)
        self.assertEqual(1, inserted)
        return self.learning.record(
            journal=self.journal,sequence=seq,now_wall_epoch_s=wall)

    def test_novel_then_repeated_is_source_labelled_and_slow(self):
        (one,) = self.write()
        self.assertEqual(("ball","new_information","mock_fixture_journal"),
                         (one.category,one.outcome,one.source))
        self.assertTrue(one.active)
        self.assertAlmostEqual(.02,self.learning.preference("observe"))
        (two,) = self.write(seq=2,mono=101.,wall=WALL+1)
        self.assertEqual("repeated_observation",two.outcome)
        self.assertAlmostEqual(.015,self.learning.preference("observe"))
        self.assertEqual(0.,self.learning.preference("inspect"))
        self.assertEqual(0.,self.mem.intent_preference("simulator","explore"))
        self.assertEqual(0,self.mem.experience_count())
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])

    def test_double_record_is_idempotent(self):
        self.write()
        prior=self.learning.preference("observe")
        again=self.learning.record(
            journal=self.journal,sequence=1,now_wall_epoch_s=WALL)
        self.assertEqual(1,len(again))
        self.assertAlmostEqual(prior,self.learning.preference("observe"))
        self.assertEqual(1,self.mem.conn.execute(
            "SELECT COUNT(*) FROM passive_learning_events").fetchone()[0])

    def test_same_category_two_tracks_same_frame_count_once(self):
        r=read(event(track="track-one"),
               event(track="track-two"),seq=1)
        self.assertEqual(2,self.journal.append(
            r,now_monotonic_s=100.1,now_wall_epoch_s=WALL))
        events=self.learning.record(
            journal=self.journal,sequence=1,now_wall_epoch_s=WALL)
        self.assertEqual(["new_information","duplicate_in_frame"],
                         [x.outcome for x in events])
        self.assertAlmostEqual(.02,self.learning.preference("observe"))

    def test_sound_and_object_stay_distinct(self):
        self.write("ball")
        (sound,) = self.write("bark",kind="sound_label",
                              seq=2,mono=101.,wall=WALL+1)
        self.assertEqual("new_information",sound.outcome)
        self.assertAlmostEqual(.02,self.learning.preference("observe"))
        self.assertAlmostEqual(.02,self.learning.preference("listen"))
        self.assertEqual(0.,self.learning.preference("inspect"))

    def test_unknown_conflict_and_low_confidence_are_not_rewards(self):
        (unknown,) = self.write("unknown")
        self.assertEqual("unresolved",unknown.outcome)
        (low,) = self.write("cat",seq=2,mono=101.,wall=WALL+1,
                             confidence=.35)
        self.assertEqual("rejected",low.outcome)
        conflict=read(
            event("cat",mono=102.),event("dog",mono=102.),
            seq=3,at=102.)
        self.journal.append(conflict,now_monotonic_s=102.1,
                            now_wall_epoch_s=WALL+2)
        (result,)=self.learning.record(
            journal=self.journal,sequence=3,now_wall_epoch_s=WALL+2)
        self.assertEqual(("unknown","unresolved"),
                         (result.category,result.outcome))
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_bad_source_failed_reader_and_missing_sequence_cannot_learn(self):
        for r in (
            read(event(),channel="oem_media_hello_only"),
            read(event(),env="robot"),
            read(event(source="sensor")),
        ):
            with self.subTest(r=r),self.assertRaises((ValueError,TypeError)):
                self.journal.append(r,now_monotonic_s=100.1,
                                    now_wall_epoch_s=WALL)
        bad=read(event(),status="unavailable_or_invalid")
        self.assertEqual(0,self.journal.append(
            bad,now_monotonic_s=100.1,now_wall_epoch_s=WALL))
        self.assertEqual((),self.learning.record(
            journal=self.journal,sequence=1,now_wall_epoch_s=WALL))
        self.assertEqual(0.,self.learning.preference("observe"))

    def test_old_or_future_fixture_not_replayed_as_consequence(self):
        r=read(event())
        self.journal.append(r,now_monotonic_s=100.1,now_wall_epoch_s=WALL)
        self.assertEqual((),self.learning.record(
            journal=self.journal,sequence=1,
            now_wall_epoch_s=WALL+3))
        self.assertEqual((),self.learning.record(
            journal=self.journal,sequence=1,
            now_wall_epoch_s=WALL-3))
        self.assertEqual(0.,self.learning.preference("observe"))
        self.assertEqual(0,len(self.learning.history()))

    def test_manual_retraction_recomputes_and_is_idempotent(self):
        (one,)=self.write()
        (two,)=self.write(seq=2,mono=101.,wall=WALL+1)
        self.assertAlmostEqual(.015,self.learning.preference("observe"))
        self.assertTrue(self.learning.retract(
            one.observation_id,reason="fixture_annotation_error"))
        self.assertAlmostEqual(.02,self.learning.preference("observe"))
        self.assertEqual(["withdrawn","new_information"],
                         [row.outcome for row in reversed(self.learning.history())])
        self.assertFalse(self.learning.retract(
            one.observation_id,reason="fixture_annotation_error"))
        self.assertTrue(self.learning.retract(
            two.observation_id,reason="source_retracted"))
        self.assertEqual(0.,self.learning.preference("observe"))
        self.assertEqual(2,len(self.journal.recent(now_wall_epoch_s=WALL+1)))
        self.assertEqual(2,len(self.learning.history()))

    def test_invalid_retraction_rejected(self):
        (one,)=self.write()
        for reason in ("", "sensor_confirmed", None):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                self.learning.retract(one.observation_id,reason=reason)
        for identifier in (None,True,0,-1,1.5):
            with self.subTest(identifier=identifier),self.assertRaises(ValueError):
                self.learning.retract(identifier,reason="source_retracted")
        self.assertAlmostEqual(.02,self.learning.preference("observe"))

    def test_cannot_mix_other_sqlite_or_journal_instances(self):
        other=ExperienceMemory()
        self.addCleanup(other.close)
        other_journal=PassiveObservationJournal(other)
        with self.assertRaises(ValueError):
            self.learning.record(journal=other_journal,
                                 sequence=1,now_wall_epoch_s=WALL)
        with self.assertRaises(TypeError):
            self.learning.record(journal="not a journal",
                                 sequence=1,now_wall_epoch_s=WALL)
        brain=AutonomyBrain(other)
        with self.assertRaises(ValueError):
            brain.propose_balanced_passive(read(event()),
                journal=other_journal,learning=self.learning,
                now_monotonic_s=100.1,now_wall_epoch_s=WALL)

    def test_persists_between_independent_connections_and_monotonic_resets(self):
        self.write()
        self.mem.close()
        # The other connection restarts its journal and clock, but not SQLite.
        reopened=ExperienceMemory(self.db)
        try:
            second_journal=PassiveObservationJournal(reopened)
            second_learning=PassiveLearning(reopened)
            self.assertNotEqual(self.journal.session_id,second_journal.session_id)
            self.assertAlmostEqual(.02,second_learning.preference("observe"))
            r=read(event(mono=10.),seq=1,at=10.)
            self.assertEqual(1,second_journal.append(
                r,now_monotonic_s=10.1,now_wall_epoch_s=WALL+1))
            (outcome,)=second_learning.record(
                journal=second_journal,sequence=1,
                now_wall_epoch_s=WALL+1)
            self.assertEqual("repeated_observation",outcome.outcome)
            self.assertAlmostEqual(.015,second_learning.preference("observe"))
            self.assertEqual(0.,reopened.intent_preference("simulator","explore"))
        finally:
            reopened.close()

    def test_attention_bias_is_opt_in_and_motor_safety_is_unchanged(self):
        self.write()
        motives=Motivations(curiosity=.73,sociability=.5,
                            play=0.,energy=1.,caution=.5)
        no_learning=AutonomyBrain(self.mem,Motivations(**vars(motives)))
        with_learning=AutonomyBrain(self.mem,Motivations(**vars(motives)))
        fresh=read(event("dog",mono=101.),seq=2,at=101.)
        without=no_learning.propose_balanced_passive(
            fresh,journal=self.journal,
            now_monotonic_s=101.1,now_wall_epoch_s=WALL+1)
        with_bias=with_learning.propose_balanced_passive(
            fresh,journal=self.journal,learning=self.learning,
            now_monotonic_s=101.1,now_wall_epoch_s=WALL+1)
        self.assertEqual("idle",without.intention)
        self.assertEqual("observe",with_bias.intention)
        self.assertFalse(with_bias.executed)
        self.assertEqual(0,with_bias.motor_commands_issued)
        self.assertEqual("halt",with_learning.choose_from_snapshot(
            fresh.snapshot,now=101.1).intention)

    def test_learning_database_failure_remains_passive_and_does_not_add_energy(self):
        self.write()
        brain=AutonomyBrain(self.mem)
        before=brain.motives.energy
        self.mem.conn.execute("DROP TABLE passive_attention_preferences")
        outcome=brain.propose_balanced_passive(
            read(event("dog",mono=101.),seq=2,at=101.),
            journal=self.journal,learning=self.learning,
            now_monotonic_s=101.1,now_wall_epoch_s=WALL+1)
        self.assertEqual(("idle","learning_unavailable"),
                         (outcome.intention,outcome.reason))
        self.assertEqual(before,brain.motives.energy)

    def test_preference_is_bounded_and_reversible(self):
        for i in range(40):
            mono=100.+i
            self.write(seq=i+1,mono=mono,wall=WALL+i)
        self.assertAlmostEqual(-MAX_ATTENTION_BIAS,
                               self.learning.preference("observe"))
        count=self.mem.conn.execute(
            "SELECT COUNT(*) FROM passive_learning_events").fetchone()[0]
        self.assertEqual(40,count)
        # A historical correction can be represented without deleting the
        # original F1-C record or altering a simulated motor preference.
        ids=[e.observation_id for e in self.learning.history(limit=50)]
        for identifier in ids:
            self.assertTrue(self.learning.retract(
                identifier,reason="source_retracted"))
        self.assertAlmostEqual(0.,self.learning.preference("observe"))

    def test_invalid_clock_and_sequence_fail_before_learning(self):
        for clock in (True,-1,float("nan"),float("inf")):
            with self.subTest(clock=clock),self.assertRaises(ValueError):
                self.learning.record(journal=self.journal,sequence=1,
                                     now_wall_epoch_s=clock)
        for seq in (True,None,-1,2**63,"1"):
            with self.subTest(seq=seq),self.assertRaises(ValueError):
                self.learning.record(journal=self.journal,sequence=seq,
                                     now_wall_epoch_s=WALL)

    def test_empty_or_missing_category_never_changes_preference(self):
        self.assertEqual((),self.learning.record(
            journal=self.journal,sequence=999,now_wall_epoch_s=WALL))
        self.assertEqual(0.,self.learning.preference("observe"))
        self.assertEqual((),self.learning.history())


if __name__ == "__main__":
    unittest.main()
