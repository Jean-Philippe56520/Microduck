"""Build ephemeral ONNX ten-input fixture. No model weights/images."""
import argparse
from pathlib import Path

NAMES = [
    f"/model.23/one2one_cv{head}.{stage}/one2one_cv{head}.{stage}.2/Conv_output_0"
    for head in (2, 3, 4) for stage in range(3)
]
SHAPES = [
    [1,4,80,80], [1,4,40,40], [1,4,20,20],
    [1,80,80,80], [1,80,40,40], [1,80,20,20],
    [1,32,80,80], [1,32,40,40], [1,32,20,20],
    [1,32,160,160],
]

def build(path: Path) -> None:
    import numpy as np
    import onnx
    from onnx import helper, TensorProto, numpy_helper
    names = NAMES + ["rknn_mask_prototypes"]
    inputs = [helper.make_tensor_value_info(name, TensorProto.FLOAT, shape)
              for name, shape in zip(names, SHAPES)]
    boxes = np.zeros((1,300,38), dtype=np.float32)
    boxes[0,0,:7] = [240,80,280,120,0.9,32,1]
    nodes = [helper.make_node("Constant", [], ["constant_boxes"],
                              value=numpy_helper.from_array(boxes, name="boxes"))]
    # Every head is consumed in the model graph; keep zero-headed fixture
    # deterministic, no image/model dependency.
    current = "constant_boxes"
    for i, name in enumerate(NAMES):
        nodes.append(helper.make_node("ReduceMean", [name], [f"mean_{i}"], keepdims=0))
        nodes.append(helper.make_node("Mul", [f"mean_{i}", "epsilon"], [f"scale_{i}"]))
        dest = "output0" if i == 8 else f"sum_{i}"
        nodes.append(helper.make_node("Add", [current, f"scale_{i}"], [dest]))
        current = dest
    nodes.append(helper.make_node("Identity", ["rknn_mask_prototypes"], ["output1"]))
    model = helper.make_model(helper.make_graph(nodes, "P10B synthetic tail", inputs,
        [helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1,300,38]),
         helper.make_tensor_value_info("output1", TensorProto.FLOAT, [1,32,160,160])],
        initializer=[numpy_helper.from_array(np.array(1e-6, dtype=np.float32), name="epsilon")]),
        opset_imports=[helper.make_operatorsetid("", 19)], ir_version=9)
    onnx.checker.check_model(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(path))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    build(p.parse_args().out)
