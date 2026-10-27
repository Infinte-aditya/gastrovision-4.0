# GastroVision

Desktop research prototype that analyses gastrointestinal endoscopy videos with a CNN
(EfficientNetV2-S, ONNX Runtime), reports which findings it sees consistently over time,
and highlights the image regions that drove each decision (class activation maps).

> **Research prototype. Not a medical device. Not validated for clinical use.**
> Results must never be used for diagnosis or treatment decisions.

## What it detects

8 Kvasir classes: `dyed-lifted-polyps`, `dyed-resection-margins`, `esophagitis`, `normal-cecum`,
`normal-pylorus`, `normal-z-line`, `polyps`, `ulcerative-colitis` - plus an `other` class
(bowel-prep, retroflexed views, etc.) so that unrelated frames are not forced into a finding.

## How an analysis works

1. ffmpeg extracts frames at 1 fps; blurry frames are dropped (relative threshold, a minimum number is always kept).
2. Each frame is cleaned (black border crop, removal of the green/teal scope-position inset), converted BGR to RGB once, and classified at 384x384.
   Probabilities are temperature-calibrated.
3. The video verdict uses temporal smoothing: a finding counts only if the model is confident (>= 0.8; >= 0.6 for polyps, shown as "possible") on
   several consecutive frames. Pathology outranks procedure frames, which outrank normal landmarks.
   If nothing is seen consistently the result is **no-finding** - which is *not* a clearance.
4. Class-specific heatmaps are generated for the most confident frames.

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
* Findings visible for under ~1 s can be missed (1 frame/s sampling).
* The heatmap-vs-lesion-mask check (Kvasir-SEG) has not been run; heatmaps are class activation maps, not segmentation.

## Run from source (Windows / Linux / macOS)

```bash
pip install -r requirements.txt        # use `onnxruntime` instead of `onnxruntime-directml` on non-Windows
# put the trained bundle files into backend/model/ :
#   gastrovision_cnn.onnx  class_names.json  preprocess.json
python launcher.py                      # starts the engine + window in one step
```

ffmpeg must be installed (or set `GASTROVISION_FFMPEG`, or place it in `backend/ffmpeg/`).
Run the tests with `pip install -r requirements-dev.txt && pytest`.

## Training

`ml/gastrovision_train.ipynb` (Kaggle, GPU): group-aware split, held-out test set, `other` class,
MixUp/CutMix, EMA, calibration, ONNX export with built-in CAM output. `ml/gastrovision_preprocess.py`
is the single preprocessing implementation shared by training and the app.

## Layout

```
backend/   FastAPI server + pipeline (video_processing, model, scoring, visualization)
frontend/  PyQt6 desktop UI
ml/        training notebook + shared preprocessing
tests/     pytest suite (synthetic fixture model; plus real-model test when the bundle is present)
Database/  optional Postgres scaffolding (not used by the prototype)
```

## Releasing a packaged Windows app

See `RELEASING.md` (PyInstaller + Inno Setup + GitHub Releases + `website/index.html`).
