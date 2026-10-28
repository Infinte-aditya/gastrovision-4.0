@echo off
REM Run from the repo root on WINDOWS:  packaging\build_windows.bat
setlocal
if not exist backend\model\gastrovision_cnn.onnx (echo Missing backend\model\gastrovision_cnn.onnx - copy the model bundle in first & exit /b 1)
if not exist packaging\ffmpeg\ffmpeg.exe (echo Missing packaging\ffmpeg\ffmpeg.exe and ffprobe.exe - see RELEASING.md & exit /b 1)
python -m venv .build-venv || exit /b 1
call .build-venv\Scripts\activate.bat
python -m pip install --upgrade pip --default-timeout=120
pip install --default-timeout=120 setuptools wheel || exit /b 1
pip install --default-timeout=120 -r packaging\requirements-build.txt || exit /b 1
pyinstaller packaging\gastrovision.spec --noconfirm || exit /b 1
echo.
echo Built: dist\GastroVision\GastroVision.exe   (test it by double-clicking!)
echo Next: open packaging\installer.iss in Inno Setup and press Compile.