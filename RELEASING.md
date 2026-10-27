# Releasing GastroVision (Windows desktop app)

Every release = edit version -> build on Windows -> test on a clean PC -> publish -> announce.

## One-time setup
1. GitHub: create a repo, push this folder (the `.onnx` is git-ignored on purpose).
2. Download FFmpeg "release essentials" for Windows (https://www.gyan.dev/ffmpeg/builds/). Copy `ffmpeg.exe` and `ffprobe.exe` into `packaging/ffmpeg/`.
3. Install Python 3.11 or 3.12 (64-bit) and Inno Setup 6 (https://jrsoftware.org/isinfo.php) on the Windows build PC.
4. Make a feedback form (Google Form or GitHub Issues template). Suggested questions: What video type? What did GastroVision say? What was expected? Rating 1-5? Pasted diagnostics (optional).
5. Put your real links into `frontend/app_info.py` (`FEEDBACK_URL`, `WEBSITE_URL`) and replace `YOUR-USER` / `YOUR NAME` in `docs/index.html` and `packaging/installer.iss`.

## Each release
1. Bump the version in `frontend/app_info.py`, `packaging/installer.iss` (`AppVer`) and `docs/index.html`; add notes to `CHANGES.md`.
2. Copy the model bundle files (`gastrovision_cnn.onnx`, `class_names.json`, `preprocess.json`, `metrics.json`) into `backend/model/`.
3. `pytest` (pip install -r requirements-dev.txt first) - all green.
4. Run `packaging\build_windows.bat` -> `dist\GastroVision\GastroVision.exe`. Double-click it and analyse a video.
5. Open `packaging\installer.iss` in Inno Setup -> Compile -> `release\GastroVision-Setup-4.0.0.exe`.
6. Test the INSTALLER on a different, clean Windows PC (no Python, no ffmpeg): install, run, analyse, uninstall.
7. Compute the hash: `certutil -hashfile release\GastroVision-Setup-4.0.0.exe SHA256` -> paste it into `docs/index.html`.
8. GitHub -> Releases -> "Draft a new release" -> tag `v4.0.0` -> attach the installer -> paste release notes -> Publish.
9. Publish the site: repo Settings -> Pages -> deploy from branch, folder `/docs` (or copy `index.html` to Netlify / Cloudflare Pages).
10. Open the live site in a private window and click every link.

## Known caveats
* The installer is **unsigned**: Windows SmartScreen shows "Windows protected your PC" -> More info -> Run anyway. Code signing (a paid certificate, or a free programme such as SignPath for open-source) removes it.
* Some antivirus tools flag freshly built PyInstaller apps. Upload to https://www.virustotal.com to check, and tell testers what to expect.
* FFmpeg is GPL/LGPL software: keep the link on the website and ship its license text with the installer (`packaging/ffmpeg/LICENSE`).
* Check the HyperKvasir licence terms and cite Borgli et al., 2020 (done in the installer text and website).
* Analysis results are stored in `%LOCALAPPDATA%\GastroVision\outputs` and deleted after 7 days automatically.
