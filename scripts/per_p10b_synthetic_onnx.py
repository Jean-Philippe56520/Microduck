"""Generate ONLY synthetic ONNX graphs for the P10B Rust ORT CI test.

All images/models/weights are absent. The ten inputs match P5, and the
graph uses all nine heads numerically. Files stay under RUNNER_TEMP.
"""
from __future__ import annotations

import argparse
from pathlib import Path

HEADS = [
    "/model.23/one2one_cv2.0/one2one_cv2.0.2/Conv_output_0",
    "/model.23/one2one_cv2.1/one2one_cv2.1.2/Conv_output_0",
    "/model.23/one2one_cv2.2/one2one_cv2.2.2/Conv_output_0",
    "/model.23/one2one_cv3.0/one2one_cv3.0.2/Conv_output_0",
    "/model.23/one2one_cv3.1/one2one_cv3.1.2/Conv_output_0",
    "/model.23/one2one_cv3.2/one2one_cv3.2.2/Conv_output_0",
    "/model.23/one2one_cv4.0/one2one_cv4.0.2/Conv_output_0",
    "/model.23/one2one_cv4.1/one2one_cv4.1.2/Conv_output_0",
    "/model.23/one2one_cv4.2/one2one_cv4.2.2/Conv_output_0",
]
SHAPES = [
    (1, 4, 80, 80), (1, 4, 40, 40), (1, 4, 20, 20),
    (1, 80, 80, 80), (1, 80, 40, 40), (1, 80, 20, 20),
    (1, 32, 80, 80), (1, 32, 40, 40), (1, 32, 20, 20),
]
PROTOS = (1, 32, 160, 160)


def build(path: Path, variant: str = "valid") -> None:
    import onnx
    import numpy as np
    from onnx import TensorProto, helper, numpy_helper

    names = HEADS.copy()
    shapes = list(SHAPES)
    rows = 300
    proto_shape = PROTOS
    proto_type = TensorProto.FLOAT
    if variant == "wrong_name":
        names[2] = "incorrect_head_2"
    elif variant == "wrong_shape":
        shapes[3] = (1, 80, 80, 79)
    elif variant == "wrong_proto_dtype":
        proto_type = TensorProto.DOUBLE
    elif variant == "wrong_proto_shape":
        proto_shape = (1, 32, 80, 80)
    elif variant == "wrong_output":
        rows = 299
    elif variant != "valid":
        raise ValueError("unknown synthetic ONNX variant")

    ins = [
        helper.make_tensor_value_info(n, TensorProto.FLOAT, shape)
        for n, shape in zip(names, shapes)
    ]
    ins.append(helper.make_tensor_value_info(
        "rknn_mask_prototypes", proto_type, proto_shape
    ))
    outs = [
        helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, rows, 38]),
        helper.make_tensor_value_info("output1", proto_type, proto_shape),
    ]

    base = np.zeros((1, rows, 38), dtype=np.float32)
    base[0, 0, :4] = (240, 80, 280, 120)
    base[0, 0, 5] = 32
    base[0, 0, 6] = 1.0  # single active mask coefficient, channel zero

    score_slot = np.zeros_like(base)
    score_slot[0, 0, 4] = 1.0  # on/off follows mean of first raw head
    coeff_slot = np.zeros_like(base)
    coeff_slot[0, 0, 6] = 1.0  # every one of the nine heads influences coefficient

    arrays = {
        "base": base,
        "score_slot": score_slot,
        "coeff_slot": coeff_slot,
        "gain_score": np.asarray(0.9, dtype=np.float32),
        "gain_coeff": np.asarray(0.001, dtype=np.float32),
    }
    initializers = [numpy_helper.from_array(v, name=k) for k, v in arrays.items()]
    nodes = []
    for i, name in enumerate(names):
        nodes.append(helper.make_node("ReduceMean", [name], [f"mean_{i}"],
                                      keepdims=0, name=f"consume_head_{i}"))
    total = "mean_0"
    for i in range(1, 9):
        nxt = f"sum_{i}"
        nodes.append(helper.make_node("Add", [total, f"mean_{i}"], [nxt]))
        total = nxt
    nodes.extend([
        helper.make_node("Mul", ["mean_0", "gain_score"], ["scalar_score"]),
        helper.make_node("Mul", ["scalar_score", "score_slot"], ["delta_score"]),
        helper.make_node("Mul", [total, "gain_coeff"], ["scalar_coeff"]),
        helper.make_node("Mul", ["scalar_coeff", "coeff_slot"], ["delta_coeff"]),
        helper.make_node("Add", ["base", "delta_score"], ["with_score"]),
        helper.make_node("Add", ["with_score", "delta_coeff"], ["output0"]),
        helper.make_node("Identity", ["rknn_mask_prototypes"], ["output1"]),
    ])

    model = helper.make_model(
        helper.make_graph(nodes, f"p10b_{variant}", ins, outs,
                          initializer=initializers),
        opset_imports=[helper.make_operatorsetid("", 19)],
        ir_version=9,
    )
    onnx.checker.check_model(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(path))
    assert 0 < path.stat().st_size < 8 * 1024 * 1024
    assert not any(x.endswith((".jpg", ".pt", ".rknn")) for x in
                   [path.name])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    for variant in (
        "valid", "wrong_name", "wrong_shape", "wrong_proto_dtype",
        "wrong_proto_shape", "wrong_output",
    ):
        build(root / (variant + ".onnx"), variant)
    print("P10B: six synthetic ONNX contracts prepared in ephemeral CI scratch.")
    print("No original model, image, training data, RKNN runtime or motor access.")


if __name__ == "__main__":
    main()
