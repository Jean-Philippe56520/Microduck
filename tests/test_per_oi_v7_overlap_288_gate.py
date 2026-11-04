"""PER-OI-V7-OVERLAP-1: source-only test harness, no model/network/pixels."""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from experiments.per_oi_v7_frozen_cohort import TARGETS
from experiments.per_oi_v7_overlap_288_gate import (
    EXPECTED_OLD_TOTAL, OpenImagesSourceStop, _read_human_positive,
    assess_frozen_metadata, roster_sha, w1_sha, _file,
)


def fake_inputs():
    roster=tuple((f"{i+1:016x}", TARGETS[i//6]) for i in range(42))
    old_c=frozenset(f"{i:016x}" for i in range(100,148))
    old_d=frozenset(f"{i:016x}" for i in range(200,392))
    old_w=frozenset(f"{i:016x}" for i in range(500,548))
    current={ident for ident,_ in roster}
    return roster,old_c,old_d,old_w,current,current.copy()


class TestOverlapGate(unittest.TestCase):
    def setUp(self):
        self.roster,self.oldc,self.oldd,self.oldw,self.positive,self.landing=fake_inputs()
        self.sha=roster_sha(self.roster)

    def assessment(self, **change):
        values=dict(
            chosen=self.roster, old_a2c=self.oldc, old_a2d=self.oldd,
            old_w1=self.oldw, positive=self.positive, landing=self.landing,
            frozen_sha256=self.sha)
        values.update(change)
        return assess_frozen_metadata(**values)

    def test_positive_synthetic_42_disjoint_from_exact_288(self):
        r=self.assessment()
        self.assertEqual("OI_42_DISJOINT_FROM_288_WITH_HUMAN_GT_METADATA_ONLY",r["status"])
        self.assertEqual(0,r["reused_known_openimages_count"])
        self.assertEqual(EXPECTED_OLD_TOTAL,r["historical_openimages_ids_reconstructed"])
        self.assertEqual(42,r["assigned_human_positive_with_bbox_count"])
        self.assertFalse(r["coco_val_5000_flickr_overlap_checked"])
        self.assertFalse(r["individual_photo_rights_verified"])
        self.assertFalse(r["cohort_commercially_approved"])
        self.assertFalse(r["scores_measured"])
        self.assertEqual(0,r["jpeg_downloaded"])
        self.assertEqual(0,r["model_inferences"])
        self.assertEqual(0,r["motor_commands"])

    def test_negative_overlap_with_consumed_w1_forbids_pass(self):
        old=frozenset((set(self.oldw)-{next(iter(self.oldw))}) | {self.roster[0][0]})
        r=self.assessment(old_w1=old)
        self.assertEqual("STOP_FROZEN_42_SOURCE_NOT_QUALIFIED",r["status"])
        self.assertEqual(1,r["reused_known_openimages_count"])

    def test_negative_overlap_with_consumed_a2c_forbids_pass(self):
        old=frozenset((set(self.oldc)-{next(iter(self.oldc))}) | {self.roster[0][0]})
        self.assertEqual(1,self.assessment(old_a2c=old)["reused_known_openimages_count"])

    def test_negative_missing_verified_human_positive_stops(self):
        less=set(self.positive)-{self.roster[0][0]}
        r=self.assessment(positive=less)
        self.assertEqual("STOP_FROZEN_42_SOURCE_NOT_QUALIFIED",r["status"])
        self.assertEqual(41,r["assigned_human_positive_with_bbox_count"])
        self.assertEqual(1,r["assigned_human_unknown_or_contradictory_count"])

    def test_negative_missing_https_landing_stops(self):
        r=self.assessment(landing=set(self.landing)-{self.roster[0][0]})
        self.assertEqual("STOP_FROZEN_42_SOURCE_NOT_QUALIFIED",r["status"])
        self.assertEqual(41,r["selected_original_landing_https_count"])

    def test_negative_historical_union_wrong_refused(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,"288 historic"):
            self.assessment(old_a2d=frozenset(self.oldd-{next(iter(self.oldd))}))

    def test_negative_historical_cohort_overlap_refused(self):
        old=frozenset((set(self.oldw)-{next(iter(self.oldw))}) | {next(iter(self.oldc))})
        with self.assertRaisesRegex(OpenImagesSourceStop,"288 historic"):
            self.assessment(old_w1=old)

    def test_negative_roster_sha_mismatch_refused(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,"sealed 42"):
            self.assessment(frozen_sha256="0"*64)

    def test_negative_duplicate_assigned_image_refused(self):
        roster=((self.roster[1][0], self.roster[0][1]),)+self.roster[1:]
        with self.assertRaisesRegex(OpenImagesSourceStop,"sealed 42"):
            self.assessment(chosen=roster,frozen_sha256=roster_sha(roster))

    def test_negative_wrong_seven_by_six_allocation_refused(self):
        roster=((self.roster[0][0],"Book"),)+self.roster[1:]
        with self.assertRaisesRegex(OpenImagesSourceStop,"sealed 42"):
            self.assessment(chosen=roster,frozen_sha256=roster_sha(roster))

    def test_negative_historical_id_format_count_refused(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,"288 historic"):
            self.assessment(old_a2c=set(self.oldc))

    def _human_file(self, *, first_conf="1.000000", conflict=False, missing=False,
                    first_source="verification"):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path=Path(tmp.name)/"human.csv"
        mids={f"/m/{i+1:05x}":name for i,name in enumerate(TARGETS)}
        reverse={name:mid for mid,name in mids.items()}
        with path.open("w",encoding="utf-8",newline="") as fp:
            w=csv.DictWriter(fp,fieldnames=("ImageID","Source","LabelName","Confidence"))
            w.writeheader()
            for i,(ident,label) in enumerate(self.roster):
                if i==0 and missing:
                    continue
                w.writerow({"ImageID":ident,"Source":first_source if i==0 else "verification",
                            "LabelName":reverse[label],"Confidence":first_conf if i==0 else "1"})
                if i==0 and conflict:
                    w.writerow({"ImageID":ident,"Source":"crowdsource-verification",
                                "LabelName":reverse[label],"Confidence":"0"})
        return path,mids

    def test_human_positive_exact_decimal_binary_accepted(self):
        path,mids=self._human_file()
        self.assertEqual(42,len(_read_human_positive(path,self.roster,mids)))

    def test_human_negative_conflict_is_not_positive(self):
        path,mids=self._human_file(conflict=True)
        self.assertEqual(41,len(_read_human_positive(path,self.roster,mids)))

    def test_human_missing_vote_is_not_negative(self):
        path,mids=self._human_file(missing=True)
        self.assertEqual(41,len(_read_human_positive(path,self.roster,mids)))

    def test_human_fractional_vote_rejected(self):
        path,mids=self._human_file(first_conf="0.5")
        with self.assertRaisesRegex(OpenImagesSourceStop,"nonbinary"):
            _read_human_positive(path,self.roster,mids)

    def test_human_machine_vote_rejected(self):
        path,mids=self._human_file(first_source="machine")
        with self.assertRaisesRegex(OpenImagesSourceStop,"not human"):
            _read_human_positive(path,self.roster,mids)

    def test_symlink_csv_rejected(self):
        path,mids=self._human_file()
        link=path.with_name("alias.csv");link.symlink_to(path)
        with self.assertRaisesRegex(OpenImagesSourceStop,"symlinked"):
            _file(link,55_000_000)


if __name__=="__main__":
    unittest.main()
