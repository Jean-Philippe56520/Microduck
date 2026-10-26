"""P-C: OEM petting/noise/voice are only interpreted as mock descriptions.

Uses the existing P-A/B portrait and the existing F4-C mock context. No
audio capture, servo/motor command, RTC identity, wake detector or SQLite write.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.behavior_personality import BehaviorPortrait
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_social_cues import MockSocialContext
from microduck_companion.behavioral_memory import BehavioralMemory
from microduck_companion.mock_cycles import MockConsequence, MockCycleRunner
from microduck_companion.mock_cycle_demo import mock_snapshot
from microduck_companion.oem_expression_hints import (
    MAX_MOCK_CUE_AGE_S, MOCK_OEM_KINDS, MockExpressionHint,
    MockOemCue, MockOemConditions, describe_oem_expression,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal

NOW=104.0
WALL=1_780_000_000.0


def consent(**changes):
    flags = dict(
        operator_opt_in=True, supervised=True, privacy_reviewed=True,
        quiet_mode=False, brief_audio_opt_in=True,
    )
    flags.update(changes)
    return MockSocialContext(**flags)


def cue(kind, at=NOW-.1):
    return MockOemCue(kind, at)


class ExpressionHintsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.mem = ExperienceMemory(Path(self.folder.name)/"one.sqlite3")
        self.addCleanup(self.mem.close)
        self.journal = PassiveObservationJournal(self.mem)
        self.brain = AutonomyBrain(self.mem)
        self.portrait = self.brain.describe_behavior(
            PassiveIntent("idle", "no_current_observation"),
            journal=self.journal, now_wall_epoch_s=WALL,
        )

    def hint(self, event, *, context=None, conditions=None, portrait=None,
             now=NOW):
        return self.brain.describe_oem_expression(
            self.portrait if portrait is None else portrait,
            cue=event,
            context=consent() if context is None else context,
            conditions=MockOemConditions() if conditions is None else conditions,
            now_monotonic_s=now,
        )

    def test_enum_mirrors_pinned_oem_without_hardware(self):
        self.assertEqual({
            "petting_start", "petting_end", "ambient_noise", "ambient_voice",
        }, MOCK_OEM_KINDS)
        self.assertEqual(0, self.mem.conn.total_changes)

    def test_default_context_silent_no_output_no_write(self):
        before = self.mem.conn.total_changes
        prior_motives = vars(self.brain.motives).copy()
        for kind in MOCK_OEM_KINDS:
            with self.subTest(kind=kind):
                p = self.hint(cue(kind), context=MockSocialContext())
                self.assertEqual(("silent", "mock_opt_in_missing", None),
                                 (p.status,p.reason,p.historical_candidate))
                self.assertEqual(0, p.speaker_commands_issued)
                self.assertEqual(0, p.motor_commands_issued)
                self.assertEqual(0, p.sensor_reads)
        self.assertEqual(before, self.mem.conn.total_changes)
        self.assertEqual(prior_motives, vars(self.brain.motives))

    def test_petting_start_is_oem_owned_no_second_coo(self):
        before = self.mem.conn.total_changes
        p = self.hint(cue("petting_start"))
        self.assertEqual(
            ("oem_owned","Petted","oem_petting_coo_already_owned"),
            (p.status,p.historical_candidate,p.reason))
        self.assertEqual(self.portrait.state,p.base_state)
        self.assertEqual(self.portrait.affect,p.base_affect)
        self.assertFalse(p.executed)
        self.assertFalse(p.real_sensor_authenticated)
        self.assertFalse(p.physical_execution_authorized)
        self.assertEqual((0,0,0,0,0),
                         (p.motor_commands_issued,p.speaker_commands_issued,
                          p.audio_bytes_stored,p.sensor_reads,p.memories_written))
        self.assertEqual(before, self.mem.conn.total_changes)

    def test_petting_end_has_no_extra_reaction(self):
        r = self.hint(cue("petting_end"))
        self.assertEqual(("silent",None,"petting_ended"),
                         (r.status,r.historical_candidate,r.reason))

    def test_oem_noise_only_suggests_historical_startle(self):
        p=self.hint(cue("ambient_noise"))
        self.assertEqual(("hypothesis","Startle","ambient_noise_startle_unverified"),
                         (p.status,p.historical_candidate,p.reason))
        self.assertFalse(p.executed)
        self.assertEqual(0,p.speaker_commands_issued)
        self.assertEqual(0,p.motor_commands_issued)

    def test_oem_voice_is_not_speech_or_wake_command(self):
        p=self.hint(cue("ambient_voice"))
        self.assertEqual(("notice_only",None,"voice_detected_not_understood"),
                         (p.status,p.historical_candidate,p.reason))
        self.assertFalse(p.wake_word_recognized)
        self.assertEqual(0,p.pc_requests_issued)
        self.assertEqual(0,p.sensor_reads)
        self.assertFalse(p.physical_execution_authorized)
        self.assertNotIn("Kwipi",str(p))
        self.assertNotIn("stop",str(p))

    def test_self_audio_and_motion_gates_block_ambient(self):
        for kind in ("ambient_noise","ambient_voice"):
            for flagged in (MockOemConditions(self_audio=True),
                            MockOemConditions(self_motion=True)):
                with self.subTest(kind=kind,flagged=flagged):
                    p=self.hint(cue(kind),conditions=flagged)
                    self.assertEqual(("silent","self_generated_noise_or_motion"),
                                     (p.status,p.reason))

    def test_busy_fallen_stop_gate_all_contextual_reactions(self):
        for conditions in (
            MockOemConditions(busy=True),
            MockOemConditions(fallen=True),
            MockOemConditions(stop_requested=True),
        ):
            for kind in MOCK_OEM_KINDS:
                with self.subTest(kind=kind,conditions=conditions):
                    p=self.hint(cue(kind), conditions=conditions)
                    self.assertEqual(("silent","mock_safety_or_stop"),
                                     (p.status,p.reason))

    def test_quiet_mode_blocks_all_extra_interpretation(self):
        for kind in MOCK_OEM_KINDS:
            p=self.hint(cue(kind),context=consent(quiet_mode=True))
            self.assertEqual(("silent","mock_quiet_mode"),(p.status,p.reason))
        # A mock quiet-mode flag CANNOT disable the OEM's own physical coo.

    def test_no_opt_in_supervision_privacy_or_sound_consent(self):
        for opts in (
            dict(operator_opt_in=False),
            dict(supervised=False),
            dict(privacy_reviewed=False),
        ):
            p=self.hint(cue("petting_start"),context=consent(**opts))
            self.assertEqual(("silent","mock_opt_in_missing"),(p.status,p.reason))
        for kind in ("ambient_voice","ambient_noise"):
            p=self.hint(cue(kind),context=consent(brief_audio_opt_in=False))
            self.assertEqual(("silent","sound_context_not_opted_in"),
                             (p.status,p.reason))
        # The separate audio flag is not required for OEM-owned petting.
        p=self.hint(cue("petting_start"),
                    context=consent(brief_audio_opt_in=False))
        self.assertEqual("oem_owned",p.status)

    def test_stale_future_boundary_and_none_are_silent(self):
        self.assertEqual("no_mock_cue", self.hint(None).reason)
        p=self.hint(cue("ambient_noise",NOW-MAX_MOCK_CUE_AGE_S))
        self.assertEqual("hypothesis",p.status)
        for t in (NOW-MAX_MOCK_CUE_AGE_S-.001, NOW+.001):
            with self.subTest(t=t):
                p=self.hint(cue("petting_start",t))
                self.assertEqual(("silent","stale_future_mock_cue"),
                                 (p.status,p.reason))

    def test_unknown_event_invalid_inputs_and_bools_rejected(self):
        with self.assertRaises(ValueError):
            MockOemCue("keyword_stop",100.)
        with self.assertRaises(ValueError):
            MockOemCue("ambient_voice",float("nan"))
        with self.assertRaises(ValueError):
            MockOemCue("ambient_voice",100.,source="robotd")
        with self.assertRaises(ValueError):
            MockOemConditions(self_audio=1)
        with self.assertRaises(TypeError):
            self.hint({"kind":"ambient_noise"})
        with self.assertRaises(TypeError):
            self.hint(cue("ambient_noise"),portrait="happy")
        with self.assertRaises(TypeError):
            self.hint(cue("petting_start"),context={"quiet_mode":False})
        with self.assertRaises(TypeError):
            self.hint(cue("petting_start"),conditions="safe")
        with self.assertRaises(ValueError):
            self.hint(cue("petting_start"),now=float("inf"))

    def test_repeated_cue_is_idempotent_no_second_scheduler(self):
        before=self.mem.conn.total_changes
        a=self.hint(cue("petting_start"))
        b=self.hint(cue("petting_start"))
        self.assertEqual(a,b)
        self.assertEqual(before,self.mem.conn.total_changes)
        self.assertIsNone(self.brain._passive_rhythm)

    def test_inspection_habit_from_existing_sqlite_is_read_only_context(self):
        runner=MockCycleRunner(self.mem,session="pc-fiction")
        behavioral=BehavioralMemory(self.mem)
        for i in range(2):
            t=70.+4.*i
            target=f"mock-toy-{i}"
            cycle=runner.step(mock_snapshot(t,target=target),now=t+.5,
                              followup=mock_snapshot(t+.4,target=target),
                              consequence=MockConsequence(target,"positive",t+.3))
            self.assertTrue(behavioral.record(
                runner=runner,sequence=cycle.sequence,now_wall_epoch_s=WALL))
        portrait=self.brain.describe_behavior(
            PassiveIntent("inspect","fictional","object_label","unknown"),
            journal=self.journal,now_wall_epoch_s=WALL,
            behavioral=behavioral,
        )
        self.assertEqual("inspection_encouraged",portrait.inspection_habit)
        before=self.mem.conn.total_changes
        p=self.hint(cue("ambient_noise"),portrait=portrait)
        self.assertEqual(("Startle","inspection_encouraged"),
                         (p.historical_candidate,p.inspection_habit))
        self.assertEqual(portrait.affect,p.base_affect)
        self.assertEqual(before,self.mem.conn.total_changes)
        self.assertFalse(p.executed)

    def test_forged_expression_can_never_claim_execution_or_oem_active_state(self):
        r=self.hint(cue("petting_start"))
        for kw in (
            dict(motor_commands_issued=1),dict(speaker_commands_issued=1),
            dict(memories_written=1),dict(wake_word_recognized=True),
            dict(real_sensor_authenticated=True),
            dict(executed=True),dict(physical_execution_authorized=True),
            dict(sensor_reads=1),dict(pc_requests_issued=1),
            dict(audio_bytes_stored=10),dict(status="hypothesis"),
            dict(historical_candidate="Held"),
            dict(status="silent"),
        ):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    replace(r,**kw)

    def test_no_hardware_and_no_model_or_personal_identification(self):
        before=self.mem.conn.total_changes
        p=self.hint(cue("ambient_noise"))
        self.assertEqual("mock_expression_read_only",p.source)
        self.assertEqual(0,p.motor_commands_issued)
        self.assertEqual(0,p.speaker_commands_issued)
        self.assertEqual(0,p.sensor_reads)
        self.assertEqual(0,p.memories_written)
        self.assertFalse(p.real_sensor_authenticated)
        self.assertFalse(p.wake_word_recognized)
        self.assertEqual(before,self.mem.conn.total_changes)


if __name__=="__main__":
    unittest.main()
