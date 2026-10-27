"""Integration acceptance of Kwipi's existing F1/F2/EX1-3/PD2/PD3 mock path.

This is NOT a MuJoCo run, a real sensor, a physical motor receipt or an
independent audio/vision benchmark. Do not promote these results to hardware.
No second controller, SQLite or LLM client is instantiated.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.behavior_continuity import MockBehaviorSituation
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_effects import (
    MockCue, MockEffectJournal, MockEffectPair,
)
from microduck_companion.experience_expectations import MockAttentionTrends
from microduck_companion.experience_ledger import (
    MockExperienceLedger, MockResolution,
)
from microduck_companion.kwipi_journal import read_journal
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.pc_hypothesis_contract import start_optional_pc_cycle
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.semantic_pc_opportunity import assess_mock_pc_opportunity

WALL = 1_780_000_000.0


def mock_read(category: str, *, at: float, seq: int,
              channel: str = "mock_fixture_unix") -> PassiveRead:
    event = PerceptionEvent(
        "object_label", category, "mock", at, 1.0, .95,
        track_id="fiction-track",
    )
    return PassiveRead(
        "ok", PerceptionSnapshot("mock", (event,), at), seq, channel,
    )


class KwipiIntegratedHostAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "single.sqlite3"
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.brain = AutonomyBrain(self.memory)
        self.journal = PassiveObservationJournal(self.memory)
        self.ledger = MockExperienceLedger(self.memory)
        self.effects = MockEffectJournal(self.ledger)
        self.trends = MockAttentionTrends(self.effects)

    def effect(self, session: str, *, at: float,
               status: str = "mock_executed") -> None:
        from microduck_companion.passive_intentions import PassiveIntent

        proposal = PassiveIntent(
            "observe", "scripted category", "object_label", "ball",
        )
        self.assertTrue(self.ledger.record_proposal(
            proposal, session=session, sequence=1, proposed_at_epoch_s=at,
        ))
        self.assertTrue(self.ledger.resolve(
            MockResolution(session, 1, status, at + 1),
        ))
        if status == "mock_executed":
            self.assertTrue(self.effects.record(MockEffectPair(
                session, 1,
                MockCue("motion", "still", at - .5, .95),
                MockCue("motion", "moving", at + 1.2, .95),
                True, False,
            )))

    def test_mock_perception_memory_experience_and_journal_one_sqlite(self):
        receipt = mock_read("ball", at=100., seq=1)
        selected = self.brain.propose_passive(
            receipt, journal=self.journal,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL,
        )
        self.assertEqual(("observe", "ball"),
                         (selected.intention, selected.target_category))
        self.assertFalse(selected.executed)

        portrait = self.brain.describe_behavior(
            selected, journal=self.journal, now_wall_epoch_s=WALL,
        )
        displayed = self.brain.describe_behavior_continuity(
            portrait, situation=MockBehaviorSituation(), now_monotonic_s=100.1,
        )
        self.assertEqual(("LookAround", "LookAround"),
                         (portrait.state, displayed.state))
        self.assertFalse(displayed.physical_execution_authorized)

        session = "s-0000000000000001"
        self.assertTrue(self.ledger.record_proposal(
            selected, session=session, sequence=1, proposed_at_epoch_s=WALL,
        ))
        # A proposal alone is not a physical or fictional execution receipt.
        (unresolved,) = self.ledger.history(now_wall_epoch_s=WALL + .1)
        self.assertEqual("proposed", unresolved.status)
        self.assertFalse(unresolved.verified_on_robot)
        self.assertTrue(self.ledger.resolve(
            MockResolution(session, 1, "mock_executed", WALL + 1),
        ))
        self.assertTrue(self.effects.record(MockEffectPair(
            session, 1,
            MockCue("motion", "still", WALL - .5, .95),
            MockCue("motion", "moving", WALL + 1.2, .95),
            True, False,
        )))
        self.assertIs(self.ledger._memory, self.memory)
        self.assertIs(self.effects._memory, self.memory)
        self.assertIs(self.trends._memory, self.memory)
        self.assertIs(self.journal._memory, self.memory)

        (effect,) = self.effects.history(now_wall_epoch_s=WALL + 2)
        self.assertEqual(("changed", "temporal_only"),
                         (effect.effect_status, effect.association_status))
        self.assertFalse(effect.causality_established)
        (history,) = read_journal(self.db, now_wall_epoch_s=WALL + 2)
        self.assertEqual(("mock_executed", "temporal_only"),
                         (history["status"], history["association_status"]))
        self.assertFalse(history["verified_on_robot"])
        self.assertFalse(history["causality_established"])

        self.assertEqual(1, self.journal.append(
            receipt, now_monotonic_s=100.1, now_wall_epoch_s=WALL + 2,
        ))
        later = mock_read("ball", at=104., seq=2)
        again = self.brain.propose_passive(
            later, journal=self.journal,
            now_monotonic_s=104.1, now_wall_epoch_s=WALL + 4,
        )
        self.assertEqual("idle", again.intention)
        self.assertEqual(0., self.trends.summary(
            intention="observe", category="ball",
            now_wall_epoch_s=WALL + 20,
        ).attention_bias)
        # Neither EX1/EX2 nor F2's mock receipt writes legacy reward tables.
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0., self.memory.intent_preference("robot", "explore"))

    def test_three_scripted_sessions_make_only_reversible_mock_bias(self):
        for i in (1, 2, 3):
            self.effect("s-" + format(i, "016x"), at=WALL + 10 * i)
        trend = self.trends.summary(
            intention="observe", category="ball", now_wall_epoch_s=WALL + 50,
        )
        self.assertEqual(3, trend.distinct_mock_sessions)
        self.assertEqual(.03, trend.attention_bias)
        self.assertFalse(trend.causality_established)
        self.assertFalse(trend.verified_on_robot)

        self.assertTrue(self.ledger.retract(
            session="s-0000000000000001", sequence=1,
            reason="source_retracted",
        ))
        after = self.trends.summary(
            intention="observe", category="ball", now_wall_epoch_s=WALL + 50,
        )
        self.assertEqual(0., after.attention_bias)
        self.assertEqual(2, after.distinct_mock_sessions)
        self.assertEqual(0, self.memory.experience_count())

    def test_persistent_mock_unknown_cannot_call_qwen_or_move(self):
        old = mock_read("unknown", at=200., seq=10)
        new = mock_read("unknown", at=201., seq=11)
        advisory = start_optional_pc_cycle(
            self.brain, new, journal=self.journal,
            now_monotonic_s=201.1, now_wall_epoch_s=WALL,
        )
        self.assertEqual("inspect", advisory.local_intent.intention)
        portrait = self.brain.describe_behavior(
            advisory.local_intent, journal=self.journal,
            now_wall_epoch_s=WALL,
        )
        situation = MockBehaviorSituation()
        displayed = self.brain.describe_behavior_continuity(
            portrait, situation=situation, now_monotonic_s=201.1,
        )
        outcome = assess_mock_pc_opportunity(
            advisory, portrait=portrait, disposition=displayed,
            previous_read=old, current_read=new, situation=situation,
            motivations=self.brain.motives, now_monotonic_s=201.1,
            pc_opt_in=True,
        )
        self.assertTrue(outcome.interesting)
        self.assertEqual("f5_has_no_discriminating_input", outcome.reason)
        self.assertFalse(outcome.eligible_for_transport)
        self.assertFalse(outcome.request_transmitted)
        self.assertEqual(0, outcome.pc_requests_issued)
        self.assertEqual(0, outcome.motor_commands_issued)
        self.assertEqual(0, self.memory.experience_count())

        untrusted = mock_read("ball", at=202., seq=12,
                              channel="unverified_oem_shape")
        refused = self.brain.propose_passive(
            untrusted, journal=self.journal,
            now_monotonic_s=202.1, now_wall_epoch_s=WALL + 2,
        )
        self.assertEqual("idle", refused.intention)
        self.assertEqual("untrusted_channel", refused.reason)


if __name__ == "__main__":
    unittest.main()
