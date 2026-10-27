"""
visualization/heatmap.py
========================
Class-activation-map (CAM) heatmaps + bounding boxes, computed from the `cam` output of the
ONNX model.  No PyTorch / transformers / internet download needed at run time.

Why this replaces attention rollout
-----------------------------------
* Attention rollout is *class-agnostic*: the map was identical whichever disease was asked for.
  CAM is *class-specific*: "where is the evidence for **polyps**?".
* For a global-average-pool -> linear head, CAM is mathematically identical to Grad-CAM, so this
  is the standard, well-understood explanation for CNNs.
* The old module normalised inputs with mean/std 0.5 while the model was trained/served with
  ImageNet statistics - the heatmap network saw different inputs than the classifier.  Now the
  heatmap and the prediction come from the *same* ONNX graph and the *same* preprocessing.

IMPORTANT: a CAM shows what the model used as evidence. It is an aid for the clinician's review,
not a segmentation of the lesion.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image


def _cam_to_unit(cam: np.ndarray, size_hw) -> np.ndarray:
    """raw CAM [h,w] -> relu -> upsample -> [0,1]."""
    c = np.maximum(cam.astype(np.float32), 0.0)
    c = cv2.resize(c, (size_hw[1], size_hw[0]), interpolation=cv2.INTER_CUBIC)
    c = np.maximum(c, 0.0)
    mx = float(c.max())
    return c / mx if mx > 1e-8 else np.zeros_like(c)


def boxes_from_map(unit: np.ndarray, thr: float = 0.5, max_boxes: int = 3, min_area_frac: float = 0.01):
    """Bounding boxes (x0, y0, x1, y1, score) around the strongest connected regions."""
    H, W = unit.shape
    binary = (unit >= thr).astype(np.uint8)
    cnts, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < min_area_frac * H * W:
            continue
        out.append((x, y, x + w, y + h, float(unit[y:y + h, x:x + w].mean())))
    out.sort(key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]) * b[4])
    return out[:max_boxes]


def render_overlay(rgb: np.ndarray, unit: np.ndarray, alpha: float = 0.55, floor: float = 0.25,
                   boxes: Optional[list] = None) -> np.ndarray:
    """Blend a JET heatmap where evidence is strong; weak areas stay untouched."""
    heat = np.clip((unit - floor) / (1 - floor), 0, 1)
    jet = cv2.cvtColor(cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    w = (alpha * heat)[..., None]
    out = rgb.astype(np.float32) * (1 - w) + jet.astype(np.float32) * w
    out = np.clip(out, 0, 255).astype(np.uint8)
    for (x0, y0, x1, y1, _s) in boxes or []:
        cv2.rectangle(out, (x0, y0), (x1 - 1, y1 - 1), (255, 255, 255), 2)
    return out


class HeatmapGenerator:
    def __init__(self, predictor, alpha: float = 0.55, box_threshold: float = 0.5):
        self.pred = predictor
        self.alpha = alpha
        self.box_threshold = box_threshold

    def generate(self, frame_bgr: np.ndarray, target_class: Optional[str] = None) -> Dict:
        e = self.pred.explain_bgr(frame_bgr, target_class)
        r0, r1, c0, c1 = e["box"]
        visual = np.ascontiguousarray(e["rgb"][r0:r1, c0:c1])            # picture area only (no black frame)
        unit = _cam_to_unit(e["cam"], visual.shape[:2])
        boxes = boxes_from_map(unit, self.box_threshold)
        overlay = render_overlay(visual, unit, self.alpha, boxes=boxes)
        H, W = visual.shape[:2]
        return {
            "overlay_image": Image.fromarray(overlay), "unit_map": unit,
            "metadata": {
                "method": "class_activation_map", "target_class": e["class"], "confidence": round(e["confidence"], 4),
                "boxes_normalised": [[round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4), round(b[4], 3)]
                                     for b in boxes],
                "peak_in_box": bool(unit.max() > 0),
            },
        }

    def generate_batch(self, frame_dir, frame_results: List[Dict], output_dir, alpha: Optional[float] = None,
                       top_n: Optional[int] = None) -> List[Dict]:
        """frame_results: [{frame, label, confidence, rank}, ...]. Writes <frame>_heatmap.png and a `_done.json` marker
        (the UI uses it to know when to stop polling, even if fewer than 5 heatmaps exist)."""
        frame_dir, output_dir = Path(frame_dir), Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        done = output_dir / "_done.json"
        if done.exists():
            done.unlink()
        if alpha is not None:
            self.alpha = alpha
        results = []
        try:
            for entry in (frame_results[:top_n] if top_n else frame_results):
                p = frame_dir / entry["frame"]
                img = cv2.imread(str(p), cv2.IMREAD_COLOR)
                if img is None:
                    continue
                try:
                    r = self.generate(img, entry.get("label"))
                except Exception as ex:            # one bad frame must not kill the batch
                    print(f"[Heatmap] {entry['frame']}: {ex}")
                    continue
                save = output_dir / f"{p.stem}_heatmap.png"
                r["overlay_image"].save(save)
                results.append({"frame": entry["frame"], "rank": entry.get("rank"), "save_path": str(save), "metadata": r["metadata"]})
        finally:
            done.write_text(json.dumps({"count": len(results)}), encoding="utf-8")
        return results
