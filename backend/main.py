"""
backend/main.py - analysis pipeline

video -> frame extraction (3 fps) -> quality filter -> CNN prediction (calibrated) ->
temporal video-level verdict -> CAM heatmaps (background thread)
"""
import os
import paths
import shutil
from threading import Lock, Thread

from model.predictor import Predictor
from scoring.frame_scoring import frame_scoring
from scoring.video_scoring import video_scoring
from video_processing.frame_extractor import frame_extractor
from video_processing.frame_selector import frame_selector
from visualization.heatmap import HeatmapGenerator

# The verdict rules below were tuned and validated on 94 held-out HyperKvasir videos scored at 1 frame/s
# (see CHANGES.md).  Deploying the same sampling rate keeps "what was measured" == "what runs".
TARGET_FPS = float(os.environ.get("GASTROVISION_FPS", "1"))
# polyps get a lower confidence bar than everything else: a missed polyp costs more than a false alarm.
# 0.6 is the plateau on val/test - going lower added false findings without finding more polyps.
CLASS_THRESHOLDS = {"polyps": 0.6}


def verdict_params(fps: float = TARGET_FPS) -> dict:
    """Time-equivalent verdict settings: a finding must persist ~1 s+ (2 samples at 1 fps), median window ~3 s."""
    smooth = max(3, int(round(3 * fps)) // 2 * 2 + 1)          # odd window
    return {"min_run": max(2, int(round(fps)) + 1), "smooth": smooth}
MAX_FRAMES = 6000
TOP_HEATMAPS = 5

_engine = None
_lock = Lock()


def get_engine():
    """Lazy singleton: the app starts instantly and a missing model gives a clear error, not an import crash."""
    global _engine
    with _lock:
        if _engine is None:
            pred = Predictor()
            _engine = {"pred": pred, "heat": HeatmapGenerator(pred), "frames": frame_scoring(), "video": video_scoring()}
        return _engine


def _ensure_ffmpeg():
    """ffmpeg lookup order: $GASTROVISION_FFMPEG -> bundled next to the app -> PATH -> common Windows folders."""
    env = os.environ.get("GASTROVISION_FFMPEG")
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [env] if env else []
    candidates += [os.path.join(here, "ffmpeg", "ffmpeg.exe"), os.path.join(os.path.dirname(here), "ffmpeg", "ffmpeg.exe")]
    for c in candidates:
        if c and os.path.exists(c):
            os.environ["PATH"] = os.path.dirname(c) + os.pathsep + os.environ.get("PATH", "")
            return c
    found = shutil.which("ffmpeg")
    if found:
        return found
    for c in (r"C:\ProgramData\chocolatey\bin\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), r"ffmpeg\bin\ffmpeg.exe")):
        if os.path.exists(c):
            os.environ["PATH"] = os.path.dirname(c) + os.pathsep + os.environ.get("PATH", "")
            return c
    return None


def analyze(video_full_path: str) -> dict:
    """Full analysis. Returns the video summary dict (label, confidence, findings, ...)."""
    if _ensure_ffmpeg() is None:
        raise RuntimeError("ffmpeg was not found. Install ffmpeg or set GASTROVISION_FFMPEG.")
    eng = get_engine()
    pred, heat = eng["pred"], eng["heat"]
    video_name = os.path.splitext(os.path.basename(video_full_path))[0]
    backend_dir = os.path.dirname(os.path.abspath(__file__))

    frames = frame_extractor().extract_frames(video_full_path, "fixed_fps", 5, TARGET_FPS, MAX_FRAMES)
    names, _, cleaned_dir = frame_selector().select_frames(frames, video_name)
    if not names:
        raise RuntimeError("No readable frames could be extracted from this video.")
    pred.predict(cleaned_dir, video_name, frame_names=names)

    summary = eng["video"].summarize(video_name, conf_threshold=pred.conf_threshold,
                                     class_thresholds=CLASS_THRESHOLDS, **verdict_params())
    eng["frames"].compute_stats(video_name, pred.conf_threshold)          # writes frame_ranked.json (kept for the report tools)
    picks = eng["video"].select_heatmap_frames(summary, video_name, TOP_HEATMAPS)
    heatmap_dir = os.path.join(paths.outputs_dir(), video_name, "heatmaps")

    def run_heatmaps():
        heat.generate_batch(cleaned_dir, picks, heatmap_dir, top_n=TOP_HEATMAPS)
    Thread(target=run_heatmaps, daemon=True).start()
    return summary


def prediction(video_full_path):
    """Backwards-compatible: (label, confidence)."""
    try:
        s = analyze(video_full_path)
        return s["label"], s["confidence"]
    except RuntimeError as e:
        return f"Error: {e}", 0
