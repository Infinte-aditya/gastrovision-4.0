"""Release metadata shown in the UI and in the feedback diagnostics. Edit this file for every release."""
import json
import os
import platform
import sys

VERSION = "4.0.0"
# Links used by the "Send feedback" button and the website.
FEEDBACK_URL = "https://github.com/Infinte-aditya/gastrovision-3.0/issues/new/choose"
WEBSITE_URL = "https://infinte-aditya.github.io/gastrovision-3.0/"


def _model_info() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(os.path.dirname(here), "backend", "model", "metrics.json"),
              os.path.join(getattr(sys, "_MEIPASS", ""), "backend", "model", "metrics.json")):
        try:
            m = json.load(open(p, encoding="utf-8"))
            return {"test_acc": round(float(m.get("test_accuracy", 0)), 3)}
        except Exception:
            continue
    return {}


def diagnostics() -> str:
    """Plain text the user pastes into the feedback form. Contains NO patient data and no file names."""
    mi = _model_info()
    return (f"GastroVision v{VERSION}\nOS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"Python: {platform.python_version()}\nModel test accuracy: {mi.get('test_acc', 'n/a')}")
