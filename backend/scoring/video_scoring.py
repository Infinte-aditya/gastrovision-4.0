"""
scoring/video_scoring.py
========================
Turns per-frame probabilities into ONE verdict for the whole video.

Why the old rule was unreliable
-------------------------------
The old code returned the class with the highest *average confidence*.  A single frame the
model was 99 % sure about (on a class seen once) beat a class seen in hundreds of frames.

New rule (all thresholds are parameters):
  1. smooth the per-class probability curves over time (median filter, 5 frames);
  2. a frame "votes" for a class only if it is the arg-max, is not the `other` class and is
     at least `conf_threshold` confident (calibrated);
  3. a class counts as DETECTED only if it has a run of >= `min_run` consecutive voting frames
     (a real lesion stays in view for a moment; single-frame noise does not);
  4. the headline verdict is taken from the most clinically important tier that has a detection:
         pathology  (polyps, esophagitis, ulcerative-colitis)
         > procedure (dyed-lifted-polyps, dyed-resection-margins)
         > landmark (normal-cecum, normal-pylorus, normal-z-line)
     and within a tier the class with most voting frames wins;
  5. nothing detected -> "no-finding".

The full list of findings (with timing) is always returned so the UI can show all of them.
"""
import json
import math
import os
import paths
from typing import Dict, List, Optional, Tuple

import numpy as np

PATHOLOGY = ("polyps", "esophagitis", "ulcerative-colitis")
PROCEDURE = ("dyed-lifted-polyps", "dyed-resection-margins")
LANDMARK = ("normal-cecum", "normal-pylorus", "normal-z-line")
TIER_ORDER = ["pathology", "procedure", "landmark"]
NO_FINDING = "no-finding"


def tier_of(cls: str) -> str:
    if cls in PATHOLOGY:
        return "pathology"
    if cls in PROCEDURE:
        return "procedure"
    if cls in LANDMARK:
        return "landmark"
    return "other"


def _median_smooth(P: np.ndarray, window: int = 5) -> np.ndarray:
    if window <= 1 or len(P) < 3:
        return P
    window = min(window, len(P) if len(P) % 2 == 1 else len(P) - 1)
    pad = window // 2
    Pp = np.pad(P, ((pad, pad), (0, 0)), mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(Pp, window, axis=0)   # [n, K, window]
    return np.median(win, axis=-1)


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


class video_scoring:
    # ---------------------------------------------------------------- loading
    @staticmethod
    def _video_dir(video_name: str) -> str:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(paths.outputs_dir(), video_name)

    def load_frame_scores(self, video_name: str) -> Tuple[List[str], List[str], np.ndarray]:
        names, classes, rows = [], None, []
        with open(os.path.join(self._video_dir(video_name), "frame_scores.jsonl"), "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if classes is None:
                    classes = list(d["probabilities"].keys())
                names.append(d["frame"])
                rows.append([d["probabilities"][c] for c in classes])
        return names, classes or [], np.asarray(rows, np.float32).reshape(len(names), len(classes or []))

    # ---------------------------------------------------------------- core
    def summarize_probs(self, names: List[str], classes: List[str], P: np.ndarray, conf_threshold: float = 0.7,
                        min_run: int = 3, smooth: int = 5, other_class: Optional[str] = "other",
                        class_thresholds: Optional[Dict[str, float]] = None) -> Dict:
        n = len(names)
        if n == 0:
            return {"label": NO_FINDING, "confidence": 0.0, "findings": [], "n_frames": 0, "n_rejected": 0,
                    "reason": "no usable frames"}
        Ps = _median_smooth(P, smooth)
        pred, conf = Ps.argmax(1), Ps.max(1)
        other_idx = classes.index(other_class) if other_class in classes else -1
        # per-class confidence bar: a missed polyp is worse than a false alarm, so `polyps` can use a lower one
        thr_vec = np.array([float((class_thresholds or {}).get(c, conf_threshold)) for c in classes], np.float32)
        voting = (conf >= thr_vec[pred]) & (pred != other_idx)
        findings = []
        for k, c in enumerate(classes):
            if k == other_idx:
                continue
            m = voting & (pred == k)
            run = _longest_run(m)
            if run < min_run:
                continue
            idx = np.where(m)[0]
            best = int(idx[np.argmax(P[idx, k])])
            findings.append({
                "class": c, "tier": tier_of(c), "frames": int(m.sum()), "longest_run": int(run),
                "mean_confidence": float(Ps[idx, k].mean()), "peak_confidence": float(P[best, k]),
                "first_frame": names[int(idx[0])], "best_frame": names[best], "best_index": best,
                "fraction_of_video": float(m.sum() / n),
                # "possible" = found only because of the lowered per-class bar; the UI should word it cautiously
                "strength": "strong" if float(Ps[idx, k].mean()) >= conf_threshold else "possible",
            })
        tier_rank = {t: i for i, t in enumerate(TIER_ORDER + ["other"])}
        findings.sort(key=lambda f: (tier_rank[f["tier"]], -f["frames"], -f["mean_confidence"]))
        n_rejected = int((~voting).sum())
        if findings:
            top = findings[0]
            label, confidence = top["class"], top["mean_confidence"]
        else:
            # Nothing consistent was found.  `confidence` is 0 on purpose: it used to be the fraction of
            # rejected frames, which the UI showed as a misleading "100 % confidence".
            label, confidence = NO_FINDING, 0.0
        out = {"label": label, "confidence": float(confidence), "findings": findings, "n_frames": n,
               "n_rejected": n_rejected, "uncertain_fraction": float(n_rejected / n),
               "conf_threshold": conf_threshold, "min_run": min_run, "smooth": smooth,
               "class_thresholds": dict(class_thresholds or {})}
        if label == NO_FINDING:
            out["note"] = ("No target finding was seen consistently. This does NOT mean the video is normal: "
                           "the model only knows 8 findings plus 'other', and frames that look different from "
                           "its training images are rejected.")
        return out

    def summarize(self, video_name: str, conf_threshold: float = 0.7, min_run: int = 3, smooth: int = 5,
                  other_class: Optional[str] = "other", class_thresholds: Optional[Dict[str, float]] = None) -> Dict:
        names, classes, P = self.load_frame_scores(video_name)
        out = self.summarize_probs(names, classes, P, conf_threshold, min_run, smooth, other_class, class_thresholds)
        with open(os.path.join(self._video_dir(video_name), "video_summary.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        return out

    # ---------------------------------------------------------------- helpers
    def select_heatmap_frames(self, summary: Dict, video_name: str, top_n: int = 5, min_gap: int = 6) -> List[Dict]:
        """Pick up to `top_n` well-spread, high-confidence frames, round-robin over the detected findings."""
        names, classes, P = self.load_frame_scores(video_name)
        picked, per_class = [], []
        for f in summary.get("findings", []):
            k = classes.index(f["class"])
            order = [int(i) for i in np.argsort(-P[:, k]) if P[i, k] >= summary.get("conf_threshold", 0.7)]
            chosen = []
            for i in order:
                if all(abs(i - j) >= min_gap for j in chosen):
                    chosen.append(i)
            per_class.append((f["class"], chosen))
        r = 0
        while len(picked) < top_n and any(r < len(c) for _, c in per_class):
            for cls, c in per_class:
                if r < len(c) and len(picked) < top_n:
                    i = c[r]
                    k = classes.index(cls)
                    picked.append({"frame": names[i], "label": cls, "confidence": float(P[i, k]), "rank": len(picked) + 1})
            r += 1
        return picked

    # ---------------------------------------------------------------- backwards-compatible API
    def average_confidence(self, video_name: str, conf_threshold: float = 0.7):
        s = self.summarize(video_name, conf_threshold)
        return s["label"], s["confidence"]
