# Tests for FastAPI application routes
import inspect
from fastapi.testclient import TestClient
import numpy as np

from shrimp.app import create_app
from shrimp.models import SegmentationError, Settings
from tests.conftest import FakeSegmenter


def test_analyze_route_ok():
    # POST /api/analyze returns 200 with TrayResult dictionary
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = np.zeros((300, 300), bool)
    shrimp[100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [shrimp]})
    app = create_app(seg, settings=Settings(min_measured=1))
    client = TestClient(app)

    resp = client.post("/api/analyze", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["reference"] == "ruler"
    assert data["scale_px_per_mm"] is not None
    assert data["n_measured"] == 1
    assert data["n_left_out"] == 0
    assert len(data["shrimp"]) == 1
    assert isinstance(data["shrimp"][0]["length_px"], float)
    assert isinstance(data["shrimp"][0]["length_mm"], float)
    assert isinstance(data["shrimp"][0]["path"], list)


def test_analyze_route_segmentation_error():
    # POST /api/analyze returns 502 with error message on SegmentationError
    seg = FakeSegmenter(exc=SegmentationError("SAM API connection failed"))
    app = create_app(seg)
    client = TestClient(app)

    resp = client.post("/api/analyze", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
    assert resp.status_code == 502
    data = resp.json()
    assert "error" in data
    assert "SAM API connection failed" in data["error"]


def test_root_page():
    # GET / serves index.html with required UI elements and status messages
    app = create_app(FakeSegmenter())
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'accept="image/*"' in html
    assert 'capture="environment"' in html
    assert "Working..." in html
    assert "N measured, M left out" in html
    assert "No ruler or card found, no millimetres shown" in html
    assert "No shrimp found" in html
    assert "Could not process the photo, nothing was saved" in html


def test_analyze_route_sync():
    # Route is a plain def and returns 200 with status for fake segmenter
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = np.zeros((300, 300), bool)
    shrimp[100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [shrimp]})
    app = create_app(seg, settings=Settings(min_measured=1))
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/analyze")
    assert not inspect.iscoroutinefunction(route.endpoint)

    client = TestClient(app)
    resp = client.post("/api/analyze", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_analyze_route_upload_too_large():
    # Large photo upload returns 413 without invoking segmenter
    def failing_segmenter(photo: bytes, prompt: str):
        raise AssertionError("Segmenter should not be called")

    app = create_app(failing_segmenter)
    client = TestClient(app)
    too_large_bytes = b"x" * (15 * 1024 * 1024 + 1)
    resp = client.post(
        "/api/analyze",
        files={"photo": ("tray.jpg", too_large_bytes, "image/jpeg")},
    )
    assert resp.status_code == 413
    assert resp.json() == {"error": "photo too large"}

