"""OEM-FIRST-RK-A1: model output contract tests (no model or private media)."""
from __future__ import annotations

import importlib.util
import unittest

from microduck_companion.rockchip_candidate_probe import (
    CandidateProbeError, _dfl_bins, _nms_indices,
    decode_rockchip, validate_vendor_outputs,
)

HAS_NUMPY = importlib.util.find_spec("numpy") is not None


@unittest.skipUnless(HAS_NUMPY, "NumPy only in candidate evaluation venv")
class RockchipDecodeTests(unittest.TestCase):
    def sample(self):
        import numpy as np
        outs=[]
        for res in (80,40,20):
            outs.extend([
                np.zeros((1,64,res,res), dtype=np.float32),
                np.zeros((1,80,res,res), dtype=np.float32),
                np.zeros((1,1,res,res), dtype=np.float32),
            ])
        return outs

    def test_all_zero_head_has_no_false_ball(self):
        outs=self.sample()
        self.assertEqual(
            decode_rockchip(outs,original_w=640,original_h=640,
                            ratio=1.,pad_left=0,pad_top=0),
            (),
        )

    def test_one_confident_ball_box_and_original_coordinates(self):
        outs=self.sample()
        # Three-sigma DFL distribution centered on 2 bins each side.
        for k in range(4):
            outs[0][0,k*16+2,30,40] = 20.
        outs[1][0,32,30,40] = 0.95  # COCO sports ball
        found=decode_rockchip(
            outs,original_w=640,original_h=640,
            ratio=1.,pad_left=0,pad_top=0
        )
        self.assertEqual(len(found),1)
        self.assertEqual(found[0].category,"sports_ball")
        self.assertAlmostEqual(found[0].confidence,.95,places=5)
        self.assertAlmostEqual(found[0].xyxy[0],308,delta=.5)
        self.assertAlmostEqual(found[0].xyxy[1],228,delta=.5)
        self.assertAlmostEqual(found[0].xyxy[2],340,delta=.5)
        self.assertAlmostEqual(found[0].xyxy[3],260,delta=.5)

    def test_non_target_category_never_becomes_false_cat(self):
        outs=self.sample()
        outs[1][0,8,30,40]=.95  # boat, not cat/dog/person/ball/chair
        self.assertEqual(
            decode_rockchip(outs,original_w=640,original_h=640,
                            ratio=1.,pad_left=0,pad_top=0),(),
        )

    def test_wrong_head_or_nonfinite_rejected(self):
        import numpy as np
        outs=self.sample()
        validate_vendor_outputs(outs)
        with self.assertRaises(CandidateProbeError):
            validate_vendor_outputs(outs[:7])
        outs[1][0,32,30,40]=np.nan
        with self.assertRaises(CandidateProbeError):
            validate_vendor_outputs(outs)

    def test_classwise_nms_preserves_distant_boxes(self):
        import numpy as np
        boxes=np.asarray([[0,0,20,20],[2,2,18,18],
                          [100,100,120,120]],dtype=np.float32)
        scores=np.asarray([.95,.80,.70],dtype=np.float32)
        self.assertEqual(_nms_indices(boxes,scores),[0,2])

    def test_stable_softmax_dfl_for_large_logits(self):
        import numpy as np
        position=np.zeros((1,64,1,1),dtype=np.float32)
        position[:,3,0,0]=100.
        reg=_dfl_bins(position)
        self.assertEqual(reg.shape,(4,1,1))
        self.assertTrue(np.isfinite(reg).all())
        self.assertAlmostEqual(float(reg[0,0,0]),3.,places=5)


if __name__=="__main__":
    unittest.main()
