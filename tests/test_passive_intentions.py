"""F2-A: non-motor proposals from fictional current categories and past SQLite.

These assertions deliberately separate cognition ("observe"/"listen") from
physical action ("halt" in the existing safety path). Every fixture is mock.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, Motivations, PassiveObservationJournal,
    PassiveIntent, PerceptionEvent, PerceptionSnapshot,
)
from microduck_companion.passive_demo import _fictional_unix_server, _frame, _item
from microduck_companion.passive_intentions import propose_passive_intention
from microduck_companion.passive_sources import FixtureUnixReader, PassiveRead

WALL = 1_770_000_000.0


def event(category="ball", *, kind="object_label", mono=100.0,
          confidence=.96, ttl=1., source="mock", track="track-fixture"):
    return PerceptionEvent(
        kind, category, source, mono, ttl, confidence,
        track_id=track if kind == "object_label" else None,
    )


def reading(*events, seq=1, environment="mock", at=100.,
            status="ok", channel="mock_fixture_unix"):
    return PassiveRead(
        status, PerceptionSnapshot(environment, tuple(events), at),
        seq, channel,
    )


class PassiveIntentionUnitTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)
        self.now = 100.1

    def propose(self, receipt, *, now=None, wall=WALL):
        return self.brain.propose_passive(
            receipt, journal=self.journal,
            now_monotonic_s=self.now if now is None else now,
            now_wall_epoch_s=wall,
        )

    def save(self, receipt, *, now=None, wall=WALL):
        return self.journal.append(
            receipt,
            now_monotonic_s=self.now if now is None else now,
            now_wall_epoch_s=wall,
        )

    def test_new_object_proposes_observe_with_no_motor(self):
        receipt = reading(event())
        answer = self.propose(receipt)
        self.assertEqual(("observe", "object_label", "ball"),
                         (answer.intention, answer.target_kind,
                          answer.target_category))
        self.assertEqual("mock", answer.source)
        self.assertFalse(answer.executed)
        self.assertEqual(0, answer.motor_commands_issued)
        self.assertFalse(answer.request_pc_analysis)

    def test_repeated_category_becomes_idle_not_repeat_or_identity(self):
        old = reading(event())
        first = self.propose(old)
        self.assertEqual("observe", first.intention)
        self.assertEqual(1, self.save(old))
        later = reading(event(track="track-another"), seq=2)
        repeat = self.propose(later)
        self.assertEqual("idle", repeat.intention)
        self.assertIsNone(repeat.target_category)
        self.assertEqual("no_new_safe_passive_attention", repeat.reason)
        self.assertIsNone(self.memory.get("track-another"))

    def test_unknown_object_proposes_inspect_cognitive_only(self):
        result = self.propose(reading(event("unknown")))
        self.assertEqual(("inspect", "object_label", "unknown"),
                         (result.intention, result.target_kind,
                          result.target_category))
        self.assertEqual("unresolved_fictional_object_category", result.reason)
        self.assertFalse(result.executed)

    def test_conflicting_labels_never_choose_one_and_propose_inspect(self):
        result = self.propose(reading(event("ball"), event("toy")))
        self.assertEqual(("inspect", "unknown"),
                         (result.intention, result.target_category))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "ball", now_wall_epoch_s=WALL))

    def test_sound_proposes_listen_without_microphone_or_transcript(self):
        result = self.propose(reading(event("knock", kind="sound_label")))
        self.assertEqual(("listen", "sound_label", "knock"),
                         (result.intention, result.target_kind,
                          result.target_category))
        self.assertFalse(result.executed)

    def test_ambiguous_sound_only_proposes_listen_not_identity(self):
        result = self.propose(reading(
            event("bark", kind="sound_label"),
            event("meow", kind="sound_label"),
        ))
        self.assertEqual(("listen", "unknown"),
                         (result.intention, result.target_category))
        self.assertFalse(result.request_pc_analysis)

    def test_keyword_stop_is_not_hardware_emergency_stop(self):
        receipt = reading(event("keyword_stop", kind="sound_label"))
        answer = self.propose(receipt)
        self.assertEqual("listen", answer.intention)
        self.assertEqual(0, answer.motor_commands_issued)
        # The independent safety path still halts due to missing floor, ToF,
        # safe zone, and actual battery measurements.
        safe = self.brain.choose_from_snapshot(receipt.snapshot, now=100.1)
        self.assertEqual("halt", safe.intention)

    def test_priority_unresolved_object_before_sound_before_new_object(self):
        both = reading(
            event("dog", track="track-dog"),
            event("knock", kind="sound_label"),
        )
        self.assertEqual("listen", self.propose(both).intention)
        triple = reading(
            event("unknown", track="track-unknown"),
            event("knock", kind="sound_label"),
            event("dog", track="track-dog"),
        )
        self.assertEqual("inspect", self.propose(triple).intention)

    def test_empty_valid_receipt_is_idle(self):
        self.assertEqual("no_current_observation",
                         self.propose(reading()).reason)

    def test_all_source_failure_states_are_idle_and_do_not_replay_memory(self):
        good = reading(event("ball"))
        self.assertEqual(1, self.save(good))
        for state in (
            "unavailable_or_invalid", "rate_limited", "clock_reset",
            "duplicate_or_out_of_order", "invented_state",
        ):
            with self.subTest(state=state):
                forged = reading(
                    event("unknown"), seq=2, status=state,
                )
                answer = self.propose(forged)
                self.assertEqual("idle", answer.intention)
                self.assertIsNone(answer.target_category)
                self.assertFalse(answer.executed)
        self.assertEqual(1, len(self.journal.recent(now_wall_epoch_s=WALL)))

    def test_missing_sensor_and_wrong_channel_fail_closed(self):
        invalids = (
            reading(event("ball"), channel="oem_media_hello_only"),
            reading(event("ball"), channel="robotd"),
            reading(event("ball"), environment="robot"),
            reading(event("ball", source="llm_suggestion")),
            reading(event("ball", source="sensor")),
            reading(event("ball"), seq=None),
            reading(event("ball"), seq=-1),
        )
        for i, receipt in enumerate(invalids):
            with self.subTest(i=i):
                self.assertEqual("idle", self.propose(receipt).intention)

    def test_fake_safety_event_is_ignored_without_promoting_clearance(self):
        forged = reading(
            PerceptionEvent("floor_clear", True, "mock", 100., 1., 1.),
            PerceptionEvent("safe_area", True, "mock", 100., 1., 1.),
            event("ball"),
        )
        self.assertEqual("idle", self.propose(forged).intention)
        self.assertEqual("untrusted_or_nonpassive_event",
                         self.propose(forged).reason)

    def test_stale_future_untrusted_are_idle_not_current_sensing(self):
        stale = reading(event("ball", mono=98.), at=98.)
        self.assertEqual("idle", self.propose(stale).intention)
        future = reading(event("ball", mono=101.), at=101.)
        self.assertEqual("idle", self.propose(future).intention)
        old = reading(event("dog"))
        self.save(old)
        self.assertEqual("idle", self.propose(
            reading(event("dog", mono=90.), at=90.)
        ).intention)

    def test_low_confidence_never_proposes_inspection(self):
        self.assertEqual("idle", self.propose(
            reading(event("ball", confidence=.4))
        ).intention)
        self.assertEqual("idle", self.propose(
            reading(event("meow", kind="sound_label", confidence=.3))
        ).intention)

    def test_no_privacy_identifiers_or_hypothetical_person_names_in_plan(self):
        receipt = reading(event("Malo", track="track-identity"))
        proposed = self.propose(receipt)
        self.assertEqual("inspect", proposed.intention)
        self.assertEqual("unknown", proposed.target_category)
        self.assertNotIn("Malo", str(proposed))
        self.assertNotIn("track-identity", str(proposed))

    def test_lower_curiosity_and_sociability_can_choose_idle(self):
        self.brain.motives.curiosity = .1
        self.brain.motives.sociability = .1
        self.assertEqual("idle", self.propose(reading(event())).intention)
        self.assertEqual("idle", self.propose(
            reading(event("unknown"))).intention)
        self.assertEqual("idle", self.propose(
            reading(event("meow", kind="sound_label"))).intention)

    def test_rest_uses_only_simulated_motivational_energy_not_battery(self):
        self.brain.motives.energy = .15
        proposal = self.propose(reading(event("dog")))
        self.assertEqual("rest", proposal.intention)
        self.assertEqual("low_simulated_motivational_energy", proposal.reason)
        self.assertIsNone(proposal.target_category)
        self.assertFalse(proposal.executed)
        # Data lost takes precedence over an unverified energy state.
        bad = reading(event("dog"), status="unavailable_or_invalid")
        self.assertEqual("idle", self.propose(bad).intention)

    def test_invalid_motivations_fail_closed_without_mutating(self):
        for attr, invalid in (("energy", float("nan")),
                              ("curiosity", float("inf")),
                              ("sociability", -1.),
                              ("play", True)):
            original = getattr(self.brain.motives, attr)
            try:
                setattr(self.brain.motives, attr, invalid)
                answer = self.propose(reading(event("dog")))
                self.assertEqual(("idle", "invalid_motivations"),
                                 (answer.intention, answer.reason))
            finally:
                setattr(self.brain.motives, attr, original)

    def test_brain_proposal_does_not_log_executed_action_or_change_motivations(self):
        receipt = reading(event("ball"))
        before = self.brain.motives.__dict__.copy()
        for _ in range(3):
            answer = self.propose(receipt)
            self.assertEqual("observe", answer.intention)
        self.assertEqual(before, self.brain.motives.__dict__)
        self.assertIsNone(self.brain.previous_intention)
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM experiences").fetchone()[0])
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM passive_observation_log").fetchone()[0])
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM intent_preferences").fetchone()[0])

    def test_journal_of_uncertain_category_not_counted_as_familiar(self):
        self.save(reading(event("unknown")))
        answer = self.propose(reading(event("ball"), seq=2))
        self.assertEqual("observe", answer.intention)

    def test_malformed_snapshot_and_large_batch_fail_closed(self):
        fake = PassiveRead("ok", "forged", 1)
        self.assertEqual("invalid_snapshot", self.propose(fake).reason)
        many = tuple(event("ball", track=f"track-{i}")
                     for i in range(65))
        answer = self.propose(reading(*many))
        self.assertEqual(("idle", "invalid_observation_batch"),
                         (answer.intention, answer.reason))

    def test_bad_clocks_rejected_without_action(self):
        receipt = reading(event())
        for value in (True, -1, float("nan"), float("inf"), "no clock"):
            with self.subTest(v=repr(value)):
                with self.assertRaises(ValueError):
                    self.brain.propose_passive(
                        receipt, journal=self.journal,
                        now_monotonic_s=value, now_wall_epoch_s=WALL,
                    )
                with self.assertRaises(ValueError):
                    self.brain.propose_passive(
                        receipt, journal=self.journal,
                        now_monotonic_s=100.1, now_wall_epoch_s=value,
                    )

    def test_memory_must_be_same_brain_and_journal_instance(self):
        other = ExperienceMemory()
        self.addCleanup(other.close)
        other_journal = PassiveObservationJournal(other)
        with self.assertRaises(ValueError):
            self.brain.propose_passive(
                reading(event()), journal=other_journal,
                now_monotonic_s=100.1, now_wall_epoch_s=WALL,
            )
        with self.assertRaises(TypeError):
            self.brain.propose_passive(
                reading(event()), journal="another database",
                now_monotonic_s=100.1, now_wall_epoch_s=WALL,
            )

    def test_sqlite_unavailable_fails_closed(self):
        receipt = reading(event("toy"))
        self.memory.close()
        answer = self.propose(receipt)
        self.assertEqual(("idle", "history_unavailable"),
                         (answer.intention, answer.reason))

    def test_invalid_passive_result_rejects_motor_execution(self):
        for kwargs in (
            {"intention": "explore", "reason": "movement"},
            {"intention": "look_at_person", "reason": "movement"},
            {"intention": "observe", "reason": "fake", "executed": True},
            {"intention": "listen", "reason": "fake", "motor_commands_issued": 1},
            {"intention": "inspect", "reason": "fake", "request_pc_analysis": True},
            {"intention": "idle", "reason": "fake", "source": "sensor"},
            {"intention": "observe", "reason": "fake",
             "target_kind": "object_label", "target_category": "Malo"},
            {"intention": "rest", "reason": "fake",
             "target_kind": "object_label", "target_category": "dog"},
            {"intention": "listen", "reason": "fake",
             "target_kind": "object_label", "target_category": "ball"},
            {"intention": "inspect", "reason": "fake",
             "target_kind": "sound_label", "target_category": "speech"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PassiveIntent(**kwargs)


@unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix fixture required")
class FixtureIntegrationTests(unittest.TestCase):
    def test_real_unix_fixture_to_existing_brain_and_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fake.sock"
            db = Path(folder) / "categories.sqlite3"
            frames = (
                _frame(1, 100., _item("ball")),
                _frame(2, 101., _item("ball")),
                _frame(3, 102., _item("unknown")),
                _frame(4, 103., _item("knock", kind="sound_label")),
                b"",  # Disconnection in the actual fake Unix socket
            )
            moments = [100.1, 101.1, 102.1, 103.1, 104.1]
            with _memory_context(db) as mem:
                brain = AutonomyBrain(mem)
                journal = PassiveObservationJournal(mem)
                clock = [moments[0]]
                with _fictional_unix_server(path, frames):
                    reader = FixtureUnixReader(path, clock=lambda: clock[0])
                    results = []
                    for idx, mono in enumerate(moments):
                        clock[0] = mono
                        current = reader.read()
                        decision = brain.propose_passive(
                            current, journal=journal,
                            now_monotonic_s=mono, now_wall_epoch_s=WALL+idx,
                        )
                        journal.append(
                            current, now_monotonic_s=mono,
                            now_wall_epoch_s=WALL+idx,
                        )
                        # The independent safety path never permits movement.
                        safety = brain.choose_from_snapshot(
                            current.snapshot, now=mono,
                        )
                        results.append((decision.intention, safety.intention))
                self.assertEqual(
                    [("observe", "halt"), ("idle", "halt"),
                     ("inspect", "halt"), ("listen", "halt"),
                     ("idle", "halt")],
                    results,
                )
                self.assertEqual(4, len(journal.recent(now_wall_epoch_s=WALL+5)))
                self.assertEqual(0, mem.conn.execute(
                    "SELECT COUNT(*) FROM objects").fetchone()[0])

    def test_new_process_uses_historical_category_not_old_live_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "categories.sqlite3"
            mem = ExperienceMemory(db)
            journal = PassiveObservationJournal(mem)
            initial = reading(event("ball"))
            self.assertEqual(1, journal.append(
                initial, now_monotonic_s=100.1, now_wall_epoch_s=WALL,
            ))
            mem.close()
            code = """
import json,sys
from microduck_companion import AutonomyBrain,ExperienceMemory,PerceptionEvent,PerceptionSnapshot,PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
db,wall=sys.argv[1],float(sys.argv[2])
memory=ExperienceMemory(db)
journal=PassiveObservationJournal(memory)
brain=AutonomyBrain(memory)
event=PerceptionEvent('object_label','ball','mock',10.,1.,.95,track_id='track-new-session')
receipt=PassiveRead('ok',PerceptionSnapshot('mock',(event,),10.),1)
result=brain.propose_passive(receipt,journal=journal,
    now_monotonic_s=10.1,now_wall_epoch_s=wall)
print(json.dumps({'intent':result.intention,'reason':result.reason,
                  'actions':memory.conn.execute('SELECT count(*) FROM experiences').fetchone()[0],
                  'history':journal.category_count('object_label','ball',now_wall_epoch_s=wall)}))
memory.close()
"""
            proc = subprocess.run(
                [sys.executable, "-c", code, str(db), str(WALL+1)],
                capture_output=True, text=True, timeout=12, check=True,
            )
            result = json.loads(proc.stdout)
            self.assertEqual(("idle", "no_new_safe_passive_attention", 1, 0),
                             (result["intent"], result["reason"],
                              result["history"], result["actions"]))


class _memory_context:
    """Test-only context; ExperienceMemory does not implement __enter__."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.memory = ExperienceMemory(self.path)
        return self.memory

    def __exit__(self, *_):
        self.memory.close()


if __name__ == "__main__":
    unittest.main()
