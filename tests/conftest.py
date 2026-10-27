import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "backend"))
sys.path.insert(0, HERE)
FIXTURE = os.path.join(HERE, "fixture_model")
if not os.path.exists(os.path.join(FIXTURE, "gastrovision_cnn.onnx")):      # generated on demand, never committed
    import make_fixture_model; make_fixture_model.build(FIXTURE)
os.environ["GASTROVISION_MODEL_DIR"] = FIXTURE
os.environ["GASTROVISION_PROVIDER"] = "CPUExecutionProvider"
