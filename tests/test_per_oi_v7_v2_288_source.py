"""PER-OI-V7-V2-SRC-0 positive/negative fixtures; no Internet or inference."""
from __future__ import annotations

import base64
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from experiments import per_oi_v7_v2_288_source as v2
from experiments.per_oi_v7_source_inventory import OpenImagesSourceStop


def save_csv(path, headers, rows):
    with path.open("w",encoding="utf-8",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=headers)
        writer.writeheader();writer.writerows(rows)


class V2SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_positive_static_and_landing_flickr_photo_identity(self):
        self.assertEqual("1234567890",v2.flickr_id("https://farm1.staticflickr.com/11/1234567890_abc.jpg"))
        self.assertEqual("1234567890",v2.flickr_id("http://live.staticflickr.com/3/1234567890_abc_b.jpg"))
        self.assertEqual("1234567890",v2.flickr_id("https://www.flickr.com/photos/j/1234567890/"))
        self.assertEqual("1234567890",v2.flickr_id("https://flickr.com/photo.gne?id=1234567890"))

    def test_negative_flickr_identity_refuses_external_host_and_credentials(self):
        for url in ("https://farm1.staticflickr.com.attacker.net/12345_a.jpg",
                    "https://user@farm1.staticflickr.com/12345_a.jpg",
                    "https://example.com/photos/u/12345",
                    "ftp://farm1.staticflickr.com/12345_a.jpg",
                    "https://flickr.com/photos/j/not-an-id"):
            with self.subTest(url=url):
                self.assertIsNone(v2.flickr_id(url))

    def test_positive_coco_flickr_json_uses_url_not_coco_numeric_id(self):
        path=self.root/"coco.json"
        path.write_text(json.dumps({"images":[
            {"id":1,"flickr_url":"http://farm2.staticflickr.com/33/1234567890_abcd.jpg"},
            {"id":2,"flickr_url":"https://live.staticflickr.com/2/2345678901_abcd.jpg"}
        ]}),encoding="utf-8")
        ids,missing=v2.coco_val_flickr_ids(path,expected=2)
        self.assertEqual({"1234567890","2345678901"},ids)
        self.assertEqual(0,missing)

    def test_negative_duplicate_coco_id_rejected(self):
        path=self.root/"coco.json"
        path.write_text(json.dumps({"images":[{"id":3,"flickr_url":"https://farm1.staticflickr.com/1/11111_a.jpg"},
            {"id":3,"flickr_url":"https://farm1.staticflickr.com/1/22222_b.jpg"}]}),encoding="utf-8")
        with self.assertRaisesRegex(OpenImagesSourceStop,"duplicate COCO"):
            v2.coco_val_flickr_ids(path,expected=2)

    def test_negative_unrecognized_coco_flickr_counted_unknown(self):
        path=self.root/"coco.json"
        path.write_text(json.dumps({"images":[
            {"id":1,"flickr_url":"https://other.example.org/no-flickr"}
        ]}),encoding="utf-8")
        ids,missing=v2.coco_val_flickr_ids(path,expected=1)
        self.assertEqual(set(),ids);self.assertEqual(1,missing)

    def fake_boxed(self,n=7):
        return {(f"{i*100+j+1:016x}",name):1
                for i,name in enumerate(v2.TARGETS) for j in range(n)}

    def test_positive_new_seeded_42_unique_not_from_old_ids(self):
        boxed=self.fake_boxed()
        first,pools,fail=v2.select_v2(boxed,frozenset())
        second,_,_=v2.select_v2(boxed,frozenset())
        self.assertEqual(first,second)
        self.assertIsNone(fail)
        self.assertEqual(42,len(first))
        self.assertEqual(42,len({x[0] for x in first}))
        self.assertEqual({n:7 for n in v2.TARGETS},pools)

    def test_negative_excluded_consumed_image_never_selected(self):
        boxed=self.fake_boxed()
        old=frozenset((f"{i*100+1:016x}" for i in range(len(v2.TARGETS))))
        selected,_,failure=v2.select_v2(boxed,old)
        self.assertIsNone(failure)
        self.assertFalse({ident for ident,_ in selected}&old)
        self.assertEqual(42,len(selected))

    def test_negative_tennis_ball_shortage_is_stop_not_lower_quota(self):
        boxed=self.fake_boxed(n=6)
        old={f"{1:016x}"}
        selected,pool,failure=v2.select_v2(boxed,old)
        self.assertFalse(selected)
        self.assertEqual("Tennis ball",failure)

    def test_negative_changed_seed_rejected(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,"seed"):
            v2.select_v2(self.fake_boxed(),set(),seed="model-chosen-seed")

    def test_negative_multi_label_same_image_cannot_be_allocated_twice(self):
        boxed=self.fake_boxed(n=6)
        # A given ID appears as the only sixth photo for both target classes.
        shared=f"{999:016x}"
        boxed.pop((f"{6:016x}","Tennis ball"))
        boxed.pop((f"{106:016x}","Book"))
        boxed[(shared,"Tennis ball")]=1
        boxed[(shared,"Book")]=1
        selected,_,failure=v2.select_v2(boxed,set())
        self.assertFalse(selected)
        self.assertIn(failure,("Tennis ball","Book"))

    def test_negative_class_name_taxonomy_missing(self):
        path=self.root/"classes.csv"
        save_csv(path,("LabelName","DisplayName"),[
            {"LabelName":f"/m/{i:04x}","DisplayName":n}
            for i,n in enumerate(v2.TARGETS[:-1])
        ])
        with self.assertRaisesRegex(OpenImagesSourceStop,"missing target"):
            v2._taxonomy(path)

    def _vote_fixture(self, confidence="1.000000", source="verification", conflict=False):
        path=self.root/"human.csv"
        rows=[dict(ImageID=f"{1:016x}",Source=source,LabelName="/m/1",Confidence=confidence)]
        if conflict:
            rows.append(dict(ImageID=f"{1:016x}",Source="crowdsource-verification",
                             LabelName="/m/1",Confidence="0"))
        save_csv(path,("ImageID","Source","LabelName","Confidence"),rows)
        return path

    def test_positive_exact_human_binary_with_bbox_candidate(self):
        self.assertEqual(frozenset({(f"{1:016x}","Tennis ball")}),
            v2._human_positive(self._vote_fixture(),{"Tennis ball":"/m/1"},{f"{1:016x}"}))

    def test_negative_human_conflict_excluded(self):
        r=v2._human_positive(self._vote_fixture(conflict=True),
                             {"Tennis ball":"/m/1"},{f"{1:016x}"})
        self.assertEqual(0,len(r))

    def test_negative_fractional_human_vote_refused(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,"nonbinary"):
            v2._human_positive(self._vote_fixture(confidence="0.25"),
                               {"Tennis ball":"/m/1"},{f"{1:016x}"})

    def test_negative_machine_source_refused(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,"not human"):
            v2._human_positive(self._vote_fixture(source="machine"),
                               {"Tennis ball":"/m/1"},{f"{1:016x}"})

    def test_positive_box_and_negative_depiction_filter(self):
        path=self.root/"boxes.csv"
        normal=dict(ImageID=f"{1:016x}",LabelName="/m/1",Source="xclick",Confidence="1",
                    XMin="0.1",XMax="0.8",YMin="0.2",YMax="0.7",
                    IsGroupOf="0",IsDepiction="0",IsInside="0")
        depicted={**normal,"ImageID":f"{2:016x}","IsDepiction":"1"}
        save_csv(path,normal.keys(),[normal,depicted])
        r=v2._valid_boxes(path,{"Tennis ball":"/m/1"},
                         frozenset({(f"{1:016x}","Tennis ball"),
                                    (f"{2:016x}","Tennis ball")}))
        self.assertEqual(1,r[(f"{1:016x}","Tennis ball")])
        self.assertNotIn((f"{2:016x}","Tennis ball"),r)

    def test_negative_invalid_box_does_not_qualify(self):
        path=self.root/"boxes.csv"
        box=dict(ImageID=f"{1:016x}",LabelName="/m/1",Source="xclick",Confidence="1",
                 XMin="nan",XMax="0.8",YMin="0.2",YMax="0.7",
                 IsGroupOf="0",IsDepiction="0",IsInside="0")
        save_csv(path,box.keys(),[box])
        self.assertFalse(v2._valid_boxes(path,{"Tennis ball":"/m/1"},
                         frozenset({(f"{1:016x}","Tennis ball")})))

    def test_source_filter_excludes_all_md5_duplicates_and_coco_flickr(self):
        def rows():
            for i in range(1,41621):
                digest=4 if i==3 else i
                yield dict(
                    ImageID=f"{i:016x}",Subset="validation",
                    License="https://creativecommons.org/licenses/by/2.0/",
                    OriginalMD5=base64.b64encode(digest.to_bytes(16,"big")).decode(),
                    Rotation="0",
                    OriginalURL=f"https://farm1.staticflickr.com/1/{10000000+i}_abcd.jpg",
                    OriginalLandingURL=f"https://www.flickr.com/photos/a/{10000000+i}/")
        with mock.patch.object(v2,"_rows",return_value=rows()):
            out,stats=v2._eligible_images(Path("fixture.csv"),
                old=frozenset({f"{5:016x}"}),coco_flickr={str(10000006)})
        self.assertNotIn(f"{3:016x}",out)
        self.assertNotIn(f"{4:016x}",out)
        self.assertNotIn(f"{5:016x}",out)
        self.assertNotIn(f"{6:016x}",out)
        self.assertEqual(41616,len(out))
        self.assertEqual(2,stats["removed_md5_duplicates_all_copies"])
        self.assertEqual(1,stats["excluded_coco_flickr_collisions"])


    def _flickr_identity_cases(self):
        """Pure fixtures: 42 selected, 288 old under different Open Images IDs."""
        selected=frozenset(f"{i+1:016x}" for i in range(42))
        historical=frozenset(f"{i+1000:016x}" for i in range(288))
        rows=[]
        for i,ident in enumerate(sorted(selected | historical)):
            photo=str(90000000+i)
            rows.append({
                "ImageID":ident,
                "OriginalURL":f"https://farm1.staticflickr.com/11/{photo}_abcd.jpg",
                "OriginalLandingURL":f"https://www.flickr.com/photos/a/{photo}/",
                "OriginalMD5":base64.b64encode((i+1).to_bytes(16,"big")).decode(),
            })
        return rows,selected,historical

    def _identity_result(self, rows, selected, historical, coco=()):
        return v2.audit_flickr_identity_rows(
            rows,selected_ids=selected,historical_ids=historical,
            coco_photo_ids=set(coco))

    def test_positive_identity_unique_across_exact_42_and_288(self):
        rows,selected,historical=self._flickr_identity_cases()
        result=self._identity_result(rows,selected,historical)
        self.assertEqual("V2_FLICKR_IDENTITY_CLEAN_METADATA_ONLY",result["status"])
        self.assertEqual(42,result["selected_ids_with_consistent_flickr_and_md5"])
        self.assertEqual(288,result["historical_ids_with_consistent_flickr_and_md5"])
        self.assertTrue(result["source_identity_clean"])
        self.assertFalse(result["individual_image_rights_verified"])
        self.assertFalse(result["perceptual_near_duplicates_verified"])
        self.assertEqual(0,result["real_pixels_loaded"])

    def test_negative_same_flickr_under_distinct_selected_ids(self):
        rows,selected,historical=self._flickr_identity_cases()
        rows[0]["OriginalURL"]=rows[1]["OriginalURL"]
        rows[0]["OriginalLandingURL"]=rows[1]["OriginalLandingURL"]
        result=self._identity_result(rows,selected,historical)
        self.assertEqual(1,result["within_selected_same_flickr_photo_aliases"])
        self.assertFalse(result["source_identity_clean"])

    def test_negative_historical_flickr_alias_even_with_distinct_md5(self):
        rows,selected,historical=self._flickr_identity_cases()
        i=next(i for i,r in enumerate(rows) if r["ImageID"] in historical)
        j=next(i for i,r in enumerate(rows) if r["ImageID"] in selected)
        rows[j]["OriginalURL"]=rows[i]["OriginalURL"]
        rows[j]["OriginalLandingURL"]=rows[i]["OriginalLandingURL"]
        result=self._identity_result(rows,selected,historical)
        self.assertEqual(1,result["selected_duplicated_flickr_with_historical"])
        self.assertEqual(0,result["selected_duplicated_md5_with_historical"])
        self.assertFalse(result["source_identity_clean"])

    def test_negative_historical_md5_alias_even_with_distinct_flickr(self):
        rows,selected,historical=self._flickr_identity_cases()
        i=next(i for i,r in enumerate(rows) if r["ImageID"] in historical)
        j=next(i for i,r in enumerate(rows) if r["ImageID"] in selected)
        rows[j]["OriginalMD5"]=rows[i]["OriginalMD5"]
        result=self._identity_result(rows,selected,historical)
        self.assertEqual(1,result["selected_duplicated_md5_with_historical"])
        self.assertEqual(0,result["selected_duplicated_flickr_with_historical"])
        self.assertFalse(result["source_identity_clean"])

    def test_negative_two_source_urls_disagree_on_flickr(self):
        rows,selected,historical=self._flickr_identity_cases()
        j=next(i for i,r in enumerate(rows) if r["ImageID"] in selected)
        rows[j]["OriginalLandingURL"]="https://www.flickr.com/photos/a/999999999/"
        result=self._identity_result(rows,selected,historical)
        self.assertEqual(1,result["unreadable_source_rows"])
        self.assertFalse(result["source_identity_complete"])

    def test_negative_missing_historical_metadata_never_becomes_zero_collision(self):
        rows,selected,historical=self._flickr_identity_cases()
        missing=next(iter(historical))
        rows=[row for row in rows if row["ImageID"]!=missing]
        result=self._identity_result(rows,selected,historical)
        self.assertEqual(287,result["historical_ids_with_consistent_flickr_and_md5"])
        self.assertFalse(result["source_identity_clean"])

    def test_negative_coco_photo_alias_rejected(self):
        rows,selected,historical=self._flickr_identity_cases()
        j=next(i for i,r in enumerate(rows) if r["ImageID"] in selected)
        coco={v2.flickr_id(rows[j]["OriginalURL"])}
        result=self._identity_result(rows,selected,historical,coco=coco)
        self.assertEqual(1,result["selected_duplicated_flickr_with_coco_val"])
        self.assertFalse(result["source_identity_clean"])

    def test_negative_duplicate_metadata_row_rejected(self):
        rows,selected,historical=self._flickr_identity_cases()
        rows.append(dict(rows[0]))
        result=self._identity_result(rows,selected,historical)
        self.assertEqual(1,result["duplicate_source_rows"])
        self.assertFalse(result["source_identity_clean"])



if __name__=="__main__": unittest.main()
