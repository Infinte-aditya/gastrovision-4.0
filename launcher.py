"""GastroVision desktop launcher: shows a splash, starts the local analysis engine in the background,
waits until the model is loaded, shows the one-time research notice, then opens the main window.

Used both from source (python launcher.py) and as the PyInstaller entry point.
Nothing leaves the computer: the engine listens on 127.0.0.1 only and videos are never uploaded anywhere.
"""

import subprocess, sys
if sys.platform == "win32":
    # Never let a child process (ffmpeg / ffprobe) open a console window.
    _orig_popen_init = subprocess.Popen.__init__
    def _popen_init(self, *a, **kw):
        kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
        si = kw.get("startupinfo") or subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kw["startupinfo"] = si
        _orig_popen_init(self, *a, **kw)
    subprocess.Popen.__init__ = _popen_init

import os
import socket
import threading
import time
import urllib.request
import ctypes
import traceback

if sys.platform == "win32" and getattr(sys, "frozen", False):
    base = sys._MEIPASS
    capi = os.path.join(base, "onnxruntime", "capi")
    os.add_dll_directory(base)
    os.add_dll_directory(capi)
    try:
        for n in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
            p = os.path.join(base, n)
            if os.path.exists(p):
                ctypes.WinDLL(p)
        for n in ("DirectML.dll", "onnxruntime_providers_shared.dll", "onnxruntime.dll"):
            ctypes.WinDLL(os.path.join(capi, n))
    except Exception:
        with open(os.path.join(os.environ.get("TEMP", "."), "gastrovision_dll.log"), "w") as f:
            traceback.print_exc(file=f)

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


def _log_error(text: str) -> str:
    """Save a startup failure next to the user's data and return the file path."""
    try:
        import paths
        p = os.path.join(paths.data_dir(), "gastrovision_error.log")
    except Exception:
        p = os.path.join(os.environ.get("TEMP", "."), "gastrovision_error.log")
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    return p


def _wait_ready(port: int, timeout: float = 120.0):
    """Return (health_dict, '') when /health says ok, otherwise ({}, human-readable reason)."""
    import json
    t0, last = time.time(), "engine did not start"
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=60) as r:
                body = json.loads(r.read().decode())
            if body.get("status") == "ok":
                return body, ""
            last = str(body.get("detail", body))[:400]
        except Exception as e:
            last = str(e)
        time.sleep(0.4)
    return {}, last


def _make_boot_thread(port: int):
    """QThread that starts the engine and waits for the model, so the splash stays animated."""
    from PyQt6.QtCore import QThread, pyqtSignal

    class Boot(QThread):
        status = pyqtSignal(float, str)
        ready = pyqtSignal(dict)
        failed = pyqtSignal(str)
        srv = None

        def run(self):
            try:
                self.status.emit(8, "Starting analysis engine…")
                import uvicorn
                self.status.emit(18, "Loading components…")
                import server  # backend/server.py (imports onnxruntime, OpenCV, ...)
                cfg = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning", log_config=None)
                self.srv = uvicorn.Server(cfg)
                threading.Thread(target=self.srv.run, daemon=True).start()
                self.status.emit(40, "Loading AI model…")
                health, problem = _wait_ready(port)
                if problem:
                    self.failed.emit(problem)
                else:
                    self.status.emit(96, "Almost ready…")
                    self.ready.emit(health)
            except Exception:
                self.failed.emit(traceback.format_exc())

    return Boot()


def main() -> int:
    _frozen_env()
    import paths
    paths.prune_outputs(7)
    port = _free_port()
    os.environ["GASTROVISION_PORT"] = str(port)

    from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)          # splash / dialogs closing must not quit the app
    import gastrovision_single as ui
    ui.apply_app_style(app)

    splash = ui.SplashScreen()
    splash.show()
    app.processEvents()

    state = {"srv": None, "win": None, "code": 0}
    boot = _make_boot_thread(port)

    def open_main(health):
        if not ui.notice_accepted():
            dlg = ui.NoticeDialog()
            if dlg.exec() != QDialog.DialogCode.Accepted:
                app.quit()
                return
            ui.remember_notice()
        win = ui.MainWindow(health)
        state["win"] = win
        app.setQuitOnLastWindowClosed(True)
        win.show()

    def on_ready(health):
        state["srv"] = boot.srv
        splash.finish(lambda: open_main(health))

    def on_failed(problem):
        log = _log_error(problem)
        splash.hide()
        QMessageBox.critical(None, "GastroVision",
                             "The analysis engine could not start.\n\n"
                             f"{problem.strip().splitlines()[-1][:300]}\n\nDetails were saved to:\n{log}")
        state["code"] = 1
        app.quit()

    boot.status.connect(splash.set_progress)
    boot.ready.connect(on_ready)
    boot.failed.connect(on_failed)
    boot.start()

    code = app.exec()
    if state["srv"] is not None:
        state["srv"].should_exit = True
    return state["code"] or code


if __name__ == "__main__":
    sys.exit(main())
