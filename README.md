# GastroVision

Free Windows program and research prototype that analyses gastrointestinal endoscopy videos with a CNN
(EfficientNetV2-S, ONNX Runtime). It reports which findings it sees consistently over time and highlights
the image regions that drove each decision (class activation maps). Everything runs on your own computer.

**[Download for Windows](https://github.com/Infinte-aditya/gastrovision-4.0/releases/latest)** ·
**[Website](https://infinte-aditya.github.io/gastrovision-4.0/)** ·
**[Send feedback](https://github.com/Infinte-aditya/gastrovision-4.0/issues/new/choose)**

> **Research prototype. Not a medical device. Not validated for clinical use.**
> Results must never be used for diagnosis or treatment decisions. "No finding" does not mean a video is normal.

## What it detects

Eight HyperKvasir classes: `dyed-lifted-polyps`, `dyed-resection-margins`, `esophagitis`, `normal-cecum`,
`normal-pylorus`, `normal-z-line`, `polyps`, `ulcerative-colitis`, plus an `other` class
(bowel-prep, retroflexed views, etc.) so that unrelated frames are not forced into a finding.
`other` is never reported as a finding, and it is not a general "I don't know": anything outside the eight
can still be mislabelled as one of them.

## How an analysis works

1. ffmpeg extracts frames at 1 fps; blurry frames are dropped (relative threshold, a minimum number is always kept).
2. Each frame is cleaned (black border crop, removal of the green/teal scope-position inset), converted BGR to RGB once, and classified at 384x384.
   Probabilities are temperature-calibrated.
3. The video verdict uses temporal smoothing (median over about 3 seconds): a finding counts only if the model is confident
   (>= 0.8; >= 0.6 for polyps, shown as "possible") on at least two consecutive samples. Pathology outranks procedure frames,
   which outrank normal landmarks. If nothing is seen consistently the result is **no-finding**, which is *not* a clearance.
4. Class-specific heatmaps (up to five) are generated for the most confident frames.

## Measured performance (v4, held-out test set, leakage-controlled split)

| Metric | Value |
|---|---|
| Frame accuracy (stills + video frames) | 84.4% |
| Macro-F1 | 0.860 |
| Accuracy on blurred / low-res / JPEG frames | 83.4% |
| Still photographs / video frames | ~95% / ~66% |
| Whole videos, labelled finding detected (46 test / 48 val videos, 1 frame/s) | ~85% / ~65% |
| `polyps` videos detected | 14/17 test, 7/12 val |

Weakest class: `polyps` in videos. Full numbers: `backend/model/metrics.json`, `CHANGES.md`.

### Known limitations

* Video performance is clearly below still-image performance; some "polyps" videos are labelled at video level only and may show no polyp.
* The video rules were tuned on the same HyperKvasir videos used for the video figures, so those figures are best-case.
* Not tested on footage from other hospitals, scopes or recording setups; expect lower numbers there.
* Findings visible for under ~1 s can be missed (1 frame/s sampling).
* The heatmap-vs-lesion-mask check (Kvasir-SEG) has not been run; heatmaps are class activation maps, not segmentation.

## Privacy

The analysis engine listens only on `127.0.0.1`; videos are never uploaded. Extracted frames and heatmaps are written to
`%LOCALAPPDATA%\GastroVision\outputs` and deleted after seven days. The *Send feedback* button only copies the app version,
Windows version and the model's test accuracy to the clipboard; it contains no video, file names or patient data.
Please do not post anything that identifies a patient in issues.

## Install (Windows 10/11, 64-bit)

Download `GastroVision-Setup-4.0.0.exe` from the [latest release](https://github.com/Infinte-aditya/gastrovision-4.0/releases/latest).
The installer is not code-signed, so SmartScreen may warn you: choose *More info*, then *Run anyway*.
Check the download with `certutil -hashfile GastroVision-Setup-4.0.0.exe SHA256` and compare it with the hash on the release page.

## Run from source (Windows / Linux / macOS)

```bash
pip install -r requirements.txt        # use `onnxruntime` instead of `onnxruntime-directml` on non-Windows
# put the trained bundle files into backend/model/ :
#   gastrovision_cnn.onnx  class_names.json  preprocess.json
python launcher.py                      # starts the engine + window in one step
```

The model file is not stored in this repository; it is included in the Windows installer.
ffmpeg must be installed (or set `GASTROVISION_FFMPEG`, or place it in `backend/ffmpeg/`).
Run the tests with `pip install -r requirements-dev.txt && pytest`.

## Training

`ml/gastrovision_train.ipynb` (Kaggle, GPU): group-aware split, held-out test set, `other` class,
MixUp/CutMix, EMA, calibration, ONNX export with built-in CAM output. `ml/gastrovision_preprocess.py`
is the single preprocessing implementation shared by training and the app.

## Layout

```
backend/    FastAPI server + pipeline (video_processing, model, scoring, visualization)
frontend/   PyQt6 desktop UI
ml/         training notebook + shared preprocessing
tests/      pytest suite (synthetic fixture model; plus real-model test when the bundle is present)
packaging/  PyInstaller spec, Inno Setup script, Windows build script
docs/       project website (GitHub Pages)
Database/   optional Postgres scaffolding (not used by the prototype)
```

## Packaging a release (maintainers)

See `RELEASING.md` (PyInstaller + Inno Setup + GitHub Releases + `docs/index.html`).

## Licence and credits

GastroVision is released under the [GNU GPL v3.0](LICENSE). Copyright (c) 2026 Aditya Verma, Aaditya Raj and Gyanam Shah.
Video decoding uses [FFmpeg](https://ffmpeg.org), which keeps its own licence.
Trained on HyperKvasir: Borgli, H., Thambawita, V., Smedsrud, P.H. et al. *HyperKvasir, a comprehensive multi-class image
and video dataset for gastrointestinal endoscopy.* Scientific Data 7, 283 (2020).
