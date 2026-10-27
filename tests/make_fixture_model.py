"""Builds a TINY stand-in ONNX model with the same interface as the real one (outputs `logits` and `cam`).
red-dominant frame  -> polyps      blue-dominant -> normal-cecum      grey -> other
Used only by the tests; it lets us verify the whole pipeline without the trained network."""
import json, os, sys
import numpy as np, onnx
from onnx import TensorProto as TP, helper as h, numpy_helper as nh

CLASSES = ["dyed-lifted-polyps", "dyed-resection-margins", "esophagitis", "normal-cecum", "normal-pylorus",
           "normal-z-line", "polyps", "ulcerative-colitis", "other"]
S = 224

def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    K = len(CLASSES)
    W = np.zeros((K, 3, 1, 1), np.float32); b = np.zeros(K, np.float32)
    W[CLASSES.index("polyps"), :, 0, 0] = [6, 0, -6]
    W[CLASSES.index("normal-cecum"), :, 0, 0] = [-6, 0, 6]
    b[CLASSES.index("other")] = 3.0
    nodes = [
        h.make_node("Conv", ["pixel_values", "W", "b"], ["z"], kernel_shape=[1, 1]),
        h.make_node("AveragePool", ["z"], ["cam"], kernel_shape=[32, 32], strides=[32, 32]),
        h.make_node("ReduceMean", ["cam"], ["logits"], axes=[2, 3], keepdims=0),
    ]
    g = h.make_graph(nodes, "tiny",
        [h.make_tensor_value_info("pixel_values", TP.FLOAT, ["batch", 3, S, S])],
        [h.make_tensor_value_info("logits", TP.FLOAT, ["batch", K]),
         h.make_tensor_value_info("cam", TP.FLOAT, ["batch", K, S // 32, S // 32])],
        [nh.from_array(W, "W"), nh.from_array(b, "b")])
    m = h.make_model(g, opset_imports=[h.make_opsetid("", 13)]); m.ir_version = 8
    onnx.checker.check_model(m); onnx.save(m, os.path.join(out_dir, "gastrovision_cnn.onnx"))
    json.dump(CLASSES, open(os.path.join(out_dir, "class_names.json"), "w"))
    json.dump({"img_size": S, "mean": [0.5] * 3, "std": [0.5] * 3, "cache_max_side": 512, "temperature": 1.0,
               "conf_threshold": 0.7, "other_class": "other", "model_file": "gastrovision_cnn.onnx"},
              open(os.path.join(out_dir, "preprocess.json"), "w"))

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "tests/fixture_model")
