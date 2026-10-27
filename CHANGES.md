# Changes in this patch

| File | Problem found | Fix |
|---|---|---|
| backend/model/predictor.py | OpenCV BGR frames fed to an RGB-trained model (red<->blue swapped); hard-coded class list / mean / std | Single preprocessing module, BGR->RGB once, config from `preprocess.json`, calibrated probabilities, GPU->CPU fallback, lazy frame loading |
| backend/visualization/heatmap.py | Attention rollout is class-agnostic; used mean/std 0.5 (model used ImageNet stats); downloaded weights from HuggingFace at run time; needed torch+transformers | Class-activation maps read from the ONNX graph; no torch, no internet |
| backend/scoring/video_scoring.py | Verdict = class with highest *average confidence* (one confident stray frame wins) | Temporal smoothing + minimum consecutive run + clinical tier priority; returns full findings list; "no-finding" when nothing qualifies |
| backend/video_processing/frame_selector.py | Kept every full-res frame in RAM; absolute blur threshold; could discard everything and crash | Disk-based, relative blur rule, minimum frames guaranteed |
| backend/main.py | All frames extracted ("all" = every frame as PNG); hard-coded `C:\Users\aadit\...` ffmpeg path; models loaded at import | 3 fps extraction, ffmpeg lookup (env / bundled / PATH), lazy engine |
| backend/server.py | `/heatmaps` gave no completion signal (UI polled forever if < 5 heatmaps) | `done` flag + `/health` endpoint |
| frontend | Polling never stopped for < 5 heatmaps | Stops on `done` |
| requirements.txt | torch/transformers/datasets pinned (GBs) | ONNX-only runtime deps |

## Update: real model integrated (CNN, 9 classes)
* Trained EfficientNetV2-S bundle installed in `backend/model/` (the `.onnx` is git-ignored; ship it via Releases).
* Test accuracy 94.4% / macro-F1 0.933 on a leakage-controlled test set; calibrated (T=0.655), threshold 0.85.
* `no-finding` no longer reports a 100% "confidence": it returns `confidence: 0`, `uncertain_fraction`, and a note; the UI says it is not a clearance.
* UI text: ViT/diagnostic wording replaced with EfficientNetV2 / research-prototype notice; README rewritten.
* New `tests/test_real_model.py` (runs only when the bundle is present).

## Update: video robustness
* `preprocess.remove_green_overlay` now removes green **and teal** scope-position boxes (HSV hue 40-100, solid-box check so scattered green fluid is left alone). Shared by training and app.
* Old v3 model on a HyperKvasir polyp video: all 24 frames `other` -> `polyps` verdict after this change alone.
* `ml/gastrovision_train.ipynb` is now **v4**: frames from HyperKvasir labelled videos (whole videos kept in one split), extra HyperKvasir image folders mapped to classes, overlay/timestamp/octagon augmentation, video-level evaluation using the app's own verdict logic, and an external check on the clips you supplied (excluded from training).

## Fix: v4 grouping bug (found from a failed full run)
* Loose 64-bit hash twins chained 8,878 of 24,719 frames into one group, leaving val=370 and test=60 frames (7 of 9 classes) and crashing `classification_report`.
* Grouping is now size-capped (<= 0.6 % of the data), strongest links first, hash twins must be confirmed by the CNN embedding; exact duplicates are dropped.
* A fail-fast gate stops the notebook before training if val/test lack >= 25 frames of any class; reports are robust to missing classes.

## Update: video verdict re-tuned on corrected video evaluation
* The earlier in-notebook video table ("100 % detected") was wrong: `eval_videos` used row positions from a filtered frame on the unfiltered one. Fixed in `ml/` notebook; the standalone `gastrovision_reeval.ipynb` re-scored all 94 held-out val/test videos (1 frame/s, whole video) from the shipped bundle - no retraining.
* Honest video numbers with the old rule (0.8 / min_run 2 / smooth 3): finding detected 65 % (val) / 80 % (test); `polyps` videos 6/12 and 12/17.
* Tuned on **val**, confirmed on **test**: base bar 0.8, **polyps bar 0.6** -> polyps detected 0.58 / 0.82, extra false findings per video 0.44 / 0.30 (a global 0.6 bar gave 0.52 / 0.50). Below 0.6 nothing more is found.
* `video_scoring.summarize*` takes `class_thresholds`; each finding has `strength` (`strong` / `possible`); UI shows "POSSIBLE FINDING ... PLEASE REVIEW" and an "ALSO SEEN" line.
* `main.py` now samples at **1 fps** (what was evaluated; override with `GASTROVISION_FPS`) and derives `min_run`/`smooth` from the fps (`verdict_params`).
* `frame_extractor`: metadata probe read `streams[0]`, which is the audio track in many clinical `.avi` files -> now uses the video stream.
* Known limit: ~6 of 32 polyp videos never exceed 0.6 for `polyps` (some likely mislabelled at video level); clip `16e7e461` is one of them (peak 0.56) and still returns no-finding.

## v4.0.0 packaging
* `launcher.py`: one-click start (engine + window); picks a free port; shows an error if the model fails to load.
* `backend/paths.py`: all writes go to `%LOCALAPPDATA%\GastroVision` when installed; old results pruned after 7 days.
* In-app **Send feedback** button (copies anonymous diagnostics to the clipboard, opens the form); version shown in title/header/footer.
* `packaging/` (PyInstaller spec, Windows build script, Inno Setup installer) and `docs/index.html`; see `RELEASING.md`.
* Verified on Linux: frozen build starts, loads the model and returns real predictions; Windows installer must be built on Windows.
