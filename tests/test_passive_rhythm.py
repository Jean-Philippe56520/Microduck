"""F2-B: bounded mock-only rhythm, no motor, audio, model or real battery."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, Motivations, PassiveObservationJournal,
    PerceptionEvent, PerceptionSnapshot,
)
from microduck_companion.passive_demo import (
    _fictional_unix_server, _frame, _item,
)
from microduck_companion.passive_rhythm import (
    ATTENTION_COOLDOWN_S, MIN_CYCLE_GAP_S, PassiveRhythm, PassiveRhythmMetrics,
)
from microduck_companion.passive_sources import FixtureUnixReader, PassiveRead

WALL = 1_770_000_000.


def evt(category="ball", *, kind="object_label", mono=100., track="track-1",
        confidence=.96, source="mock", ttl=1.):
    return PerceptionEvent(
        kind, category, source, mono, ttl, confidence,
        track_id=track if kind == "object_label" else None,
    )


def receipt(*events, seq=1, at=100., status="ok",
            channel="mock_fixture_unix", environment="mock"):
    return PassiveRead(
        status, PerceptionSnapshot(environment, tuple(events), at),
        seq, channel,
    )


class RhythmTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)

    def pace(self, r, *, mono=100.1, wall=WALL):
        return self.brain.propose_balanced_passive(
            r, journal=self.journal,
            now_monotonic_s=mono, now_wall_epoch_s=wall,
        )

    def test_first_novel_mock_category_proposes_observe_only(self):
        answer = self.pace(receipt(evt()))
        self.assertEqual(("observe", "ball", "mock"),
                         (answer.intention, answer.target_category,
                          answer.source))
        self.assertFalse(answer.executed)
        self.assertEqual(0, answer.motor_commands_issued)
        self.assertFalse(answer.request_pc_analysis)
        self.assertEqual("halt", self.brain.choose_from_snapshot(
            receipt(evt()).snapshot, now=100.1).intention)

    def test_three_same_category_events_within_cooldown_do_not_repeat(self):
        first = self.pace(receipt(evt(), seq=1), mono=100.1)
        second = self.pace(receipt(evt(mono=101.), seq=2, at=101.),
                           mono=101.1)
        third = self.pace(receipt(evt(mono=102.), seq=3, at=102.),
                          mono=102.1)
        self.assertEqual(["observe", "idle", "idle"],
                         [x.intention for x in (first, second, third)])
        self.assertEqual("no_high_scoring_passive_attention", second.reason)
        metrics = self.brain.passive_rhythm_metrics()
        self.assertEqual(3, metrics.cycles)
        self.assertEqual(2, metrics.cooldown_blocks)
        self.assertEqual(0, metrics.consecutive_active_repeats)
        self.assertEqual(1, metrics.count("observe"))
        self.assertEqual(2, metrics.count("idle"))
        self.assertEqual(0, metrics.count("explore"))

    def test_cooldown_expires_without_physical_action(self):
        self.assertEqual("observe", self.pace(receipt(evt())).intention)
        t = 100.1 + ATTENTION_COOLDOWN_S + .1
        next_tick = self.pace(receipt(evt(mono=t-.1), seq=2, at=t-.1),
                              mono=t)
        self.assertEqual("observe", next_tick.intention)
        self.assertEqual(0, next_tick.motor_commands_issued)
        self.assertEqual(0, self.memory.experience_count())

    def test_different_object_categories_can_be_proposed(self):
        options = [("ball", 100., 1), ("dog", 101., 2), ("toy", 102., 3)]
        intentions = []
        for category, t, seq in options:
            decision = self.pace(receipt(evt(category, mono=t), seq=seq, at=t),
                                 mono=t+.1)
            intentions.append(decision.intention)
        self.assertEqual(["observe"]*3, intentions)
        metrics = self.brain.passive_rhythm_metrics()
        self.assertEqual(2, metrics.consecutive_active_repeats)
        self.assertEqual(3, metrics.count("observe"))
        self.assertLessEqual(len(metrics.recent_intentions), 32)

    def test_multiple_categories_select_highest_score_not_first_event(self):
        r = receipt(evt("dog", track="track-dog"),
                    evt("ball", track="track-ball"))
        one = self.pace(r)
        self.assertEqual(("observe", "ball"),
                         (one.intention, one.target_category))

    def test_familiar_category_in_sqlite_is_not_reannounced_as_new(self):
        r = receipt(evt("ball"))
        self.assertEqual(1, self.journal.append(
            r, now_monotonic_s=100.1, now_wall_epoch_s=WALL))
        decision = self.pace(receipt(evt("ball", track="track-another"), seq=2))
        self.assertEqual("idle", decision.intention)
        self.assertIsNone(decision.target_category)
        self.assertIsNone(self.memory.get("track-another"))

    def test_unknown_current_object_proposes_inspect_then_cooldown_idle(self):
        first = self.pace(receipt(evt("unknown")))
        second = self.pace(receipt(evt("unknown", mono=101.), seq=2, at=101.),
                           mono=101.1)
        self.assertEqual(("inspect", "unknown"),
                         (first.intention, first.target_category))
        self.assertEqual("idle", second.intention)

    def test_conflict_remains_unknown_without_identity(self):
        conflicting = receipt(evt("ball"), evt("toy"))
        plan = self.pace(conflicting)
        self.assertEqual(("inspect", "unknown"),
                         (plan.intention, plan.target_category))
        self.assertNotIn("track-1", repr(plan))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "ball", now_wall_epoch_s=WALL))

    def test_audio_is_just_a_label_never_a_microphone_capture(self):
        plan = self.pace(receipt(evt("knock", kind="sound_label")))
        self.assertEqual(("listen", "knock"),
                         (plan.intention, plan.target_category))
        self.assertEqual(0, plan.motor_commands_issued)
        self.assertFalse(plan.executed)

    def test_different_audio_categories_can_be_proposed(self):
        first = self.pace(receipt(evt("bark", kind="sound_label")))
        second = self.pace(receipt(evt("meow", kind="sound_label",
                                       mono=101.), seq=2, at=101.),
                           mono=101.1)
        self.assertEqual(["listen", "listen"],
                         [first.intention, second.intention])

    def test_caution_dominates_motivation_and_allows_idle(self):
        self.brain.motives.caution = .99
        self.assertEqual("idle", self.pace(receipt(evt("ball"))).intention)

    def test_no_curiosity_no_play_can_choose_idle_for_object(self):
        self.brain.motives.curiosity = 0.
        self.brain.motives.play = 0.
        self.brain.motives.caution = 0.
        self.assertEqual("idle", self.pace(receipt(evt("ball"))).intention)

    def test_no_sociability_chooses_idle_for_sound(self):
        self.brain.motives.sociability = 0.
        self.brain.motives.caution = 0.
        self.assertEqual("idle", self.pace(receipt(
            evt("meow", kind="sound_label"))).intention)

    def test_play_prefers_toy_over_non_toy_without_action(self):
        self.brain.motives.curiosity = .35
        self.brain.motives.play = 1.
        self.brain.motives.caution = .2
        self.brain.motives.energy = 1.
        results = self.pace(receipt(
            evt("dog", track="track-dog"),
            evt("toy", track="track-toy")))
        self.assertEqual(("observe", "toy"),
                         (results.intention, results.target_category))
        self.assertFalse(results.executed)

    def test_low_simulated_energy_enters_rest_with_hysteresis(self):
        self.brain.motives.energy = .2
        intents, energies = [], []
        for i in range(6):
            t = 100. + i
            answer = self.pace(
                receipt(evt("ball", mono=t), seq=i+1, at=t),
                mono=t+.1,
            )
            intents.append(answer.intention)
            energies.append(self.brain.motives.energy)
        self.assertEqual(["rest", "rest", "rest", "rest", "observe", "idle"],
                         intents)
        self.assertGreaterEqual(energies[3], .34 - 1e-9)
        self.assertGreater(energies[4], .2)
        self.assertLess(energies[4], energies[3])
        self.assertEqual(0, self.memory.experience_count())

    def test_rest_never_fakes_battery_measurement_or_execution(self):
        self.brain.motives.energy = .1
        answer = self.pace(receipt(evt("dog")))
        self.assertEqual("rest", answer.intention)
        self.assertEqual("simulated_energy_recovery_hysteresis", answer.reason)
        self.assertFalse(answer.executed)
        self.assertEqual(0, answer.motor_commands_issued)
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM intent_preferences").fetchone()[0])

    def test_source_loss_during_rest_does_not_recharge(self):
        self.brain.motives.energy = .15
        self.assertEqual("rest", self.pace(receipt(evt("dog"))).intention)
        energy = self.brain.motives.energy
        failed = receipt(evt("dog", mono=101.), seq=2, at=101.,
                         status="unavailable_or_invalid")
        outcome = self.pace(failed, mono=101.1)
        self.assertEqual("idle", outcome.intention)
        self.assertEqual("source_unavailable", outcome.reason)
        self.assertEqual(energy, self.brain.motives.energy)
        third = receipt(evt("dog", mono=102.), seq=3, at=102.)
        self.assertEqual("rest", self.pace(third, mono=102.1).intention)

    def test_rate_limit_returns_idle_and_does_not_change_energy(self):
        self.assertEqual("observe", self.pace(receipt(evt())).intention)
        energy = self.brain.motives.energy
        earlier = receipt(evt(mono=100.2), seq=2, at=100.2)
        outcome = self.pace(earlier, mono=100.2)
        self.assertEqual(("idle", "cycle_rate_limited"),
                         (outcome.intention, outcome.reason))
        self.assertEqual(energy, self.brain.motives.energy)
        self.assertEqual(1, self.brain.passive_rhythm_metrics().count("observe"))
        later = receipt(evt("dog", mono=100.7), seq=2, at=100.7)
        self.assertEqual("observe", self.pace(later, mono=100.7).intention)

    def test_duplicate_source_sequence_cannot_schedule_again(self):
        self.assertEqual("observe", self.pace(receipt(evt(), seq=8)).intention)
        next_tick = receipt(evt("toy", mono=101.), seq=8, at=101.)
        result = self.pace(next_tick, mono=101.1)
        self.assertEqual(("idle", "duplicate_source_sequence"),
                         (result.intention, result.reason))

    def test_clock_reset_requires_fresh_next_read_and_clears_cooldown(self):
        self.assertEqual("observe", self.pace(receipt(evt())).intention)
        reset = receipt(evt("ball", mono=50.), seq=1, at=50.)
        result = self.pace(reset, mono=50.1)
        self.assertEqual(("idle", "clock_reset_requires_new_read"),
                         (result.intention, result.reason))
        next_read = receipt(evt("ball", mono=51.), seq=1, at=51.)
        self.assertEqual("observe", self.pace(next_read, mono=51.1).intention)

    def test_untrusted_channel_robot_source_or_safety_event_fail_closed(self):
        inputs = (
            receipt(evt("ball"), channel="oem_media_hello_only"),
            receipt(evt("ball"), environment="robot"),
            receipt(evt("ball", source="sensor")),
            receipt(PerceptionEvent("floor_clear", True, "mock", 100., 1., 1.)),
            receipt(evt("ball"), status="clock_reset"),
        )
        for i, r in enumerate(inputs):
            with self.subTest(i=i):
                brain = AutonomyBrain(self.memory)
                decision = brain.propose_balanced_passive(
                    r, journal=self.journal,
                    now_monotonic_s=100.1,
                    now_wall_epoch_s=WALL,
                )
                self.assertEqual("idle", decision.intention)
                self.assertEqual(0, decision.motor_commands_issued)

    def test_stale_or_low_confidence_do_not_get_promoted(self):
        for r in (
            receipt(evt(mono=98.), at=98.),
            receipt(evt(mono=101.), at=101.),
            receipt(evt(confidence=.3)),
            receipt(evt("meow", kind="sound_label", confidence=.3)),
        ):
            with self.subTest(r=r):
                brain = AutonomyBrain(self.memory)
                d = brain.propose_balanced_passive(
                    r, journal=self.journal, now_monotonic_s=100.1,
                    now_wall_epoch_s=WALL,
                )
                self.assertEqual("idle", d.intention)

    def test_invalid_motivation_state_cannot_schedule_or_consume_energy(self):
        old = self.brain.motives.caution
        self.brain.motives.caution = float("nan")
        try:
            answer = self.pace(receipt(evt()))
            self.assertEqual(("idle", "invalid_motivations"),
                             (answer.intention, answer.reason))
            self.assertEqual(.8, self.brain.motives.energy)
        finally:
            self.brain.motives.caution = old

    def test_bad_timestamps_refused_and_no_metrics(self):
        for invalid in (True, -1, float("nan"), float("inf"), "bad"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.pace(receipt(evt()), mono=invalid)
        self.assertEqual(0, self.brain.passive_rhythm_metrics().cycles)

    def test_no_second_brain_or_other_sqlite_is_permitted(self):
        another = ExperienceMemory()
        self.addCleanup(another.close)
        other_journal = PassiveObservationJournal(another)
        with self.assertRaises(ValueError):
            self.brain.propose_balanced_passive(
                receipt(evt()), journal=other_journal,
                now_monotonic_s=100.1, now_wall_epoch_s=WALL,
            )
        with self.assertRaises(TypeError):
            self.brain.propose_balanced_passive(
                receipt(evt()), journal="not a journal",
                now_monotonic_s=100.1, now_wall_epoch_s=WALL,
            )

    def test_proposals_do_not_modify_object_memory_rewards_or_experiences(self):
        sequence = [
            receipt(evt("ball")),
            receipt(evt("knock", kind="sound_label", mono=101.),
                    seq=2, at=101.),
            receipt(evt("unknown", mono=102.), seq=3, at=102.),
        ]
        for i, r in enumerate(sequence):
            self.pace(r, mono=100.1+i)
        for table in ("objects", "experiences", "sim_motion_trials",
                      "intent_preferences", "passive_observation_log"):
            self.assertEqual(0, self.memory.conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        self.assertIsNone(self.brain.previous_intention)
        self.assertNotEqual(.8, self.brain.motives.energy)

    def test_history_and_cooldown_only_contain_category_names(self):
        self.pace(receipt(evt("Malo", track="track-identity")))
        state = self.brain._passive_rhythm
        self.assertIsNotNone(state)
        self.assertFalse(any("track-" in str(v) or "Malo" in str(v)
                             for v in state._cooldown_until))
        self.assertNotIn("Malo", str(self.brain.passive_rhythm_metrics()))

    def test_metrics_are_bounded_to_last_32_proposals(self):
        for i in range(40):
            t = 100. + i
            self.pace(receipt(seq=i+1, at=t), mono=t+.1)
        m = self.brain.passive_rhythm_metrics()
        self.assertIsInstance(m, PassiveRhythmMetrics)
        self.assertEqual(40, m.cycles)
        self.assertEqual(32, len(m.recent_intentions))
        self.assertEqual(40, sum(v for _, v in m.counts))
        self.assertGreaterEqual(m.count("idle"), 35)
        self.assertEqual(0, m.count("explore"))

    def test_independent_brains_have_independent_cooldowns(self):
        first = self.pace(receipt(evt("ball")))
        other = AutonomyBrain(self.memory)
        second = other.propose_balanced_passive(
            receipt(evt("ball")), journal=self.journal,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL,
        )
        self.assertEqual(("observe", "observe"),
                         (first.intention, second.intention))
        self.assertEqual(1, self.brain.passive_rhythm_metrics().cycles)
        self.assertEqual(1, other.passive_rhythm_metrics().cycles)


@unittest.skipUnless(hasattr(socket, "AF_UNIX"), "requires synthetic Unix IPC")
class UnixFixtureTests(unittest.TestCase):
    def test_five_real_unix_fixture_reads_have_no_motor_or_media_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "fake-memory.sqlite3"
            sock = Path(folder) / "fake.sock"
            mem = ExperienceMemory(db)
            try:
                journal = PassiveObservationJournal(mem)
                brain = AutonomyBrain(mem)
                moments = [100.1, 101.1, 102.1, 103.1, 104.1]
                replies = (
                    _frame(1, 100., _item("ball")),
                    _frame(2, 101., _item("ball")),
                    _frame(3, 102., _item("unknown")),
                    _frame(4, 103., _item("knock", kind="sound_label")),
                    b"",  # Fake local source disconnected
                )
                clock = [moments[0]]
                outcomes = []
                with _fictional_unix_server(sock, replies):
                    reader = FixtureUnixReader(sock, clock=lambda: clock[0])
                    for i, mono in enumerate(moments):
                        clock[0] = mono
                        r = reader.read()
                        proposal = brain.propose_balanced_passive(
                            r, journal=journal, now_monotonic_s=mono,
                            now_wall_epoch_s=WALL+i,
                        )
                        journal.append(
                            r, now_monotonic_s=mono, now_wall_epoch_s=WALL+i,
                        )
                        safety = brain.choose_from_snapshot(r.snapshot, now=mono)
                        outcomes.append((proposal.intention, safety.intention))
                self.assertEqual(
                    [("observe", "halt"), ("idle", "halt"),
                     ("inspect", "halt"), ("listen", "halt"),
                     ("idle", "halt")],
                    outcomes,
                )
                self.assertEqual(4, len(journal.recent(
                    now_wall_epoch_s=WALL+5)))
                metrics = brain.passive_rhythm_metrics()
                self.assertEqual(5, metrics.cycles)
                self.assertEqual(0, metrics.consecutive_active_repeats)
                self.assertEqual(0, mem.conn.execute(
                    "SELECT COUNT(*) FROM objects").fetchone()[0])
                self.assertEqual(0, mem.conn.execute(
                    "SELECT COUNT(*) FROM intent_preferences").fetchone()[0])
            finally:
                mem.close()

    def test_process_restart_keeps_category_memory_but_resets_cooldowns(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "fictional-memory.sqlite3"
            mem = ExperienceMemory(db)
            try:
                journal = PassiveObservationJournal(mem)
                r = receipt(evt("ball"))
                journal.append(r, now_monotonic_s=100.1,
                               now_wall_epoch_s=WALL)
                # Only journal is durable. The per-brain rhythm state is not.
                brain = AutonomyBrain(mem)
                first = brain.propose_balanced_passive(
                    receipt(evt("unknown")),
                    journal=journal, now_monotonic_s=100.1,
                    now_wall_epoch_s=WALL,
                )
                self.assertEqual("inspect", first.intention)
            finally:
                mem.close()
            code = """
import json,sys
from microduck_companion import AutonomyBrain,ExperienceMemory,PassiveObservationJournal,PerceptionEvent,PerceptionSnapshot
from microduck_companion.passive_sources import PassiveRead
db,wall=sys.argv[1],float(sys.argv[2])
memory=ExperienceMemory(db)
journal=PassiveObservationJournal(memory)
brain=AutonomyBrain(memory)
event=PerceptionEvent('object_label','ball','mock',10.,1.,.95,track_id='track-new')
receipt=PassiveRead('ok',PerceptionSnapshot('mock',(event,),10.),1)
plan=brain.propose_balanced_passive(receipt,journal=journal,
    now_monotonic_s=10.1,now_wall_epoch_s=wall)
metrics=brain.passive_rhythm_metrics()
print(json.dumps({'intent':plan.intention,'cycles':metrics.cycles,
                  'energy':metrics.simulated_motivation_energy,
                  'historical':journal.category_count(
                     'object_label','ball',now_wall_epoch_s=wall),
                  'action_rows':memory.conn.execute(
                     'SELECT count(*) FROM experiences').fetchone()[0]}))
memory.close()
"""
            proc = subprocess.run(
                [sys.executable, "-c", code, str(db), str(WALL+1)],
                capture_output=True, text=True, check=True, timeout=12,
            )
            result = json.loads(proc.stdout)
            self.assertEqual(("idle", 1, 1, 0),
                             (result["intent"], result["cycles"],
                              result["historical"], result["action_rows"]))


if __name__ == "__main__":
    unittest.main()
