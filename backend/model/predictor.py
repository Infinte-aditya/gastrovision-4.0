"""
model/predictor.py
==================
ONNX inference for the GastroVision CNN.

Fixes vs. the old ViT predictor
-------------------------------
* COLOUR ORDER: the old in-memory path fed OpenCV **BGR** frames to a model trained on
  **RGB** (red <-> blue swapped on every frame).  All conversion now happens once, in
  `preprocess.preprocess_batch_bgr`.
* One preprocessing implementation shared with training (`preprocess.py`); parameters are read
  from `preprocess.json` that ships next to the model (no hard-coded mean/std/classes).
* Calibrated probabilities (temperature from training) and an explicit `other` class.
* Frames are read lazily from disk in small batches (no 1000 x 1080p frames held in RAM).
* GPU (CUDA/DirectML) is used when it works, with automatic CPU fallback.
* The ONNX graph also returns class-activation maps, so heatmaps need no PyTorch.
"""
from __future__ import annotations

import json
import os
import paths
import time
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np
import onnxruntime as ort

try:                                    # works both as `model.preprocess` (backend run) and standalone
    from . import preprocess as gp
except ImportError:                     # pragma: no cover
    import preprocess as gp

BATCH_SIZE = 16


def default_model_dir() -> str:
    return os.environ.get("GASTROVISION_MODEL_DIR") or os.path.dirname(os.path.abspath(__file__))


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class Predictor:
    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or default_model_dir()
        self.cfg = gp.load_cfg(self.model_dir)
        with open(os.path.join(self.model_dir, "class_names.json"), "r", encoding="utf-8") as f:
            self.classes: List[str] = json.load(f)
        self.temperature = float(self.cfg.get("temperature", 1.0))
        self.conf_threshold = float(self.cfg.get("conf_threshold", 0.7))
        other = self.cfg.get("other_class")
        self.other_idx = self.classes.index(other) if other in self.classes else None
        model_path = os.path.join(self.model_dir, self.cfg.get("model_file", "gastrovision_cnn.onnx"))
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        self.session, self.provider = self._make_session(model_path)
        self.input_name = self.session.get_inputs()[0].name
        out_names = [o.name for o in self.session.get_outputs()]
        self.has_cam = "cam" in out_names

    # ------------------------------------------------------------------ session
    def _make_session(self, path: str):
        avail = ort.get_available_providers()
        forced = os.environ.get("GASTROVISION_PROVIDER")           # e.g. "CPUExecutionProvider"
        order = [forced] if forced else [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in avail]
        if "CPUExecutionProvider" not in order:
            order.append("CPUExecutionProvider")
        for prov in order:
            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            if prov == "DmlExecutionProvider":                     # DirectML requirements
                so.enable_mem_pattern = False
                so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            try:
                sess = ort.InferenceSession(path, so, providers=[prov])
                size = int(self.cfg["img_size"])                   # warm-up proves the provider really works
                sess.run(None, {sess.get_inputs()[0].name: np.zeros((1, 3, size, size), np.float32)})
                return sess, prov
            except Exception as e:                                 # fall through to the next provider
                print(f"[Predictor] provider {prov} unusable ({type(e).__name__}); trying next")
        raise RuntimeError("No usable ONNX Runtime execution provider")

    # ------------------------------------------------------------------ core
    def _run(self, batch: np.ndarray):
        outs = self.session.run(None, {self.input_name: batch})
        return outs[0], (outs[1] if self.has_cam and len(outs) > 1 else None)

    def probabilities(self, logits: np.ndarray) -> np.ndarray:
        return _softmax(logits / self.temperature)

    def predict_arrays_bgr(self, frames_bgr: Sequence[np.ndarray]) -> np.ndarray:
        """BGR frames (as returned by OpenCV) -> calibrated probabilities [N, K]."""
        out = []
        for i in range(0, len(frames_bgr), BATCH_SIZE):
            batch = gp.preprocess_batch_bgr(frames_bgr[i:i + BATCH_SIZE], self.cfg)
            out.append(self.probabilities(self._run(batch)[0]))
        return np.concatenate(out) if out else np.zeros((0, len(self.classes)), np.float32)

    def predict_files(self, frame_dir: str, names: Sequence[str]) -> np.ndarray:
        """Read frames lazily from `frame_dir` in small batches."""
        out = []
        for i in range(0, len(names), BATCH_SIZE):
            frames = []
            for n in names[i:i + BATCH_SIZE]:
                img = cv2.imread(os.path.join(frame_dir, n), cv2.IMREAD_COLOR)   # BGR
                frames.append(img if img is not None else np.zeros((16, 16, 3), np.uint8))
            out.append(self.probabilities(self._run(gp.preprocess_batch_bgr(frames, self.cfg))[0]))
        return np.concatenate(out) if out else np.zeros((0, len(self.classes)), np.float32)

    # ------------------------------------------------------------------ compat API
    def predict(self, frame_input, video_name: str, frame_names: Optional[List[str]] = None):
        """Same call shape as the old predictor.  `frame_input` = directory of frames or a list of BGR arrays.
        Writes outputs/<video>/frame_scores.jsonl and returns [[frame, label, confidence], ...]."""
        t0 = time.time()
        if isinstance(frame_input, str):
            names = list(frame_names) if frame_names is not None else sorted(
                f for f in os.listdir(frame_input) if f.lower().endswith((".png", ".jpg", ".jpeg")))
            probs = self.predict_files(frame_input, names)
        else:
            names = list(frame_names) if frame_names is not None else [f"frame_{i:06d}.png" for i in range(len(frame_input))]
            probs = self.predict_arrays_bgr(frame_input)

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        video_dir = os.path.join(paths.outputs_dir(), video_name)
        os.makedirs(video_dir, exist_ok=True)
        result = []
        with open(os.path.join(video_dir, "frame_scores.jsonl"), "w", encoding="utf-8") as fh:
            for name, p in zip(names, probs):
                k = int(p.argmax())
                label, conf = self.classes[k], float(p[k])
                result.append([name, label, conf])
                fh.write(json.dumps({
                    "frame": name, "label": label, "confidence": conf,
                    "is_other": self.other_idx is not None and k == self.other_idx,
                    "probabilities": {c: float(v) for c, v in zip(self.classes, p)},
                }) + "\n")
        print(f"[Predictor] {len(names)} frames in {time.time() - t0:.1f}s on {self.provider}")
        return result

    # ------------------------------------------------------------------ explainability
    def explain_bgr(self, frame_bgr: np.ndarray, class_name: Optional[str] = None) -> Dict:
        """Class-activation map for one frame. Returns the raw CAM [h, w] for `class_name`
        (default: predicted class) plus the black-border crop box in original pixel coordinates."""
        if not self.has_cam:
            raise RuntimeError("This model file has no CAM output")
        rgb = gp.bgr_to_rgb(frame_bgr)
        logits, cam = self._run(gp.preprocess_rgb(rgb, self.cfg)[None])
        p = self.probabilities(logits)[0]
        k = self.classes.index(class_name) if class_name else int(p.argmax())
        return {"cam": cam[0, k].astype(np.float32), "class": self.classes[k], "confidence": float(p[k]),
                "box": gp.black_border_box(rgb), "rgb": rgb}


predictor = Predictor        # backwards-compatible name used by older code
