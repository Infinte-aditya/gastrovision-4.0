"""Runs only when the trained model bundle is present in backend/model/ (skipped otherwise)."""
import os
import numpy as np
import pytest

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "model")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(MODEL_DIR, "gastrovision_cnn.onnx")),
                                reason="trained model not installed")


def test_real_model_loads_and_predicts():
    from model.predictor import Predictor
    p = Predictor(MODEL_DIR)
    assert len(p.classes) == 9 and p.other_idx is not None and p.has_cam
    frames = [np.random.randint(0, 255, (576, 720, 3), np.uint8) for _ in range(2)]
    P = p.predict_arrays_bgr(frames)
    assert P.shape == (2, 9) and np.allclose(P.sum(1), 1, atol=1e-4)
    out = p.explain_bgr(frames[0])
    assert out["cam"].ndim == 2 and out["cam"].shape == tuple(p.cfg["cam_size"])
