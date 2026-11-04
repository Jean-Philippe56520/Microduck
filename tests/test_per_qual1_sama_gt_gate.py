"""Positive and negative source/selection fixtures for PER-QUAL-1A."""
import io
import json
import unittest
import zipfile

from experiments.per_qual1_sama_gt_gate import (
    TARGETS, SourceGateError, unpack_sama_archive, choose_paired_cohort,
    summarize_ground_truth,
)


def fixture():
    categories = [{"id": i + 1, "name": name.replace("_", " ")}
                  for i, name in enumerate(TARGETS)]
    original = {"categories": categories, "images": [], "annotations": []}
    sama = {"categories": categories, "images": [], "annotations": []}
    a = 1
    for cat in range(len(TARGETS)):
        for n in range(7):
            ident = 1000 + 100*cat+n
            img = {"id": ident, "width": 300, "height": 200,
                   "file_name": f"{ident:012d}.jpg", "license": 4}
            original["images"].append(dict(img))
            sama["images"].append(dict(img))
            for data in (original, sama):
                data["annotations"].append({"id": a, "image_id": ident,
                    "category_id": cat+1, "iscrowd": 0,
                    "bbox": [20,30,90,70]})
                a += 1
    return original, sama


def archive(shards):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for n, data in shards:
            z.writestr(n,json.dumps(data))
    return buf.getvalue()


class SamaSourceGateFixtures(unittest.TestCase):
    def test_frozen_source_and_roster_sha_fail_closed(self):
        from hashlib import sha256
        from experiments.per_qual1_sama_gt_gate import (
            _frozen_sha256, SAMA_ANNOTATION_ZIP_SHA256, FROZEN_COHORT_SHA256)
        self.assertEqual(len(SAMA_ANNOTATION_ZIP_SHA256), 64)
        self.assertEqual(len(FROZEN_COHORT_SHA256), 64)
        raw=b"original public metadata"
        digest=sha256(raw).hexdigest()
        self.assertEqual(_frozen_sha256(raw, digest, "test source"),digest)
        with self.assertRaisesRegex(SourceGateError,"frozen SHA256 mismatch"):
            _frozen_sha256(raw+b"altered",digest,"test source")
        with self.assertRaisesRegex(SourceGateError,"frozen SHA256 mismatch"):
            _frozen_sha256(b"unexpected roster",FROZEN_COHORT_SHA256,"roster")

    def test_maximum_pairing_is_order_independent(self):
        from experiments.per_qual1_sama_gt_gate import _paired_iou50
        original = ((0., 0., 10., 10.), (2., 0., 12., 10.))
        secondary = ((1., 0., 11., 10.), (-2., 0., 8., 10.))
        for left in (original, tuple(reversed(original))):
            for right in (secondary, tuple(reversed(secondary))):
                self.assertEqual(_paired_iou50(left, right), 2)
        self.assertEqual(_paired_iou50(original, ((20., 20., 30., 30.),)), 0)
        self.assertEqual(_paired_iou50((original[0],), (original[0], original[0])), 1)

    def test_disjoint_balance_and_determinism(self):
        o, s = fixture()
        args = dict(old_ids=frozenset(), allowed_license_ids=frozenset({4}))
        first = choose_paired_cohort(o,s,**args)
        self.assertEqual(len(first[0]), 42)
        self.assertEqual(len(set(x[0] for x in first[0])),42)
        self.assertTrue(all(sum(cat==name for _,cat in first[0])==6
                            for name in TARGETS))
        self.assertEqual(42, sum(x["allocated_photos"] for x in
                                 summarize_ground_truth(*first[:4]).values()))
        o["annotations"].reverse()
        s["images"].reverse()
        self.assertEqual(first[0],choose_paired_cohort(o,s,**args)[0])

    def test_exclusions_are_source_only_and_no_quota_change(self):
        o,s=fixture()
        selected=choose_paired_cohort(o,s,old_ids=frozenset(),
                                      allowed_license_ids=frozenset({4}))[0]
        with self.assertRaisesRegex(SourceGateError,"STOP_SOURCE"):
            choose_paired_cohort(o,s,old_ids=frozenset(x[0] for x in selected),
                                allowed_license_ids=frozenset({4}))
        with self.assertRaises(SourceGateError):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset({4}),per_class=5)

    def test_missing_relabelled_box_and_crowd_do_not_become_negative(self):
        o,s=fixture()
        s["annotations"]=[a for a in s["annotations"]
                          if a["category_id"]!=TARGETS.index("cat")+1]
        with self.assertRaisesRegex(SourceGateError,"STOP_SOURCE"):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset({4}))
        o,s=fixture()
        for ann in s["annotations"]:
            if ann["category_id"]==TARGETS.index("cat")+1:
                ann["iscrowd"]=1
        with self.assertRaisesRegex(SourceGateError,"STOP_SOURCE"):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset({4}))

    def test_invalid_source_license_image_geometry_and_class(self):
        o,s=fixture()
        with self.assertRaisesRegex(SourceGateError,"STOP_SOURCE"):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset())
        o,s=fixture()
        s["images"][0]["width"]+=1
        with self.assertRaises(SourceGateError):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset({4}))
        o,s=fixture()
        s["categories"][0]["name"]="dog"
        with self.assertRaises(SourceGateError):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset({4}))
        o,s=fixture()
        for ann in s["annotations"][:2]:
            ann["bbox"][2]=-1
        with self.assertRaises(SourceGateError):
            choose_paired_cohort(o,s,old_ids=frozenset(),
                                allowed_license_ids=frozenset({4}),per_class=6)

    def test_unzip_shards_positive_and_zip_bomb_negative(self):
        o,s=fixture()
        shards=[]
        for i in range(2):
            subset = [x for x in s["images"] if x["id"]%100<4] if i==0 else [x for x in s["images"] if x["id"]%100>=4]
            ids={x["id"] for x in subset}
            shards.append((f"shard{i}.json",{"categories":s["categories"],
                           "images":subset,
                           "annotations":[a for a in s["annotations"] if a["image_id"] in ids]}))
        loaded=unpack_sama_archive(archive(shards))
        self.assertEqual(len(loaded["images"]),49)
        self.assertEqual(len(loaded["annotations"]),49)
        with self.assertRaises(SourceGateError):
            unpack_sama_archive(archive([("../escape.json",s)]))
        with self.assertRaises(SourceGateError):
            unpack_sama_archive(archive([("shard.json",s),("shard.json",s)]))
        with self.assertRaises(SourceGateError):
            unpack_sama_archive(b"not a zip archive" * 8)


if __name__=="__main__":
    unittest.main()
