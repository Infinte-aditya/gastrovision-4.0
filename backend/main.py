"""
backend/main.py - analysis pipeline

video -> frame extraction (1 fps) -> quality filter -> CNN prediction (calibrated) ->
temporal video-level verdict -> CAM heatmaps (background thread)

v4.0 UI update: the pipeline now publishes its stage (get_progress) and honours cancel requests
(request_cancel) so the desktop UI can show a real progress bar.
"""
import os
import time
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

# ---------------------------------------------------------------- progress / cancel (read by the UI) ----
# stage -> overall percent at the START of that stage; the UI eases the bar between stages.
_progress = {}
_cancelled = set()


class Cancelled(RuntimeError):
    """Raised between pipeline stages when the user pressed Cancel."""


def _set_progress(name: str, stage: str, pct: int, **extra) -> None:
    _progress[name] = {"stage": stage, "pct": pct, "t": time.time(), **extra}


def get_progress(name: str) -> dict:
    return _progress.get(name, {"stage": "idle", "pct": 0})


def request_cancel(name: str) -> None:
    _cancelled.add(name)


def _check_cancel(name: str) -> None:
    if name in _cancelled:
        raise Cancelled("Analysis cancelled.")


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
    video_name = os.path.splitext(os.path.basename(video_full_path))[0]
    _cancelled.discard(video_name)
    _set_progress(video_name, "extract", 3)
    try:
        if _ensure_ffmpeg() is None:
            raise RuntimeError("ffmpeg was not found. Install ffmpeg or set GASTROVISION_FFMPEG.")
        eng = get_engine()
        pred, heat = eng["pred"], eng["heat"]

        frames = frame_extractor().extract_frames(video_full_path, "fixed_fps", 5, TARGET_FPS, MAX_FRAMES)
        _check_cancel(video_name)
        _set_progress(video_name, "filter", 30, n_extracted=len(frames))
        names, _, cleaned_dir = frame_selector().select_frames(frames, video_name)
        if not names:
            raise RuntimeError("No readable frames could be extracted from this video.")
        _check_cancel(video_name)

        _set_progress(video_name, "predict", 40, n_frames=len(names))
        pred.predict(cleaned_dir, video_name, frame_names=names)
        _check_cancel(video_name)

        _set_progress(video_name, "verdict", 90, n_frames=len(names))
        summary = eng["video"].summarize(video_name, conf_threshold=pred.conf_threshold,
                                         class_thresholds=CLASS_THRESHOLDS, **verdict_params())
        eng["frames"].compute_stats(video_name, pred.conf_threshold)          # writes frame_ranked.json (kept for the report tools)
        picks = eng["video"].select_heatmap_frames(summary, video_name, TOP_HEATMAPS)
        heatmap_dir = os.path.join(paths.outputs_dir(), video_name, "heatmaps")

        def run_heatmaps():
            heat.generate_batch(cleaned_dir, picks, heatmap_dir, top_n=TOP_HEATMAPS)
        Thread(target=run_heatmaps, daemon=True).start()
        _set_progress(video_name, "done", 100, n_frames=len(names))
        return summary
    except Exception:
        _set_progress(video_name, "error", 0)
        raise


def prediction(video_full_path):
    """Backwards-compatible: (label, confidence)."""
    try:
        s = analyze(video_full_path)
        return s["label"], s["confidence"]
    except RuntimeError as e:
        return f"Error: {e}", 0
