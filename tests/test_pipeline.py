import json, os, shutil, subprocess, time
import cv2, numpy as np, pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def textured(color_rgb, size=(240, 320), seed=0, border=True):
    """Noise-textured solid colour so the blur filter sees a sharp image. Returns BGR like cv2."""
    rng = np.random.default_rng(seed)
    base = np.array(color_rgb, np.float32)[None, None, :] + rng.normal(0, 18, (*size, 3))
    img = np.clip(base, 0, 255).astype(np.uint8)
    if border:
        full = np.zeros((size[0] + 40, size[1] + 60, 3), np.uint8); full[20:-20, 30:-30] = img; img = full
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


# ------------------------------------------------------------------ preprocessing
def test_bgr_to_rgb_is_applied_exactly_once():
    from model import preprocess as gp
    red_bgr = np.zeros((64, 64, 3), np.uint8); red_bgr[..., 2] = 200          # OpenCV red
    x = gp.preprocess_batch_bgr([red_bgr], {"img_size": 32})
    assert x[0, 0].mean() > 0 > x[0, 2].mean(), "channel 0 must be RED after conversion"


def test_old_bug_would_flip_prediction():
    """Regression test for the root-cause bug: feeding BGR as RGB makes a red frame look blue."""
    from model.predictor import Predictor
    from model import preprocess as gp
    p = Predictor()
    red_bgr = textured((200, 40, 40), border=False)
    good = p.predict_arrays_bgr([red_bgr])[0]
    buggy_in = gp.preprocess_rgb(red_bgr, p.cfg)[None]                        # old behaviour: BGR array treated as RGB
    bad = p.probabilities(p._run(buggy_in)[0])[0]
    assert p.classes[int(good.argmax())] == "polyps"
    assert p.classes[int(bad.argmax())] == "normal-cecum", "old pipeline misreads red as blue"


def test_black_border_and_green_overlay_removed():
    from model import preprocess as gp
    img = np.zeros((300, 400, 3), np.uint8); img[40:260, 50:350] = (170, 70, 70); img[200:255, 55:130] = (0, 230, 0)
    c = gp.clean_frame(img)
    assert c.shape[0] < 300 and c.shape[1] < 400
    assert not ((c[..., 1] > 200) & (c[..., 0] < 50)).any()


# ------------------------------------------------------------------ predictor
def test_predictor_probabilities_and_classes():
    from model.predictor import Predictor
    p = Predictor()
    gray = textured((128, 128, 128), border=False)
    pr = p.predict_arrays_bgr([textured((200, 40, 40)), textured((40, 40, 200)), gray])
    assert pr.shape == (3, 9) and np.allclose(pr.sum(1), 1, atol=1e-5)
    assert [p.classes[int(i)] for i in pr.argmax(1)] == ["polyps", "normal-cecum", "other"]
    assert p.has_cam


# ------------------------------------------------------------------ video scoring
def _scores(seq, classes):
    P = np.full((len(seq), len(classes)), 0.01, np.float32)
    for i, c in enumerate(seq):
        P[i, classes.index(c)] = 0.9
    return [f"f{i:04d}.png" for i in range(len(seq))], P


def test_video_rule_not_fooled_by_single_confident_frame():
    from scoring.video_scoring import video_scoring
    cl = ["polyps", "normal-cecum", "other"]
    names, P = _scores(["normal-cecum"] * 30 + ["other"] * 10, cl)
    P[5] = [0.99, 0.005, 0.005]                       # one 99 %-sure stray frame of "polyps"
    s = video_scoring().summarize_probs(names, cl, P)
    assert s["label"] == "normal-cecum", s            # old rule (best average confidence) would answer "polyps"


def test_video_pathology_outranks_landmark_and_no_finding():
    from scoring.video_scoring import video_scoring
    cl = ["polyps", "normal-cecum", "other"]
    names, P = _scores(["normal-cecum"] * 40 + ["polyps"] * 6 + ["other"] * 10, cl)
    s = video_scoring().summarize_probs(names, cl, P)
    assert s["label"] == "polyps" and {f["class"] for f in s["findings"]} == {"polyps", "normal-cecum"}
    names, P = _scores(["other"] * 50, cl)
    assert video_scoring().summarize_probs(names, cl, P)["label"] == "no-finding"


# ------------------------------------------------------------------ heatmaps
def test_cam_points_at_the_red_region_and_box_covers_it():
    from model.predictor import Predictor
    from visualization.heatmap import HeatmapGenerator
    p = Predictor(); g = HeatmapGenerator(p)
    img = textured((128, 128, 128), border=False)
    img[:, :img.shape[1] // 2] = textured((220, 30, 30), border=False)[:, :img.shape[1] // 2]   # red LEFT half
    r = g.generate(img, "polyps")
    unit = r["unit_map"]; H, W = unit.shape
    assert unit[:, : W // 2].mean() > 3 * unit[:, W // 2:].mean(), "heat must sit on the left (red) half"
    x0, y0, x1, y1 = r["metadata"]["boxes_normalised"][0][:4]
    assert x0 < 0.1 and 0.4 < x1 < 0.65


# ------------------------------------------------------------------ end to end with a real video file
@pytest.fixture(scope="module")
def video_path(tmp_path_factory):
    d = tmp_path_factory.mktemp("vid"); fr = d / "f"; fr.mkdir()
    plan = [(128, 128, 128)] * 20 + [(220, 40, 40)] * 15 + [(128, 128, 128)] * 20 + [(40, 40, 220)] * 25   # 10 fps, 8 s
    for i, c in enumerate(plan):
        cv2.imwrite(str(fr / f"{i:04d}.png"), textured(c, seed=i))
    out = d / "demo_case.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "10", "-i", str(fr / "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)
    return str(out)


def test_end_to_end_video(video_path):
    import main
    t0 = time.time()
    s = main.analyze(video_path)
    classes = {f["class"] for f in s["findings"]}
    assert s["label"] == "polyps", s
    assert classes == {"polyps", "normal-cecum"}, classes
    # heat-maps are produced in a background thread; wait for the done-marker
    hdir = os.path.join(os.path.dirname(main.__file__), "outputs", "demo_case", "heatmaps")
    for _ in range(100):
        if os.path.exists(os.path.join(hdir, "_done.json")): break
        time.sleep(0.1)
    assert os.path.exists(os.path.join(hdir, "_done.json"))
    pngs = [f for f in os.listdir(hdir) if f.endswith(".png")]
    assert 1 <= len(pngs) <= 5
    print(f"\nend-to-end: {s['n_frames']} frames, label={s['label']}, findings={sorted(classes)}, "
          f"heatmaps={len(pngs)}, {time.time()-t0:.1f}s")
    shutil.rmtree(os.path.join(os.path.dirname(main.__file__), "outputs", "demo_case"), ignore_errors=True)


def test_api_roundtrip(video_path):
    from fastapi.testclient import TestClient
    import server
    c = TestClient(server.app)
    assert c.get("/health").json()["status"] == "ok"
    with open(video_path, "rb") as f:
        r = c.post("/predict", files={"file": ("demo_case2.mp4", f, "video/mp4")})
    assert r.status_code == 200, r.text
    j = r.json(); assert j["label"] == "polyps" and "findings" in j
    for _ in range(100):
        hm = c.get("/heatmaps/demo_case2").json()
        if hm["done"]: break
        time.sleep(0.1)
    assert hm["done"] and len(hm["heatmap_paths"]) >= 1
    shutil.rmtree(os.path.join(os.path.dirname(server.__file__), "outputs", "demo_case2"), ignore_errors=True)


def test_teal_and_green_overlay_removed_but_clean_frames_untouched():
    import numpy as np
    from model import preprocess as gp
    base = np.full((400, 500, 3), (150, 70, 60), np.uint8)
    for colour in ((20, 160, 140), (10, 230, 20)):                      # HyperKvasir teal, Kvasir green
        img = base.copy(); img[250:380, 10:140] = colour
        out = gp.remove_green_overlay(img)
        assert not ((out[250:380, 10:140] == colour).all(axis=2)).any()
    assert np.array_equal(gp.remove_green_overlay(base), base)           # nothing to remove -> untouched
    specks = base.copy()
    for y, x in [(220, 20), (300, 90), (350, 150), (260, 60), (330, 30)]:
        specks[y:y + 3, x:x + 3] = (60, 200, 60)
    assert np.array_equal(gp.remove_green_overlay(specks), specks)       # scattered green is NOT a box


def test_polyps_use_a_lower_bar_than_other_classes():
    """A polyp seen at ~0.65 confidence is reported (as 'possible'); the same score for a landmark is not."""
    from scoring.video_scoring import video_scoring
    cl = ["polyps", "normal-cecum", "other"]
    P = np.full((12, 3), 0.05, np.float32); P[:, 0] = 0.65; P[:, 2] = 0.30
    names = [f"f{i:04d}.png" for i in range(12)]
    s = video_scoring().summarize_probs(names, cl, P, conf_threshold=0.8, min_run=2, smooth=3,
                                        class_thresholds={"polyps": 0.6})
    assert s["label"] == "polyps" and s["findings"][0]["strength"] == "possible"
    P2 = P.copy(); P2[:, [0, 1]] = P2[:, [1, 0]]                       # same scores, but for normal-cecum
    s2 = video_scoring().summarize_probs(names, cl, P2, conf_threshold=0.8, min_run=2, smooth=3,
                                         class_thresholds={"polyps": 0.6})
    assert s2["label"] == "no-finding"
