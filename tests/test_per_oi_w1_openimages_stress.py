"""Offline positive/negative gates for prospective PER-OI-W1, no network."""
from __future__ import annotations
import unittest
from tests.test_cata2d_openimages_bbox_public import csv_bytes
from experiments.per_oi_w1_openimages_stress import (
    TARGETS, PER_LABEL, target_mids, choose_cases, _matched,
)
from experiments.cata2d_openimages_bbox_public import PublicCase, PublicBox
from experiments.per80_yolox_coco_public import Proposal
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError


class OpenImagesW1Tests(unittest.TestCase):
    def setUp(self):
        self.classes = [("/m/w1"+str(i),name)
                        for i,(cat,(name,_)) in enumerate(TARGETS.items())]
        self.meta=[];self.votes=[];self.boxes=[]
        for i,cat in enumerate(TARGETS):
            for presence in (True,False):
                for n in range(PER_LABEL+1):
                    ident=f"{i*100+int(not presence)*20+n+1:016x}"
                    self.meta.append((ident,"validation",
                        "https://creativecommons.org/licenses/by/2.0/","48000","0"))
                    self.votes.append((ident,"verification",f"/m/w1{i}",str(int(presence))))
                    if presence:
                        self.boxes.append((ident,"xclick",f"/m/w1{i}","1",
                                          ".1",".5",".2",".8","0","0","0","0","0"))
    def sources(self):
        return (
            csv_bytes(None,self.classes),
            csv_bytes(["ImageID","Subset","License","OriginalSize","Rotation"],self.meta),
            csv_bytes(["ImageID","Source","LabelName","Confidence"],self.votes),
            csv_bytes(["ImageID","Source","LabelName","Confidence",
                       "XMin","XMax","YMin","YMax","IsOccluded",
                       "IsTruncated","IsGroupOf","IsDepiction","IsInside"],self.boxes),
        )
    def select(self,excluded=frozenset()):
        return choose_cases(*self.sources(),excluded_ids=excluded)
    def test_positive_balanced_48_distinct_gt(self):
        result=self.select()
        self.assertEqual(48,len(result))
        self.assertEqual(48,len({c.image_id for c in result}))
        for cat in TARGETS:
            self.assertEqual(8,sum(c.category==cat and c.present for c in result))
            self.assertEqual(8,sum(c.category==cat and not c.present for c in result))
        self.assertTrue(all(c.boxes for c in result if c.present))
        self.assertTrue(all(not c.boxes for c in result if not c.present))
    def test_order_invariance_and_exclusion(self):
        first=self.select()
        self.classes.reverse();self.meta.reverse();self.votes.reverse();self.boxes.reverse()
        self.assertEqual(first,self.select())
        exclude=frozenset(c.image_id for c in first)
        with self.assertRaisesRegex(PhotoBaselineError,"STOP_SOURCE"):
            self.select(exclude)
    def test_missing_or_ambiguous_mid_stops(self):
        for invalid in (
            csv_bytes(None,self.classes[:-1]),
            csv_bytes(None,self.classes+[self.classes[0]]),
        ):
            with self.assertRaises(PhotoBaselineError):
                target_mids(invalid)
    def test_missing_or_unverified_negative_stops(self):
        # A missing vote may not be interpreted as a negative.
        self.votes=[v for v in self.votes if not (
            v[2]=="/m/w10" and v[3]=="0")]
        with self.assertRaises(PhotoBaselineError):
            self.select()
    def test_conflict_bad_bbox_and_license_stop(self):
        self.votes.append((self.votes[0][0],"crowdsource-verification",
                           self.votes[0][2],"0"))
        self.assertEqual(48,len(self.select()))  # one replacement available
        self.votes.pop()
        saved=self.boxes[0]
        b=list(saved);b[4]="nan";self.boxes[0]=tuple(b)
        with self.assertRaises(PhotoBaselineError):
            self.select()
        self.boxes[0]=saved
        self.meta[0]=(self.meta[0][0],"validation",
                      "https://creativecommons.org/licenses/by-nc/2.0/","48000","0")
        self.assertEqual(48,len(self.select()))  # rejection, replacement available
    def test_exclusion_validation_and_count_must_be_fixed(self):
        with self.assertRaises(PhotoBaselineError):
            choose_cases(*self.sources(),excluded_ids=frozenset({"invalid"}))
        with self.assertRaises(PhotoBaselineError):
            choose_cases(*self.sources(),excluded_ids=frozenset(),count=7)
    def test_correct_class_and_overlap_required(self):
        case=PublicCase("0000000000000001","book",True,
                        (PublicBox((.1,.2,.5,.8),"0"),))
        idx=TARGETS["book"][1]
        self.assertEqual((1,1),_matched(case,(Proposal(idx,(10.,20.,50.,80.),.9),),100,100))
        self.assertEqual((0,0),_matched(case,(Proposal(idx+1,(10.,20.,50.,80.),.9),),100,100))
        self.assertEqual((1,0),_matched(case,(Proposal(idx,(60.,20.,90.,80.),.9),),100,100))
        self.assertEqual((2,1),_matched(case,(Proposal(idx,(10.,20.,50.,80.),.9),
                                             Proposal(idx,(10.,20.,50.,80.),.8)),100,100))


if __name__=="__main__":
    unittest.main()
