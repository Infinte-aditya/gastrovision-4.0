"""
gastrovision_preprocess.py
==========================
SINGLE SOURCE OF TRUTH for image preprocessing.

The exact same file is used by the training notebook and by the desktop app.
Most "great in the notebook, useless in the app" failures are caused by the two
sides preprocessing images slightly differently (colour order, normalisation,
resize method, borders).  Keeping one implementation removes that failure mode.

Colour convention: every public function in this module takes/returns **RGB**.
OpenCV (cv2.imread / VideoCapture) gives **BGR** - convert with `bgr_to_rgb`
before calling anything here.

Pipeline (identical for train-cache creation and for inference):
    rgb -> crop_black_borders -> remove_green_overlay -> limit_side
        -> resize to (img_size, img_size) [PIL bilinear] -> normalise -> CHW float32
"""
from __future__ import annotations

import json
import os
from typing import Dict, Tuple

import cv2
import numpy as np
from PIL import Image

DEFAULT_CFG: Dict = {
    "img_size": 384,
    "mean": [0.5, 0.5, 0.5],
    "std": [0.5, 0.5, 0.5],
    "cache_max_side": 512,
}


def bgr_to_rgb(frame_bgr: np.ndarray) -> np.ndarray:
    """OpenCV frames are BGR. The model was trained on RGB."""
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def black_border_box(rgb: np.ndarray, thr: int = 18, min_keep: float = 0.5):
    """Return (r0, r1, c0, c1) of the picture area inside any black frame."""
    h, w = rgb.shape[:2]
    if rgb.ndim != 3:
        return 0, h, 0, w
    bright = rgb.max(axis=2) > thr
    rows = np.where(bright.mean(axis=1) > 0.05)[0]
    cols = np.where(bright.mean(axis=0) > 0.05)[0]
    if len(rows) == 0 or len(cols) == 0:
        return 0, h, 0, w
    r0, r1, c0, c1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
    if (r1 - r0) * (c1 - c0) < min_keep * h * w:
        return 0, h, 0, w
    return r0, r1, c0, c1


def crop_black_borders(rgb: np.ndarray, thr: int = 18, min_keep: float = 0.5) -> np.ndarray:
    """Trim the black frame that most endoscopy recorders add around the picture.
    Falls back to the untouched image if the crop would remove > (1-min_keep) of it."""
    r0, r1, c0, c1 = black_border_box(rgb, thr, min_keep)
    return np.ascontiguousarray(rgb[r0:r1, c0:c1])


def remove_green_overlay(rgb: np.ndarray, region: Tuple[float, float] = (0.45, 0.50),
                         min_frac: float = 0.01) -> np.ndarray:
    """Endoscopy recorders draw a solid green / teal 'scope position' inset in the bottom-left corner
    (bright green in Kvasir stills, teal in HyperKvasir videos).  It is not anatomy, and a network can learn it
    as a shortcut.  Detect it (hue 40-100 = green..teal, strongly saturated) and inpaint it away.

    Safety: the detected pixels must form a *solid box* (>= 50 % of their bounding box), so scattered
    greenish fluid is never inpainted.  No-op when absent, so ordinary frames are returned untouched."""
    h, w = rgb.shape[:2]
    r0, c1 = int(h * (1 - region[1])), int(w * region[0])
    patch = np.ascontiguousarray(rgb[r0:, :c1])
    if patch.size == 0:
        return rgb
    hsv = cv2.cvtColor(patch, cv2.COLOR_RGB2HSV)
    green = (hsv[..., 0] >= 40) & (hsv[..., 0] <= 100) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 90)
    if green.mean() < min_frac:
        return rgb
    ys, xs = np.where(green)
    box = green[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if box.mean() < 0.5:
        return rgb
    pad_y, pad_x = max(3, int(0.02 * h)), max(3, int(0.02 * w))
    y0, y1 = max(0, ys.min() - pad_y), min(patch.shape[0], ys.max() + pad_y + 1)
    x0, x1 = max(0, xs.min() - pad_x), min(patch.shape[1], xs.max() + pad_x + 1)
    mask = np.zeros(patch.shape[:2], np.uint8)
    mask[y0:y1, x0:x1] = 255
    out = rgb.copy()
    out[r0:, :c1] = cv2.inpaint(patch, mask, 5, cv2.INPAINT_TELEA)
    return out


def clean_frame(rgb: np.ndarray) -> np.ndarray:
    """crop black borders + remove green overlay. RGB uint8 in, RGB uint8 out."""
    return remove_green_overlay(crop_black_borders(rgb))


def limit_side(img: Image.Image, max_side: int) -> Image.Image:
    w, h = img.size
    m = max(w, h)
    if m <= max_side:
        return img
    s = max_side / m
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.BILINEAR)


def pil_to_tensor_array(img: Image.Image, img_size: int, mean, std) -> np.ndarray:
    """PIL RGB -> float32 CHW, resized (squash) with PIL bilinear, normalised."""
    img = img.convert("RGB").resize((img_size, img_size), Image.BILINEAR)
    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.asarray(mean, np.float32)) / np.asarray(std, np.float32)
    return np.ascontiguousarray(x.transpose(2, 0, 1))


def preprocess_rgb(rgb: np.ndarray, cfg: Dict = None) -> np.ndarray:
    """Full inference-time preprocessing of ONE RGB frame -> float32 [3,S,S]."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    img = Image.fromarray(clean_frame(rgb))
    img = limit_side(img, int(cfg["cache_max_side"]))
    return pil_to_tensor_array(img, int(cfg["img_size"]), cfg["mean"], cfg["std"])


def preprocess_batch_bgr(frames_bgr, cfg: Dict = None) -> np.ndarray:
    """OpenCV (BGR) frames -> float32 [N,3,S,S].  The BGR->RGB swap lives HERE, once."""
    return np.stack([preprocess_rgb(bgr_to_rgb(f), cfg) for f in frames_bgr]).astype(np.float32)


def load_cfg(model_dir: str) -> Dict:
    p = os.path.join(model_dir, "preprocess.json")
    with open(p, "r", encoding="utf-8") as f:
        return {**DEFAULT_CFG, **json.load(f)}
