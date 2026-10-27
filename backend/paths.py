"""Single place that decides where the app WRITES (analysis outputs, temporary uploads).

* From source:            <repo>/backend/outputs, <repo>/backend/uploads   (unchanged behaviour)
* Installed (PyInstaller): %LOCALAPPDATA%/GastroVision/...                (Program Files is read-only)
* Override anywhere:      GASTROVISION_DATA_DIR
"""
import os
import sys
import time
import shutil

_BACKEND = os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    env = os.environ.get("GASTROVISION_DATA_DIR")
    if env:
        base = env
    elif getattr(sys, "frozen", False):
        root = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
        base = os.path.join(root, "GastroVision")
    else:
        base = _BACKEND
    os.makedirs(base, exist_ok=True)
    return base


def outputs_dir() -> str:
    d = os.path.join(data_dir(), "outputs")
    os.makedirs(d, exist_ok=True)
    return d


def uploads_dir() -> str:
    d = os.path.join(data_dir(), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def prune_outputs(max_age_days: float = 7.0) -> int:
    """Delete analysis folders (frames, heatmaps) older than N days so the disk does not fill up."""
    cutoff, n = time.time() - max_age_days * 86400, 0
    base = outputs_dir()
    for name in os.listdir(base):
        p = os.path.join(base, name)
        try:
            if os.path.isdir(p) and os.path.getmtime(p) < cutoff:
                shutil.rmtree(p, ignore_errors=True); n += 1
        except OSError:
            pass
    return n
