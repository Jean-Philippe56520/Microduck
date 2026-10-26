"""F4-B: offline spatial uncertainty is not mapping or navigation."""
from __future__ import annotations

from pathlib import Path
import math
import sqlite3
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.uncertain_spatial_memory import (
    FRAMES, LANDMARKS, MAX_ROWS, RETAIN_SECONDS, MIN_RADIUS_M,
    MAX_RADIUS_M, MockSpatialObservation, SpatialMemoryError,
    UncertainSpatialMemory,
)

WALL=1_780_000_000.


def sample(*,frame="mock_zone_a",landmark="toy",x=1.,y=2.,radius=.25,
           confidence=.92,wall=WALL,mono=100.,sequence=1,
           source="mock",channel="mock_spatial_fixture",environment="mock"):
    return MockSpatialObservation(frame,landmark,x,y,radius,confidence,mono,
                                  wall,sequence,source,channel,environment)


class SpatialMemoryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/"spatial.sqlite3"
        self.mem=ExperienceMemory(self.db)
        self.addCleanup(self.mem.close)
        self.spatial=UncertainSpatialMemory(self.mem)

    def add(self,one=None,*,now_mono=100.2,now_wall=WALL+.2):
        return self.spatial.append(one or sample(),now_monotonic_s=now_mono,
                                   now_wall_epoch_s=now_wall)

    def recall(self,frame="mock_zone_a",landmark="toy",now=WALL+1):
        return self.spatial.recall(frame=frame,landmark=landmark,
                                   now_wall_epoch_s=now)

    def test_initially_empty_and_never_navigation_authorized(self):
        r=self.recall()
        self.assertEqual("no_historical_fixture",r.status)
        self.assertEqual(0,r.observations)
        self.assertIsNone(r.x_m)
        self.assertFalse(r.real_reference_frame_verified)
        self.assertFalse(r.real_sensor_authenticated)
        self.assertFalse(r.floor_clearance_verified)
        self.assertFalse(r.navigation_authorized)
        self.assertEqual(0,r.motor_commands_issued)

    def test_single_mock_landmark_has_reported_error_and_no_authority(self):
        self.assertTrue(self.add())
        r=self.recall()
        self.assertEqual("bounded_historical_mock_only",r.status)
        self.assertEqual((1.,2.,.25),(r.x_m,r.y_m,r.uncertainty_radius_m))
        self.assertEqual(.92,r.reported_confidence)
        self.assertTrue(r.historical_only)
        self.assertEqual("mock_spatial_fixture_only",r.source)
        self.assertFalse(r.navigation_authorized)
        self.assertIsNone(self.mem.get("toy"))
        self.assertEqual(0,self.mem.experience_count())

    def test_different_fictional_frames_cannot_be_transformed_or_fused(self):
        self.add()
        self.add(sample(frame="mock_zone_b",x=-3.,y=-4.,sequence=2,
                        mono=101.,wall=WALL+1),
                 now_mono=101.1,now_wall=WALL+1.1)
        a=self.recall()
        b=self.recall(frame="mock_zone_b")
        self.assertEqual(1.,a.x_m)
        self.assertEqual(-3.,b.x_m)
        self.assertEqual(1,a.observations)
        self.assertEqual(1,b.observations)
        self.assertEqual({"mock_zone_a","mock_zone_b"},FRAMES)

    def test_overlap_does_not_artificially_improve_precision(self):
        self.add(sample(x=0.,y=0.,radius=.5))
        self.add(sample(x=.1,y=0.,radius=.4,sequence=2,
                        mono=101.,wall=WALL+1),
                 now_mono=101.1,now_wall=WALL+1.1)
        r=self.recall()
        self.assertEqual("bounded_historical_mock_only",r.status)
        self.assertEqual(2,r.observations)
        self.assertAlmostEqual(.6,r.uncertainty_radius_m)
        self.assertAlmostEqual(.1,r.x_m)
        self.assertEqual(.92,r.reported_confidence)
        self.assertFalse(r.navigation_authorized)

    def test_disjoint_error_disks_fail_closed_no_location(self):
        self.add(sample(x=0.,y=0.,radius=.2))
        self.add(sample(x=1.,y=0.,radius=.2,sequence=2,
                        mono=101.,wall=WALL+1),
                 now_mono=101.1,now_wall=WALL+1.1)
        r=self.recall()
        self.assertEqual("conflicting_mock_landmarks",r.status)
        self.assertEqual(2,r.observations)
        self.assertIsNone(r.x_m)
        self.assertIsNone(r.uncertainty_radius_m)
        self.assertIsNone(r.reported_confidence)
        self.assertFalse(r.floor_clearance_verified)

    def test_overlapping_but_excessive_combined_radius_fails_closed(self):
        self.add(sample(x=0.,y=0.,radius=1.3))
        self.add(sample(x=2.,y=0.,radius=1.3,sequence=2,
                        mono=101.,wall=WALL+1),
                 now_mono=101.1,now_wall=WALL+1.1)
        r=self.recall()
        self.assertEqual("uncertainty_too_large",r.status)
        self.assertIsNone(r.x_m)

    def test_any_low_confidence_blocks_instead_of_cherry_picking(self):
        self.add(sample(x=0.,y=0.,confidence=.5))
        self.add(sample(x=.1,y=0.,confidence=.99,sequence=2,
                        mono=101.,wall=WALL+1),
                 now_mono=101.1,now_wall=WALL+1.1)
        r=self.recall()
        self.assertEqual("insufficient_mock_confidence",r.status)
        self.assertIsNone(r.x_m)
        self.assertFalse(r.navigation_authorized)

    def test_identical_replay_is_idempotent_without_precision_gain(self):
        first=sample()
        self.assertTrue(self.add(first))
        self.assertFalse(self.add(first))
        self.assertEqual(1,self.recall().observations)
        self.assertEqual(1,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4b_mock_spatial_observations").fetchone()[0])

    def test_same_sequence_new_coordinate_is_rejected_without_mutation(self):
        self.add()
        with self.assertRaisesRegex(SpatialMemoryError,"conflicting replay"):
            self.add(sample(x=7.))
        self.assertEqual(1.,self.recall().x_m)

    def test_out_of_order_sequence_rejected(self):
        self.add(sample(sequence=2))
        with self.assertRaisesRegex(SpatialMemoryError,"out-of-order"):
            self.add(sample(sequence=1,mono=100.5,wall=WALL+.5),
                     now_mono=100.6,now_wall=WALL+.6)
        self.assertEqual(1,self.recall().observations)

    def test_out_of_order_wall_timestamp_rejected(self):
        self.add(sample(sequence=2,wall=WALL+1,mono=101.),
                 now_wall=WALL+1.1,now_mono=101.1)
        with self.assertRaisesRegex(SpatialMemoryError,"out-of-order"):
            self.add(sample(sequence=3,wall=WALL+.5,mono=102.),
                     now_wall=WALL+1.2,now_mono=102.1)

    def test_withdrawal_is_persistent_and_cannot_be_resurrected_by_replay(self):
        self.add()
        (rid,)=self.spatial.records(frame="mock_zone_a",landmark="toy",
                                    now_wall_epoch_s=WALL+1)
        self.assertTrue(self.spatial.retract(rid,reason="source_retracted"))
        self.assertFalse(self.spatial.retract(rid,reason="source_retracted"))
        self.assertEqual("no_historical_fixture",self.recall().status)
        self.assertFalse(self.add())
        self.assertEqual((),self.spatial.records(
            frame="mock_zone_a",landmark="toy",now_wall_epoch_s=WALL+1))

    def test_retract_one_conflict_can_restore_historical_mock_recall(self):
        self.add(sample(x=0.,y=0.,radius=.2))
        self.add(sample(x=1.,y=0.,radius=.2,sequence=2,
                        mono=101.,wall=WALL+1),
                 now_mono=101.1,now_wall=WALL+1.1)
        self.assertEqual("conflicting_mock_landmarks",self.recall().status)
        ids=self.spatial.records(frame="mock_zone_a",landmark="toy",
                                 now_wall_epoch_s=WALL+1)
        self.assertTrue(self.spatial.retract(ids[0],
                                             reason="fixture_annotation_error"))
        r=self.recall()
        self.assertEqual("bounded_historical_mock_only",r.status)
        self.assertEqual(1,r.observations)
        self.assertEqual(0.,r.x_m)
        self.assertFalse(r.real_reference_frame_verified)

    def test_sqlite_restart_preserves_historical_fixture_only(self):
        self.add(sample(landmark="table"))
        self.mem.close()
        reopened=ExperienceMemory(self.db)
        try:
            loc=UncertainSpatialMemory(reopened)
            r=loc.recall(frame="mock_zone_a",landmark="table",
                         now_wall_epoch_s=WALL+1)
            self.assertEqual("bounded_historical_mock_only",r.status)
            self.assertTrue(r.historical_only)
            self.assertFalse(r.real_sensor_authenticated)
            self.assertNotEqual(self.spatial.session_id,loc.session_id)
        finally:
            reopened.close()

    def test_missing_new_observation_never_makes_prior_history_current(self):
        self.add()
        r=self.recall(now=WALL+8)
        self.assertEqual("bounded_historical_mock_only",r.status)
        self.assertTrue(r.historical_only)
        self.assertFalse(r.navigation_authorized)
        self.assertFalse(r.floor_clearance_verified)

    def test_expired_data_not_recalled_and_can_be_pruned(self):
        self.add()
        self.assertEqual("no_historical_fixture",
                         self.recall(now=WALL+RETAIN_SECONDS+2).status)
        self.assertEqual(1,self.spatial.prune(
            now_wall_epoch_s=WALL+RETAIN_SECONDS+2))
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4b_mock_spatial_observations").fetchone()[0])

    def test_256_stored_items_cap_and_query_cap(self):
        for i in range(MAX_ROWS+5):
            t=float(i)/10
            self.add(sample(sequence=i+1,landmark="wall",
                            x=0.,y=0.,wall=WALL+t,mono=100.+t),
                     now_mono=100.+t+.05,now_wall=WALL+t+.05)
        self.assertEqual(MAX_ROWS,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4b_mock_spatial_observations").fetchone()[0])
        self.assertEqual(MAX_ROWS,self.recall("mock_zone_a","wall",
                                              WALL+MAX_ROWS/10+2).observations)
        self.assertEqual(50,len(self.spatial.records(
            frame="mock_zone_a",landmark="wall",
            now_wall_epoch_s=WALL+MAX_ROWS/10+2,limit=50)))

    def test_invalid_free_text_landmarks_cannot_be_stored(self):
        for label in ("person","child","Nessquick","Kitty","Malo",
                      "room_12","secret-token","unknown",""):
            with self.subTest(label=label),self.assertRaises(SpatialMemoryError):
                sample(landmark=label)
        self.assertEqual({"toy","ball","table","door","wall"},LANDMARKS)

    def test_arbitrary_real_world_frames_cannot_be_stored(self):
        for frame in ("robot_pose","home","kitchen","GPS","unknown",""):
            with self.subTest(frame=frame),self.assertRaises(SpatialMemoryError):
                sample(frame=frame)

    def test_forged_source_channel_and_environment_rejected(self):
        for changes in ({"source":"sensor"},{"source":"simulator"},
                        {"channel":"robotd"},{"environment":"robot"},
                        {"environment":"simulator"}):
            with self.subTest(changes=changes),self.assertRaises(SpatialMemoryError):
                sample(**changes)
        with self.assertRaises(TypeError):
            self.spatial.append({"x_m":1},now_monotonic_s=100.2,
                                now_wall_epoch_s=WALL+.2)

    def test_nonfinite_or_out_of_bounds_coordinates_and_uncertainty(self):
        for kwargs in ({"x":11.},{"y":-11.},{"x":float("nan")},
                       {"y":float("inf")},{"x":True},
                       {"radius":0.},{"radius":.049},
                       {"radius":2.01},{"radius":float("nan")},
                       {"confidence":-1.},{"confidence":1.1},
                       {"confidence":float("inf")},{"confidence":True}):
            with self.subTest(kwargs=kwargs),self.assertRaises(SpatialMemoryError):
                sample(**kwargs)
        self.assertEqual(.05,MIN_RADIUS_M)
        self.assertEqual(2.,MAX_RADIUS_M)

    def test_monotonic_stale_and_future_rejected_before_sql(self):
        for observed,now in ((100.,101.01),(100.1,100.),
                             (100.,float("inf")),(100.,True)):
            with self.subTest(observed=observed,now=now),self.assertRaises(
                SpatialMemoryError):
                self.add(sample(mono=observed),now_mono=now)
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4b_mock_spatial_observations").fetchone()[0])

    def test_wall_stale_future_and_invalid_stamp_rejected(self):
        for stamp,now in ((WALL,WALL+3.),(WALL+1,WALL),
                          (WALL,float("nan")),(WALL,True)):
            with self.subTest(stamp=stamp,now=now),self.assertRaises(
                (SpatialMemoryError,ValueError)):
                self.add(sample(wall=stamp),now_wall=now)
        for invalid in (-1.,True,float("nan"),float("inf")):
            with self.assertRaises(SpatialMemoryError):
                sample(wall=invalid)

    def test_invalid_query_and_correction_parameters(self):
        for kw in ({"frame":"real_room"},{"landmark":"person"},
                   {"frame":"mock_zone_zz"}):
            args={"frame":"mock_zone_a","landmark":"toy",
                  "now_wall_epoch_s":WALL}
            args.update(kw)
            with self.assertRaises(ValueError):
                self.spatial.recall(**args)
        for limit in (0,51,True):
            with self.assertRaises(ValueError):
                self.spatial.records(frame="mock_zone_a",landmark="toy",
                                     now_wall_epoch_s=WALL,limit=limit)
        for record_id,reason in ((0,"source_retracted"),
                                 (True,"source_retracted"),
                                 (1,"grant_navigation")):
            with self.assertRaises(ValueError):
                self.spatial.retract(record_id,reason=reason)

    def test_closed_database_stays_inaccessible_without_motor_fallback(self):
        self.mem.close()
        with self.assertRaises(sqlite3.Error):
            self.recall()
        with self.assertRaises(sqlite3.Error):
            self.add()

    def test_repeating_sample_does_not_verify_physical_floor(self):
        self.add(sample(landmark="door"))
        r=self.recall(landmark="door")
        self.assertEqual("bounded_historical_mock_only",r.status)
        self.assertFalse(r.navigation_authorized)
        self.assertFalse(r.floor_clearance_verified)
        self.assertFalse(r.real_sensor_authenticated)
        self.assertFalse(r.real_reference_frame_verified)
        self.assertEqual(0,r.motor_commands_issued)


if __name__=="__main__":
    unittest.main()
