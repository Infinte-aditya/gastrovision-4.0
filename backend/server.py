import os
import paths
import shutil

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile

from main import analyze, get_engine

UPLOAD_DIR = paths.uploads_dir()

app = FastAPI(title="GastroVision backend")


@app.get("/")
def root():
    return {"message": "GastroVision backend running"}


@app.get("/health")
def health():
    """Used by the desktop shell to know when the model is loaded."""
    try:
        e = get_engine()["pred"]
        return {"status": "ok", "provider": e.provider, "classes": e.classes, "conf_threshold": e.conf_threshold}
    except Exception as ex:
        return {"status": "error", "detail": str(ex)}


@app.post("/predict")
async def predict_video(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, os.path.basename(file.filename))
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        s = analyze(file_path)
        return {"file": file.filename, "label": s["label"], "confidence": s["confidence"],
                "findings": s["findings"], "n_frames": s["n_frames"], "n_rejected": s["n_rejected"],
                "uncertain_fraction": s.get("uncertain_fraction", 0.0), "note": s.get("note", "")}
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/heatmaps/{video_name}")
def get_heatmaps(video_name: str):
    d = os.path.join(paths.outputs_dir(), os.path.basename(video_name), "heatmaps")
    if not os.path.exists(d):
        return {"heatmap_paths": [], "done": False}
    pngs = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".png"))
    return {"heatmap_paths": pngs, "done": os.path.exists(os.path.join(d, "_done.json"))}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
