"""
video_processing/frame_selector.py
==================================
Quality filter for extracted frames.

Changes vs. the old version
---------------------------
* Frames are NOT kept in RAM (the old code held every full-resolution frame at once).
* Blur is judged on a fixed-size grey copy and RELATIVE to the video's own median sharpness, so the
  same setting works for 480p and 1080p recordings (the old absolute threshold of 130 was resolution
  dependent and could discard every frame of a smooth video, which then crashed torch.stack([])).
* A minimum number of frames is always kept (sharpest first).
* Near-duplicates are NOT removed any more: the video-level decision needs consecutive frames
  ("this finding stays in view for >= 3 frames"); removing duplicates would shorten those runs.
"""
import json
import os
import paths
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import List

import cv2
import numpy as np


class frame_selector:
    ANALYSIS_WIDTH = 480

    def _sharpness(self, path: str):
        g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if g is None:
            return None
        h, w = g.shape
        if w > self.ANALYSIS_WIDTH:
            g = cv2.resize(g, (self.ANALYSIS_WIDTH, max(1, int(h * self.ANALYSIS_WIDTH / w))), interpolation=cv2.INTER_AREA)
        return float(cv2.Laplacian(g, cv2.CV_64F).var())

    def select_frames(self, frames: List[str], video_name: str, blur_rel: float = 0.5, min_keep: int = 12):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        video_dir = os.path.join(paths.outputs_dir(), video_name)
        frames_dir = os.path.join(video_dir, "frames")
        cleaned_dir = os.path.join(video_dir, "cleaned_frames")
        shutil.rmtree(cleaned_dir, ignore_errors=True)
        os.makedirs(cleaned_dir)

        frames = sorted(frames)
        with ThreadPoolExecutor(max_workers=4) as ex:
            scores = list(ex.map(lambda f: self._sharpness(os.path.join(frames_dir, f)), frames))
        ok = [(f, s) for f, s in zip(frames, scores) if s is not None]
        if not ok:
            return [], [], cleaned_dir
        var = np.array([s for _, s in ok])
        cutoff = max(blur_rel * float(np.median(var)), 1.0)       # absolute floor drops black / flat frames
        keep = [f for f, s in ok if s >= cutoff]
        fallback = False
        if len(keep) < min(min_keep, len(ok)):                    # never starve the model
            fallback = True
            keep = sorted(f for f, _ in sorted(ok, key=lambda t: -t[1])[:min(min_keep, len(ok))])
        for f in keep:
            shutil.copy2(os.path.join(frames_dir, f), os.path.join(cleaned_dir, f))
        with open(os.path.join(video_dir, "cleaned_metadata.json"), "w", encoding="utf-8") as fh:
            json.dump({"selected_frames": keep, "stats": {
                "total_input": len(frames), "blurry_removed": len(ok) - len(keep) if not fallback else 0,
                "final_selected": len(keep), "median_sharpness": float(np.median(var)),
                "cutoff": cutoff, "fallback_used": fallback}}, fh, indent=2)
        return keep, keep, cleaned_dir          # (names, names, dir): same 3-tuple shape the old main.py expected
