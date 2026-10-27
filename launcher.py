"""GastroVision desktop launcher: starts the local analysis engine, waits until the model is loaded, opens the window.

Used both from source (python launcher.py) and as the PyInstaller entry point.
Nothing leaves the computer: the engine listens on 127.0.0.1 only and videos are never uploaded anywhere.
"""
import os
import sys
import socket
import threading
import time
import urllib.request

ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
for sub in ("", "backend", "frontend"):
    sys.path.insert(0, os.path.join(ROOT, sub))


def _frozen_env():
    """Inside the installed app, files live next to the exe, not next to the .py files."""
    if getattr(sys, "frozen", False):
        os.environ.setdefault("GASTROVISION_MODEL_DIR", os.path.join(ROOT, "backend", "model"))
        ff = os.path.join(ROOT, "ffmpeg", "ffmpeg.exe")
        if os.path.exists(ff):
            os.environ.setdefault("GASTROVISION_FFMPEG", ff)


def _free_port(preferred: int = 8000) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("No free local port")


def _start_engine(port: int):
    import uvicorn
    import server  # backend/server.py
    cfg = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning", log_config=None)
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    return srv


def _wait_ready(port: int, timeout: float = 90.0) -> str:
    """Return '' when /health says ok, otherwise a human-readable reason."""
    t0, last = time.time(), "engine did not start"
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:
                body = r.read().decode()
            if '"status":"ok"' in body.replace(" ", ""):
                return ""
            last = body[:300]
        except Exception as e:
            last = str(e)
        time.sleep(0.4)
    return last


def main() -> int:
    _frozen_env()
    import paths
    paths.prune_outputs(7)
    port = _free_port()
    os.environ["GASTROVISION_PORT"] = str(port)
    srv = _start_engine(port)

    from PyQt6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    problem = _wait_ready(port)
    if problem:
        QMessageBox.critical(None, "GastroVision", f"The analysis engine could not start.\n\n{problem}")
        return 1
    import gastrovision_single as ui
    win = ui.MainWindow()
    win.show()
    code = app.exec()
    srv.should_exit = True
    return code


if __name__ == "__main__":
    sys.exit(main())
