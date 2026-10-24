"""Deterministic tests for source, time and safety of the perception boundary."""
import math
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, PerceptionEvent, PerceptionSnapshot,
)


class PerceptionTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.brain = AutonomyBrain(self.memory)

    def tearDown(self):
        self.memory.close()

    @staticmethod
    def event(kind, value, *, source="mock", at=100., ttl=1., confidence=1.,
              track_id=None, schema_version=1):
        return PerceptionEvent(
            kind, value, source, at, ttl, confidence,
            track_id=track_id, schema_version=schema_version,
        )

    def snapshot(self, *events, environment="mock", observed_at=100.):
        return PerceptionSnapshot(environment, tuple(events), observed_at)

    def safe_events(self, source="mock", area_source=None):
        return (
            self.event("safe_area", True, source=area_source or source),
            self.event("floor_clear", True, source=source),
            self.event("obstacle_m", 1.0, source=source),
            self.event("battery_pct", 90., source=source),
        )

    def choose(self, *events, environment="mock", now=100.2):
        snap = self.snapshot(*events, environment=environment)
        return self.brain.choose_from_snapshot(snap, now=now)

    def test_fresh_mock_snapshot_explores_without_pc(self):
        plan = self.choose(*self.safe_events())
        self.assertEqual("explore", plan.intention)
        self.assertFalse(plan.request_pc_analysis)

    def test_missing_each_required_safety_signal_halts(self):
        for missing in ("safe_area", "floor_clear", "obstacle_m", "battery_pct"):
            with self.subTest(missing=missing):
                items = [x for x in self.safe_events() if x.kind != missing]
                self.assertEqual("halt", self.choose(*items).intention)

    def test_expired_each_required_signal_halts(self):
        for stale in ("safe_area", "floor_clear", "obstacle_m", "battery_pct"):
            with self.subTest(stale=stale):
                items = [
                    self.event(e.kind, e.value, at=95.) if e.kind == stale else e
                    for e in self.safe_events()
                ]
                self.assertEqual("halt", self.choose(*items).intention)

    def test_future_sensor_does_not_authorize_movement(self):
        items = [
            self.event(e.kind, e.value, at=100.) if e.kind != "floor_clear"
            else self.event("floor_clear", True, at=100.)
            for e in self.safe_events()
        ]
        # Snapshot itself is from the future relative to the decision clock.
        self.assertEqual("halt", self.choose(*items, now=99.).intention)

    def test_conflicting_floor_and_safe_area_halt(self):
        for kind in ("floor_clear", "safe_area"):
            with self.subTest(kind=kind):
                self.assertEqual(
                    "halt", self.choose(
                        *self.safe_events(), self.event(kind, False),
                    ).intention,
                )

    def test_low_confidence_floor_halts(self):
        items = [
            self.event(e.kind, e.value, confidence=.2) if e.kind == "floor_clear"
            else e for e in self.safe_events()
        ]
        self.assertEqual("halt", self.choose(*items).intention)

    def test_ambiguous_obstacle_reading_halts(self):
        self.assertEqual("halt", self.choose(
            *self.safe_events(), self.event("obstacle_m", .1, confidence=.1),
        ).intention)

    def test_nearest_obstacle_wins_and_halts(self):
        self.assertEqual("halt", self.choose(
            *self.safe_events(), self.event("obstacle_m", .2),
        ).intention)

    def test_lowest_battery_wins_and_rests(self):
        self.assertEqual("rest", self.choose(
            *self.safe_events(), self.event("battery_pct", 12.),
        ).intention)

    def test_robot_needs_real_sources_and_operator_boundary(self):
        # A simulator or mock must never claim that a real floor is safe.
        self.assertEqual("halt", self.choose(
            *self.safe_events(), environment="robot",
        ).intention)
        robot_events = (
            self.event("safe_area", True, source="operator"),
            self.event("floor_clear", True, source="sensor"),
            self.event("obstacle_m", 1., source="sensor"),
            self.event("battery_pct", 90., source="robotd"),
        )
        self.assertEqual("explore", self.choose(
            *robot_events, environment="robot"
        ).intention)

    def test_simulator_sources_are_separate_from_robot_sources(self):
        events = self.safe_events("simulator")
        self.assertEqual("explore", self.choose(
            *events, environment="simulator").intention)
        self.assertEqual("halt", self.choose(
            *events, environment="robot").intention)

    def test_llm_cannot_certify_a_safe_floor(self):
        items = [x for x in self.safe_events() if x.kind != "floor_clear"]
        self.assertEqual("halt", self.choose(
            *items,
            self.event("floor_clear", True, source="llm_suggestion"),
        ).intention)

    def test_llm_object_hypothesis_is_not_a_sensor_sighting(self):
        obj = self.event("object_label", "ball", source="llm_suggestion",
                         track_id="obj-1")
        plan = self.choose(*self.safe_events(), obj)
        self.assertEqual("explore", plan.intention)
        self.assertIsNone(self.memory.get("obj-1"))

    def test_fresh_mock_object_is_not_mislabeled_as_sensor(self):
        obj = self.event("object_label", "ball", track_id="obj-1")
        plan = self.choose(*self.safe_events(), obj)
        self.assertEqual("inspect_object", plan.intention)
        known = self.memory.get("obj-1")
        self.assertEqual("mock", known.label_source)
        self.assertEqual("ball", known.label)

    def test_sensor_observation_can_replace_mock_label(self):
        self.memory.observe("obj-1", "toy", source="mock")
        known = self.memory.observe("obj-1", "ball", source="sensor")
        self.assertEqual("ball", known.label)
        self.assertEqual("sensor", known.label_source)

    def test_simulated_label_cannot_override_real_sensor_label(self):
        self.memory.observe("obj-1", "ball", source="sensor")
        known = self.memory.observe("obj-1", "toy", source="simulator")
        self.assertEqual("ball", known.label)
        self.assertEqual("sensor", known.label_source)

    def test_expired_object_not_added_to_memory(self):
        obj = self.event("object_label", "ball", track_id="obj-1", at=98.)
        plan = self.choose(*self.safe_events(), obj)
        self.assertEqual("explore", plan.intention)
        self.assertIsNone(self.memory.get("obj-1"))

    def test_low_confidence_object_not_added_to_memory(self):
        obj = self.event("object_label", "ball", confidence=.5,
                         track_id="obj-1")
        self.choose(*self.safe_events(), obj)
        self.assertIsNone(self.memory.get("obj-1"))

    def test_lost_obstacle_sensor_stops_next_decision(self):
        self.assertEqual("explore", self.choose(*self.safe_events()).intention)
        self.assertEqual("halt", self.choose(
            *[e for e in self.safe_events() if e.kind != "obstacle_m"]
        ).intention)

    def test_reject_unsupported_versions(self):
        with self.assertRaises(ValueError):
            self.event("floor_clear", True, schema_version=2)
        with self.assertRaises(ValueError):
            PerceptionSnapshot("mock", (), 100., schema_version=2)

    def test_invalid_values_and_nonfinite_are_rejected(self):
        invalid = (
            ("floor_clear", "yes", {}),
            ("obstacle_m", -0.1, {}),
            ("obstacle_m", math.nan, {}),
            ("battery_pct", 120., {}),
            ("battery_pct", True, {}),
            ("object_label", "ball", {}),
            ("floor_clear", True, {"confidence": math.nan}),
            ("floor_clear", True, {"at": math.inf}),
            ("floor_clear", True, {"ttl": math.inf}),
            ("floor_clear", True, {"ttl": 0.}),
            ("floor_clear", True, {"ttl": 30.}),
        )
        for kind, value, kw in invalid:
            with self.subTest(kind=kind, value=value, kw=kw):
                with self.assertRaises(ValueError):
                    self.event(kind, value, **kw)

    def test_snapshot_rejects_future_event_or_unknown_environment(self):
        with self.assertRaises(ValueError):
            self.snapshot(self.event("floor_clear", True, at=101.))
        with self.assertRaises(ValueError):
            self.snapshot(environment="spacecraft")

    def test_empty_snapshot_defaults_to_halt(self):
        self.assertEqual("halt", self.choose().intention)

    def test_object_label_conflict_keeps_identity_but_not_label(self):
        events = self.safe_events() + (
            self.event("object_label", "ball", track_id="tracked"),
            self.event("object_label", "toy", track_id="tracked"),
        )
        plan = self.choose(*events)
        self.assertEqual("inspect_object", plan.intention)
        self.assertEqual("unknown", self.memory.get("tracked").label)

    def test_contradictory_person_detection_is_ignored(self):
        events = self.safe_events() + (
            self.event("person_visible", True),
            self.event("person_visible", False),
        )
        self.assertEqual("explore", self.choose(*events).intention)

    def test_fake_labels_do_not_authorize_play_on_robot(self):
        self.memory.observe("tracked", "toy", source="mock")
        real = (
            self.event("safe_area", True, source="operator"),
            self.event("floor_clear", True, source="sensor"),
            self.event("obstacle_m", 1., source="sensor"),
            self.event("battery_pct", 90., source="robotd"),
            self.event("object_label", "unknown", source="sensor", track_id="tracked"),
        )
        plan = self.choose(*real, environment="robot")
        self.assertEqual("inspect_object", plan.intention)

    def test_uncertain_current_object_cannot_use_old_verified_label(self):
        self.memory.observe("tracked", "toy", source="sensor")
        real = (
            self.event("safe_area", True, source="operator"),
            self.event("floor_clear", True, source="sensor"),
            self.event("obstacle_m", 1., source="sensor"),
            self.event("battery_pct", 90., source="robotd"),
            self.event("object_label", "unknown", source="sensor", track_id="tracked"),
        )
        self.assertNotEqual("play_with_object", self.choose(
            *real, environment="robot"
        ).intention)


if __name__ == "__main__":
    unittest.main()
