"""Tests of PER-P6: synthetic ONNX graph only; no vendor weight, robot or camera."""
import tempfile
from pathlib import Path
import unittest

from experiments.per_p6_yolo26seg_tail import make_segment_tail, _require_finite


class TailFixtures(unittest.TestCase):
    def setUp(self):
        try:
            import onnx
            import onnxruntime
            import numpy
        except ImportError:
            self.skipTest("P6 workflow installs ONNX/ORT; generic Python CI may not")
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.heads = [f"head_{i}" for i in range(9)]

    def _source(self, extra=True, invalid_shape=False):
        import onnx
        from onnx import helper, TensorProto

        shape = [1, 300, 38]
        dims = [1, 32, 160, 160] if not invalid_shape else [1, 32, 80, 80]
        nodes = []
        ins = []
        for i, name in enumerate(self.heads):
            src = f"raw_{i}"
            ins.append(helper.make_tensor_value_info(src, TensorProto.FLOAT, shape))
            nodes.append(helper.make_node("Identity", [src], [name], name=f"raw_head_{i}"))
        current = self.heads[0]
        for i in range(1, 9):
            dest = "output0" if i == 8 else f"sum_{i}"
            nodes.append(helper.make_node("Add", [current, self.heads[i]], [dest]))
            current = dest
        if extra:
            ins.append(helper.make_tensor_value_info("proto_src", TensorProto.FLOAT, dims))
            nodes.append(helper.make_node("Identity", ["proto_src"], ["output1"]))
        outs = [helper.make_tensor_value_info("output0", TensorProto.FLOAT, shape)]
        if extra:
            outs.append(helper.make_tensor_value_info("output1", TensorProto.FLOAT, dims))
        model = helper.make_model(
            helper.make_graph(nodes, "minimal_segment", ins, outs),
            opset_imports=[helper.make_operatorsetid("", 19)], ir_version=9
        )
        path = self.root / "source.onnx"
        onnx.save(model, str(path))
        return path

    def test_tail_extraction_and_prototype_passthrough(self):
        import numpy as np
        import onnxruntime as ort
        source = self._source()
        path = self.root / "tail.onnx"
        report = make_segment_tail(source, path, self.heads)
        self.assertGreater(report["tail_bytes"], 0)
        s = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.assertEqual([x.name for x in s.get_inputs()], self.heads + ["rknn_mask_prototypes"])
        self.assertEqual([x.name for x in s.get_outputs()], ["output0", "output1"])
        inputs = {name: np.full((1, 300, 38), i+1, dtype=np.float32)
                  for i, name in enumerate(self.heads)}
        prototypes = np.full((1, 32, 160, 160), 17, dtype=np.float32)
        inputs["rknn_mask_prototypes"] = prototypes
        box, proto = s.run(None, inputs)
        np.testing.assert_array_equal(box, np.full((1,300,38), 45, dtype=np.float32))
        np.testing.assert_array_equal(proto, prototypes)

    def test_missing_prototype_is_refused(self):
        with self.assertRaisesRegex(ValueError, "output0 and output1"):
            make_segment_tail(self._source(extra=False), self.root/"tail.onnx", self.heads)

    def test_wrong_prototype_dims_refused(self):
        with self.assertRaisesRegex(ValueError, "prototype tensor shape"):
            make_segment_tail(self._source(invalid_shape=True), self.root/"tail.onnx", self.heads)

    def test_duplicate_head_refused(self):
        with self.assertRaisesRegex(ValueError, "nine distinct"):
            make_segment_tail(self._source(), self.root/"tail.onnx", self.heads[:-1]+[self.heads[0]])

    def test_unknown_head_refused(self):
        with self.assertRaisesRegex(ValueError, "required raw head"):
            make_segment_tail(self._source(), self.root/"tail.onnx", self.heads[:-1]+["missing"])

    def test_nan_output_refused(self):
        import numpy as np
        with self.assertRaisesRegex(ValueError, "non-finite"):
            _require_finite([np.array([float("nan")], dtype=np.float32)], 1, "negative")
        with self.assertRaisesRegex(ValueError, "wrong output count"):
            _require_finite([], 1, "negative")


if __name__ == "__main__":
    unittest.main()
