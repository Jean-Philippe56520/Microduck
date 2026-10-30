"""PER-P2A host fixtures; no file download or ONNX runtime required."""
from __future__ import annotations

from io import BytesIO
from unittest import TestCase, main
from unittest.mock import patch

from experiments import per_p2a_onnx_contract as p2


GOOD = [
    [1, 4, 80, 80], [1, 80, 80, 80],
    [1, 4, 40, 40], [1, 80, 40, 40],
    [1, 4, 20, 20], [1, 80, 20, 20],
]


class P2ContractFixtures(TestCase):
    def test_predeclared_rockchip_six_tensor_candidate(self):
        meta = p2.validate_shapes([[1, 3, 640, 640]], GOOD)
        self.assertTrue(meta["rockchip_ppyoloe_example_shape_match"])
        self.assertFalse(meta["oem_duck_detect_head_compatible"])
        self.assertEqual(80, meta["class_channels"])
        self.assertEqual({"20": [4, 80], "40": [4, 80], "80": [4, 80]},
                         meta["channels_by_scale"])

    def test_nine_outputs_with_optional_single_channel_branch(self):
        with_extra = GOOD + [[1, 1, i, i] for i in (80, 40, 20)]
        self.assertEqual(9, p2.validate_shapes(
            [[1, 3, 640, 640]], with_extra)["outputs"])

    def test_monoclass_oem_head_rejected_instead_of_misidentified(self):
        with self.assertRaises(ValueError):
            p2.validate_shapes([[1, 3, 320, 320]], [[1, 5, 2100]])
        with self.assertRaises(ValueError):
            p2.validate_shapes([[1, 3, 640, 640]], [[1, 5, 2100]])

    def test_dynamic_or_nhwc_input_rejected(self):
        for x in ([[1, 3, 0, 640]], [[1, 640, 640, 3]],
                  [[1, 3, 416, 416]], [[-1, 3, 640, 640]]):
            with self.subTest(shape=x):
                with self.assertRaises(ValueError):
                    p2.validate_shapes(x, GOOD)

    def test_missing_class_map_or_stride_or_duplicate_outputs_refused(self):
        wrong = [
            GOOD[:4],
            GOOD[:-1] + [[1, 5, 20, 20]],
            GOOD[:-1] + [[1, 80, 10, 10]],
            GOOD[:-1] + [[1, 4, 20, 20]],
            GOOD[:-1] + [[1, 80, 40, 40]],
        ]
        for heads in wrong:
            with self.subTest(heads=heads):
                with self.assertRaises(ValueError):
                    p2.validate_shapes([[1, 3, 640, 640]], heads)

    def test_nonfinite_wrong_dimensions_and_fake_class_accepted_never(self):
        for dims in (
            [1, 80, 80, float("nan")], [1, 80, 80, None],
            [1, 80, 80, True], [1, 80, -80, 80],
        ):
            with self.subTest(dims=dims):
                modified = GOOD[:]
                modified[1] = dims
                with self.assertRaises(ValueError):
                    p2.validate_shapes([[1, 3, 640, 640]], modified)

    def test_exact_https_only_and_refuse_unapproved_redirect(self):
        p2.require_authorized_url(p2.OFFICIAL_URL)
        bad = (
            "http://ftrg.zbox.filez.com/v2/delivery/data/foo",
            "https://malicious.invalid/ppyoloe_s.onnx",
            "https://ftrg.zbox.filez.com.evil.invalid/x",
            "https://ftrg.zbox.filez.com:444/",
            "https://ftrg.zbox.filez.com/v2/delivery/data/unknown/x",
            p2.OFFICIAL_URL + "?replace=1",
            "https://alice@ftrg.zbox.filez.com/v2/delivery/data/x",
        )
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                p2.require_authorized_url(url)

    def test_bounded_model_read_positive_negative(self):
        with patch.object(p2, "MIN_MODEL_BYTES", 4), patch.object(
                p2, "MAX_MODEL_BYTES", 16):
            self.assertEqual(b"ABCD", p2.bounded_read(BytesIO(b"ABCD")))
            with self.assertRaisesRegex(ValueError, "too small"):
                p2.bounded_read(BytesIO(b"ABC"))
            with self.assertRaisesRegex(ValueError, "64 MiB"):
                p2.bounded_read(BytesIO(b"x"*17))
            self.assertEqual(b"x"*16, p2.bounded_read(BytesIO(b"x"*16)))


if __name__ == "__main__":
    main()
