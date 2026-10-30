"""PER-P8 fixtures: prove the standalone Rust binary does not fabricate masks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from experiments.per_p8_rust_parity import run_rust_once, verify_against_official


class RustParityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
        except ImportError:
            raise unittest.SkipTest("NumPy is optional in the global companion CI") from None
        cls.np = np
        probe = os.environ.get("KWIPI_RUST_PARITY_BIN")
        if not probe or not Path(probe).is_file():
            raise unittest.SkipTest("Rust parity binary available only in P8 CI")
        cls.probe = Path(probe)

    def fake_tensors(self):
        np = self.np
        decoded = np.zeros((1, 300, 38), dtype=np.float32)
        prototype = np.zeros((1, 32, 160, 160), dtype=np.float32)
        decoded[0, 0, :4] = (40, 40, 120, 120)
        decoded[0, 0, 4:6] = (0.75, 1)
        decoded[0, 0, 6] = 1.0
        prototype[0, 0] = 1.0
        return decoded, prototype

    def test_positive_one_square_with_real_rust_execution(self):
        decoded, proto = self.fake_tensors()
        meta, mask = run_rust_once(self.probe, decoded, proto)
        self.assertEqual(meta["count"], 1)
        self.assertEqual(meta["classes"], [1])
        self.assertEqual(mask.shape, (1, 160, 160))
        self.assertEqual(int(mask.sum()), 400)
        self.assertEqual(int(mask[0, 10, 10]), 1)
        self.assertEqual(int(mask[0, 9, 10]), 0)
        self.assertEqual(int(mask[0, 30, 10]), 0)

    def test_vendor_fixture_parity_uses_unmodified_official_decoder(self):
        report = {}
        decoded, proto = self.fake_tensors()
        verify_against_official(decoded, proto, self.probe, report)
        self.assertTrue(report["p8_rust_parity_passed"])
        self.assertEqual(report["p8_mismatched_pixels"], 0)
        self.assertEqual(report["p8_comparison_pixels"], 25600)

    def test_vendor_preserves_detection_source_order_not_score_ranking(self):
        # Pinned Ultralytics end2end NMS takes the first valid rows, never sorts.
        decoded, proto = self.fake_tensors()
        decoded[0, 0, 4:6] = (0.61, 1.0)
        decoded[0, 2, :4] = (160.0, 160.0, 240.0, 240.0)
        decoded[0, 2, 4:6] = (0.99, 3.0)
        decoded[0, 2, 6] = 1.0
        meta, masks = run_rust_once(self.probe, decoded, proto)
        self.assertEqual(meta["classes"], [1, 3])
        self.assertEqual(meta["count"], 2)
        report = {}
        verify_against_official(decoded, proto, self.probe, report)
        self.assertTrue(report["p8_rust_parity_passed"])
        self.assertEqual(report["p8_mismatched_pixels"], 0)

    def test_truncated_float_tensor_is_refused_without_mask(self):
        np = self.np
        with tempfile.TemporaryDirectory(prefix="kwipi-p8-negative-") as tmp:
            base = Path(tmp)
            (base / "out0").write_bytes(b"x" * 3)
            (base / "proto").write_bytes(b"x" * 3)
            dest = base / "must-not-exist.bin"
            result = subprocess.run(
                [str(self.probe), str(base / "out0"), str(base / "proto"), str(dest)],
                capture_output=True, text=True, check=False, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(dest.exists())

    def test_nan_coefficient_and_invalid_boxes_are_refused(self):
        np = self.np
        decoded, proto = self.fake_tensors()
        for selector, value in [(6, float("nan")), (0, -10.0), (4, 1.1), (5, 80.0)]:
            invalid = decoded.copy()
            invalid[0, 0, selector] = value
            with self.assertRaises((ValueError, RuntimeError)):
                run_rust_once(self.probe, invalid, proto)


if __name__ == "__main__":
    unittest.main()
