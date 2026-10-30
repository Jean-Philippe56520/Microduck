"""PER-P5 source gate tests. No actual model, RKNN device or private media."""
import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from experiments.per_p5_yolo26_rknn_compat import (
    CALIBRATION_COUNT, MODELS, verify_sources, _cropped_head_outputs,
)


class TestPerP5ReadOnlyGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.weights = self.root / "yolo26n.pt"
        self.weights.write_bytes(b"fake-official-content")
        self.cal = self.root / "coco_subset_20.txt"
        subset = self.root / "subset"
        subset.mkdir()
        paths = []
        for idx in range(CALIBRATION_COUNT):
            photo = subset / f"{idx:02d}.jpg"
            photo.write_bytes(b"not-a-real-photo" * 10)
            paths.append(f"./subset/{photo.name}")
        self.cal.write_text("\n".join(paths), encoding="utf-8")
        # Pin the fixture hash so negative calibration tests reach the intended gate.
        self.fixture_sha = __import__("hashlib").sha256(self.weights.read_bytes()).hexdigest()
        self.fixture_patch = patch.dict(MODELS, {"yolo26n.pt": self.fixture_sha})
        self.fixture_patch.start()
        self.addCleanup(self.fixture_patch.stop)

    def test_positive_on_expected_sha_for_fixture_only(self):
        # It proves validation logic, not authenticity of a vendor model.
        with patch.dict(MODELS, {"yolo26n.pt": __import__("hashlib").sha256(
            self.weights.read_bytes()).hexdigest()}):
            result = verify_sources(self.weights, self.cal)
        self.assertEqual(result["calibration_count"], 20)

    def test_wrong_model_sha_is_rejected(self):
        with patch.dict(MODELS, {"yolo26n.pt": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                verify_sources(self.weights, self.cal)

    def test_unknown_model_is_rejected(self):
        other = self.root / "arbitrary.pt"
        other.write_bytes(b"foo")
        with self.assertRaisesRegex(ValueError, "unapproved"):
            verify_sources(other, self.cal)

    def test_calibration_count_and_duplicate_are_refused(self):
        good = self.cal.read_text()
        self.cal.write_text("\n".join(good.splitlines()[:-1]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "count"):
            verify_sources(self.weights, self.cal)
        self.cal.write_text("\n".join([good.splitlines()[0]] * 20), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "count"):
            verify_sources(self.weights, self.cal)

    def test_calibration_escape_is_rejected(self):
        lines = self.cal.read_text().splitlines()
        lines[0] = "../secret.jpg"
        self.cal.write_text("\n".join(lines), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected calibration"):
            verify_sources(self.weights, self.cal)

    def test_missing_calibration_file_is_rejected(self):
        (self.root / "subset" / "00.jpg").unlink()
        with self.assertRaisesRegex(ValueError, "missing/unsafe"):
            verify_sources(self.weights, self.cal)



class TestSameBuilderRKNNHeadSelection(unittest.TestCase):
    @staticmethod
    def _graph(heads=6, segment=False):
        nodes = []
        for i in range(heads):
            signal = f"raw_head_{i}"
            nodes.append(SimpleNamespace(op_type="Conv",
                                         name=f"/model.23/one2one_cv3.{i}/Conv",
                                         output=[signal], input=[]))
            nodes.append(SimpleNamespace(op_type="Reshape",
                                         name=f"/tail/{i}", input=[signal],
                                         output=[f"reshaped_{i}"]))
        graph_outputs = [SimpleNamespace(name="output0")]
        if segment:
            graph_outputs.append(SimpleNamespace(name="output1"))
        return SimpleNamespace(node=nodes, output=graph_outputs)

    def test_detection_has_six_raw_heads(self):
        g = self._graph(6)
        self.assertEqual(len(_cropped_head_outputs(g, "/model.23/", "detect")), 6)

    def test_segmentation_keeps_prototype_output_separate(self):
        g = self._graph(9, segment=True)
        names = _cropped_head_outputs(g, "/model.23/", "segment")
        self.assertEqual(len(names), 10)
        self.assertEqual(names[-1], "output1")

    def test_missing_head_is_refused_not_fabricated(self):
        with self.assertRaisesRegex(RuntimeError, "head count"):
            _cropped_head_outputs(self._graph(5), "/model.23/", "detect")

    def test_missing_segmentation_prototype_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "prototype outputs"):
            _cropped_head_outputs(self._graph(9), "/model.23/", "segment")

    def test_unexpected_task_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unexpected task"):
            _cropped_head_outputs(self._graph(6), "/model.23/", "depth")


if __name__ == "__main__":
    unittest.main()
