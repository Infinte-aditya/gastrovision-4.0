# PyInstaller spec - build with:  pyinstaller packaging/gastrovision.spec --noconfirm
# One-FOLDER build (starts faster and triggers fewer antivirus false alarms than --onefile).
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas, binaries, hidden = [], [], [
    "server", "main", "paths", "app_info", "gastrovision_single",
    "video_processing.frame_extractor", "video_processing.frame_selector",
    "scoring.video_scoring", "scoring.frame_scoring", "visualization.heatmap",
    "model.predictor", "model.preprocess",
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "multipart",
]
for pkg in ("onnxruntime",):                       # native DLLs (incl. DirectML on Windows)
    d, b, h = collect_all(pkg); datas += d; binaries += b; hidden += h

# model weights + config (the .onnx is NOT in git: copy it into backend/model/ before building)
datas += [(os.path.join(ROOT, "backend", "model", f), "backend/model")
          for f in ("gastrovision_cnn.onnx", "class_names.json", "preprocess.json", "metrics.json")]
# ffmpeg + ffprobe (see RELEASING.md) -> <app>/ffmpeg/
for exe in ("ffmpeg.exe", "ffprobe.exe"):
    p = os.path.join(ROOT, "packaging", "ffmpeg", exe)
    if os.path.exists(p):
        datas.append((p, "ffmpeg"))

a = Analysis([os.path.join(ROOT, "launcher.py")],
             pathex=[ROOT, os.path.join(ROOT, "backend"), os.path.join(ROOT, "frontend")],
             binaries=binaries, datas=datas, hiddenimports=hidden, excludes=["tkinter", "pytest", "scipy", "matplotlib", "pandas", "IPython"])
SYS = os.path.join(os.environ["SystemRoot"], "System32")
RT = ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "vcruntime140.dll", "vcruntime140_1.dll")
a.binaries = [b for b in a.binaries if os.path.basename(b[0]).lower() not in RT]
a.binaries += [(n, os.path.join(SYS, n), "BINARY") for n in RT if os.path.exists(os.path.join(SYS, n))]
pyz = PYZ(a.pure)
icon = os.path.join(ROOT, "packaging", "gastrovision.ico")
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GastroVision", console=False,
          icon=icon if os.path.exists(icon) else None)
coll = COLLECT(exe, a.binaries, a.datas, name="GastroVision")
