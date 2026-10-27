"""X2-B host acceptance: bounded memory of SIMULATED power state only.

No OEM simulator, camera, recognizer, movement, cause-effect reward or Qwen
is run by this file. These tests use scripted immutable telemetry dataclasses.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_ipc import DepthReading, HealthReading, StateReading
from microduck_companion.sim_passive_cycles import PassiveSimCycleRunner


def reading(*, at: float = 100., seq: int = 1,
            battery: float | None = 80.) -> SimulatorTelemetry:
    stamp = at - .05
    return SimulatorTelemetry(
        HealthReading(True, battery, 50., 49.9, 0, stamp),
        StateReading(False, False, 49.9, 0, seq * 1_000_000, stamp),
        DepthReading(seq, (1400,) * 64, (5,) * 64,
                     seq * 1_000_000 + 10_000, stamp),
    )


class SimPowerContextTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "one.sqlite3"
        self.memory = ExperienceMemory(self.path)
        self.addCleanup(self.memory.close)
        self.runner = PassiveSimCycleRunner(self.memory, session="initial")

    def test_first_observation_is_idle_without_historical_reference(self):
        c = self.runner.step(reading(), now=100.)
        self.assertEqual(("coherent", "halt"), (c.quality, c.plan.intention))
        self.assertEqual(("idle", "no_reference", None),
                         (c.attention, c.comparison, c.reference_id))
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT count(*) FROM intent_preferences").fetchone()[0])
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT count(*) FROM objects").fetchone()[0])

    def test_low_to_normal_is_cautious_attention_not_a_motor_action(self):
        energy = self.runner.brain.motives.energy
        a = self.runner.step(reading(battery=12.), now=100.)
        self.assertEqual(("rest", "rest", "no_reference"),
                         (a.plan.intention, a.attention, a.comparison))
        # Merely proposing rest cannot recharge fictional motivation.
        self.assertEqual(energy, self.runner.brain.motives.energy)
        b = self.runner.step(reading(at=101., seq=2, battery=80.), now=101.)
        self.assertEqual("halt", b.plan.intention)
        self.assertEqual("observe_status", b.attention)
        self.assertEqual("low_to_normal", b.comparison)
        self.assertEqual(1, b.reference_id)
        self.assertEqual(energy, self.runner.brain.motives.energy)
        self.assertEqual(["rest", "observe_status"],
                         [x["attention"] for x in self.runner.history()])
        self.assertFalse(any(x["reward"] is not None
                             for x in self.runner.history()))
        self.assertEqual({0}, {x["motor_commands"]
                               for x in self.runner.history()})
        self.assertEqual({"no_action_executed"},
                         {x["outcome"] for x in self.runner.history()})

    def test_normal_to_low_is_rest_and_stable_band_not_repeated_novelty(self):
        a = self.runner.step(reading(battery=83.), now=100.)
        b = self.runner.step(reading(at=101., seq=2, battery=11.), now=101.)
        c = self.runner.step(reading(at=102., seq=3, battery=10.), now=102.)
        self.assertEqual(["idle", "rest", "rest"],
                         [a.attention, b.attention, c.attention])
        self.assertEqual(["no_reference", "normal_to_low", "stable_band"],
                         [a.comparison, b.comparison, c.comparison])
        self.assertEqual((1, 2), (b.reference_id, c.reference_id))
        self.assertEqual(0., self.memory.intent_preference("simulator", "explore"))

    def test_low_to_normal_only_if_existing_motivation_allows(self):
        self.runner.step(reading(battery=10.), now=100.)
        self.runner.brain.motives.caution = 1.
        c = self.runner.step(reading(at=101., seq=2, battery=70.), now=101.)
        self.assertEqual("low_to_normal", c.comparison)
        self.assertEqual("idle", c.attention)
        self.assertEqual("halt", c.plan.intention)

    def test_prior_unknown_battery_never_masquerades_as_known(self):
        self.runner.step(reading(battery=None), now=100.)
        c = self.runner.step(reading(at=101., seq=2, battery=80.), now=101.)
        self.assertEqual("unknown_battery", c.comparison)
        self.assertIsNone(c.reference_id)
        self.assertEqual("idle", c.attention)

    def test_current_unknown_cannot_be_comparison_reference(self):
        self.runner.step(reading(battery=12.), now=100.)
        unknown = self.runner.step(reading(at=101., seq=2, battery=None),
                                   now=101.)
        self.assertEqual(("unknown_battery", "abstain"),
                         (unknown.comparison, unknown.attention))
        after = self.runner.step(reading(at=102., seq=3, battery=80.), now=102.)
        self.assertEqual(("unknown_battery", "idle", None),
                         (after.comparison, after.attention, after.reference_id))

    def test_invalid_or_replayed_sample_interrupts_memory_not_a_reward(self):
        self.runner.step(reading(battery=10.), now=100.)
        stale = self.runner.step(reading(at=97., seq=2, battery=80.), now=101.)
        self.assertEqual(("invalid_or_missing", "halt", "abstain"),
                         (stale.quality, stale.plan.intention, stale.attention))
        next_good = self.runner.step(
            reading(at=102., seq=3, battery=80.), now=102.)
        self.assertEqual(("interrupted", "idle", None),
                         (next_good.comparison, next_good.attention,
                          next_good.reference_id))
        replay = self.runner.step(
            reading(at=103., seq=3, battery=10.), now=103.)
        self.assertEqual(("nonadvancing_frame", "abstain"),
                         (replay.quality, replay.attention))
        self.assertEqual({"no_action_executed"},
                         {r["outcome"] for r in self.runner.history()})

    def test_fallen_robot_prevents_using_remembered_good_battery(self):
        self.runner.step(reading(battery=12.), now=100.)
        sample = reading(at=101., seq=2, battery=80.)
        unsafe = replace(sample, state=replace(sample.state, fallen=True))
        got = self.runner.step(unsafe, now=101.)
        self.assertEqual(("invalid_or_missing", "halt", "abstain"),
                         (got.quality, got.plan.intention, got.attention))
        self.assertEqual("interrupted", got.comparison)

    def test_expiry_uses_current_read_not_old_pseudo_sensor(self):
        self.runner.step(reading(at=100., battery=10.), now=100.)
        c = self.runner.step(reading(at=161., seq=2, battery=80.), now=161.)
        self.assertEqual(("expired", "idle", None),
                         (c.comparison, c.attention, c.reference_id))

    def test_new_session_timebase_reset_and_tof_reset_do_not_compare(self):
        self.runner.step(reading(at=100., seq=200, battery=10.), now=100.)
        restarted = PassiveSimCycleRunner(self.memory, session="new-sim")
        # New ToF stream, despite increasing local monotonic time.
        reset = restarted.step(reading(at=101., seq=1, battery=80.), now=101.)
        self.assertEqual(("incompatible_clock", "idle", None),
                         (reset.comparison, reset.attention, reset.reference_id))

    def test_new_session_earlier_timebase_cannot_use_future_old_history(self):
        self.runner.step(reading(at=100., seq=20, battery=10.), now=100.)
        second = PassiveSimCycleRunner(self.memory, session="new-clock")
        c = second.step(reading(at=50., seq=1, battery=80.), now=50.)
        self.assertEqual(("incompatible_clock", "idle", None),
                         (c.comparison, c.attention, c.reference_id))

    def test_two_fresh_sessions_share_durable_history_not_sensor_authority(self):
        self.runner.step(reading(battery=10.), now=100.)
        self.memory.close()
        other = ExperienceMemory(self.path)
        try:
            second = PassiveSimCycleRunner(other, session="session-b")
            c = second.step(reading(at=101., seq=2, battery=80.), now=101.)
            self.assertEqual(("low_to_normal", "observe_status", 1),
                             (c.comparison, c.attention, c.reference_id))
            self.assertEqual(2, len(second.history()))
            self.assertEqual({"simulator_ipc"},
                             {row["source"] for row in second.history()})
            self.assertEqual(0, other.experience_count())
            self.assertEqual(0, other.conn.execute(
                "SELECT count(*) FROM sim_motion_trials").fetchone()[0])
        finally:
            other.close()

    def test_existing_p2b_sqlite_migrates_in_place_without_deleting_history(self):
        self.memory.conn.execute("DROP TABLE sim_passive_cycles")
        self.memory.conn.execute("""
            CREATE TABLE sim_passive_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session TEXT NOT NULL, sequence INTEGER NOT NULL,
                observed_at REAL NOT NULL, quality TEXT NOT NULL,
                intention TEXT NOT NULL, disposition TEXT NOT NULL,
                depth_seq INTEGER, state_t_ns INTEGER, depth_t_ns INTEGER,
                battery_pct REAL, source TEXT NOT NULL,
                outcome TEXT NOT NULL, reward REAL, motor_commands INTEGER,
                UNIQUE(session, sequence)
            )""")
        self.memory.conn.execute("""
            INSERT INTO sim_passive_cycles (
                session,sequence,observed_at,quality,intention,disposition,
                depth_seq,state_t_ns,depth_t_ns,battery_pct,
                source,outcome,reward,motor_commands)
            VALUES ('old',1,100.,'coherent','rest','observation_only',
                    1,1000000,1010000,12.,
                    'simulator_ipc','no_action_executed',NULL,0)
        """)
        self.memory.conn.commit()
        migrated = PassiveSimCycleRunner(self.memory, session="new")
        old = migrated.history()[0]
        self.assertEqual("not_evaluated", old["attention"])
        self.assertEqual("not_evaluated", old["comparison"])
        self.assertIsNone(old["reference_id"])
        now = migrated.step(reading(at=101., seq=2, battery=70.), now=101.)
        self.assertEqual(("low_to_normal", "observe_status", 1),
                         (now.comparison, now.attention, now.reference_id))
        migrated_again = PassiveSimCycleRunner(self.memory, session="another")
        self.assertEqual(2, len(migrated_again.history()))

    def test_historical_context_cannot_change_causal_preferences(self):
        self.runner.step(reading(battery=10.), now=100.)
        self.runner.step(reading(at=101., seq=2, battery=80.), now=101.)
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0., self.memory.intent_preference("simulator", "explore"))
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT count(*) FROM intent_preferences").fetchone()[0])
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT count(*) FROM objects").fetchone()[0])

    def test_brain_cognitive_hint_pure_does_not_restore_energy_or_move(self):
        brain = AutonomyBrain(self.memory)
        old = (brain.motives.energy, brain.motives.curiosity, brain.previous_intention)
        self.assertEqual("observe_status", brain.consider_simulator_status(
            quality="coherent", battery_pct=80.,
            prior_battery_low=True, comparable_memory=True))
        self.assertEqual("idle", brain.consider_simulator_status(
            quality="coherent", battery_pct=80.,
            prior_battery_low=True, comparable_memory=False))
        self.assertEqual("rest", brain.consider_simulator_status(
            quality="coherent", battery_pct=10.,
            prior_battery_low=None, comparable_memory=False))
        self.assertEqual("abstain", brain.consider_simulator_status(
            quality="source_error", battery_pct=None,
            prior_battery_low=True, comparable_memory=True))
        self.assertEqual(old, (brain.motives.energy, brain.motives.curiosity,
                               brain.previous_intention))
        self.assertEqual(0, self.memory.experience_count())


if __name__ == "__main__":
    unittest.main()
