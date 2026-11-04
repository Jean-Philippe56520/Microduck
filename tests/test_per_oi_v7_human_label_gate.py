"""OI-V7-HUMAN-1 source-only positive and negative fixture tests."""
from __future__ import annotations
import base64
import csv
from pathlib import Path
import tempfile
import unittest

from experiments.per_oi_v7_human_label_gate import qualify_metadata, OpenImagesSourceStop, TARGETS


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

class TestOIV7HumanLabels(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        root = Path(self.t.name)
        self.paths = {key: root/(key+'.csv') for key in ('classes','images','boxes','human')}
        self.mids = {n:'/m/'+f'{i+1:05d}' for i,n in enumerate(TARGETS)}
        self.classes = [{'LabelName':self.mids[n], 'DisplayName':n} for n in TARGETS]
        self.classes += [{'LabelName':'/m/'+str(i+1000), 'DisplayName':f'other-{i}'} for i in range(110)]
        self.images = []
        for i in range(1,1005):
            self.images.append({'ImageID':f'{i:016x}', 'Subset':'validation',
                'OriginalURL':f'https://example.org/{i}.jpg',
                'OriginalLandingURL':f'https://example.org/photo/{i}',
                'License':'https://creativecommons.org/licenses/by/2.0/',
                'OriginalMD5':base64.b64encode(i.to_bytes(16,'big')).decode(),
                'Rotation':'0'})
        self.boxes=[]
        self.human=[]
        for i,n in enumerate(TARGETS,1):
            self.boxes.append(dict(ImageID=f'{i:016x}', LabelName=self.mids[n], Source='xclick',
                Confidence='1',XMin='0.1',XMax='0.7',YMin='0.2',YMax='0.8',
                IsGroupOf='0',IsDepiction='0',IsInside='0'))
            self.human.append(dict(ImageID=f'{i:016x}', Source='verification',
                LabelName=self.mids[n],Confidence='1'))
            self.human.append(dict(ImageID=f'{i+30:016x}', Source='verification',
                LabelName=self.mids[n],Confidence='0'))
        for i in range(101,205):
            self.human.append(dict(ImageID=f'{i:016x}',Source='verification',
                LabelName=self.mids['Book'],Confidence='0'))
        self.flush()

    def flush(self):
        write_csv(self.paths['classes'], ['LabelName','DisplayName'], self.classes)
        write_csv(self.paths['images'], ['ImageID','Subset','OriginalURL','OriginalLandingURL','License','OriginalMD5','Rotation'], self.images)
        write_csv(self.paths['boxes'], ['ImageID','LabelName','Source','Confidence','XMin','XMax','YMin','YMax','IsGroupOf','IsDepiction','IsInside'], self.boxes)
        write_csv(self.paths['human'], ['ImageID','Source','LabelName','Confidence'], self.human)

    def run_qualify(self):
        return qualify_metadata(*(self.paths[k] for k in ('classes','images','boxes','human')))

    def test_positive_count_and_unknown_labels_not_negatives(self):
        r = self.run_qualify()
        self.assertEqual('STOP_GT_POOL_LT6_NOT_LICENSED',r['status'])
        self.assertEqual(1004,r['validation_image_metadata_rows'])
        self.assertEqual(1,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])
        self.assertEqual(1,r['per_target']['Tennis ball']['human_negative'])
        self.assertEqual(0,r['per_target']['Cat']['boxed_without_human_positive'])
        self.assertEqual(0,r['real_pixels_loaded'])
        self.assertFalse(r['cohort_selected'])
        self.assertFalse(r['rights_verified_individually'])
        self.assertFalse(r['cross_corpus_dedup_verified'])
        self.assertFalse(r['six_per_class_possible_from_metadata'])

    def test_negative_box_without_verified_positive_not_candidate(self):
        self.human = [x for x in self.human if x['ImageID']!='0000000000000007']
        self.flush(); r=self.run_qualify()
        self.assertEqual(0,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])
        self.assertEqual(1,r['per_target']['Tennis ball']['boxed_without_human_positive'])

    def test_positive_decimal_binary_values_still_verified(self):
        for row in self.human:
            row['Confidence'] = ('1.000000' if row['Confidence']=='1' else '0.000000')
        self.flush(); r=self.run_qualify()
        self.assertEqual(1,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])

    def test_negative_fractional_human_label_refused(self):
        self.human[0]['Confidence']='0.5'
        self.flush()
        with self.assertRaisesRegex(OpenImagesSourceStop,'nonbinary verified label'):
            self.run_qualify()

    def test_negative_human_label_conflict_excluded(self):
        self.human.append(dict(ImageID='0000000000000007',Source='crowdsource-verification',
                               LabelName=self.mids['Tennis ball'],Confidence='0'))
        self.flush(); r=self.run_qualify()
        self.assertEqual(0,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])
        self.assertEqual(1,r['per_target']['Tennis ball']['conflicting_human_labels_excluded'])

    def test_negative_nonhuman_source_stops(self):
        self.human[0]['Source']='machine'; self.flush()
        with self.assertRaisesRegex(OpenImagesSourceStop,'non-human'):
            self.run_qualify()

    def test_negative_license_and_duplicate_md5_exclude(self):
        self.images[6]['License']='https://creativecommons.org/licenses/by-nc/2.0/'
        self.images[1]['OriginalMD5']=self.images[0]['OriginalMD5']
        self.flush(); r=self.run_qualify()
        self.assertEqual(0,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])
        self.assertEqual(0,r['per_target']['Cat']['candidate_boxed_and_human_positive'])
        self.assertEqual(2,r['excluded_metadata'])

    def test_negative_gt_depiction_or_group_does_not_count(self):
        self.boxes[6]['IsDepiction']='1'
        self.flush(); r=self.run_qualify()
        self.assertEqual(0,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])

    def test_negative_unknown_target_mid_stops(self):
        self.classes[6]['DisplayName']='unverified generic ball'
        self.flush()
        with self.assertRaisesRegex(OpenImagesSourceStop,'incomplete target'):
            self.run_qualify()

    def test_negative_wrong_pin_stops(self):
        with self.assertRaisesRegex(OpenImagesSourceStop,'pinned CSVs drifted'):
            qualify_metadata(*(self.paths[k] for k in ('classes','images','boxes','human')),
                            require_official_pins=True)

    def test_negative_invalid_coordinate_excluded(self):
        self.boxes[6]['XMin']='nan'
        self.flush(); r=self.run_qualify()
        self.assertEqual(1,r['invalid_target_boxes_excluded'])
        self.assertEqual(0,r['per_target']['Tennis ball']['candidate_boxed_and_human_positive'])

    def test_negative_symlink_source_stops(self):
        linked=self.paths['human'].with_name('labels-link.csv')
        linked.symlink_to(self.paths['human'])
        with self.assertRaisesRegex(OpenImagesSourceStop,'symlinked'):
            qualify_metadata(self.paths['classes'],self.paths['images'],self.paths['boxes'],linked)

    def test_positive_six_per_class_still_not_qualified(self):
        for i,name in enumerate(TARGETS):
            for k in range(5):
                ident=f'{200+i*10+k:016x}'
                item=self.boxes[i].copy(); item['ImageID']=ident
                self.boxes.append(item)
                self.human.append(dict(ImageID=ident, Source='verification',
                                       LabelName=self.mids[name],Confidence='1'))
        self.flush(); r=self.run_qualify()
        self.assertEqual('METADATA_42_POSSIBLE_NOT_LICENSED',r['status'])
        self.assertTrue(r['six_per_class_possible_from_metadata'])
        self.assertFalse(r['rights_verified_individually'])
        self.assertFalse(r['cohort_selected'])

if __name__=='__main__': unittest.main()
