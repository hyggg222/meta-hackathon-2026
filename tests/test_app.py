# Tests for FastAPI application routes
from datetime import date
import inspect
from fastapi.testclient import TestClient
import numpy as np
import pytest

from shrimp.app import create_app
from shrimp.models import SegmentationError, Settings
from shrimp.service import Service
from shrimp.store import Store
from tests.conftest import FakeSegmenter
from tests.test_service import FakeTable


# Build test service instance
def make_test_service(seg=None, store=None, table=None) -> Service:
    # Helper to construct service with defaults
    return Service(
        segmenter=seg or FakeSegmenter(),
        store=store or Store(":memory:"),
        table=table or FakeTable(),
    )


def test_samples_route_ok():
    # POST /api/samples returns 200 with TrayResult dictionary
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = np.zeros((300, 300), bool)
    shrimp[100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [shrimp]})
    store = Store(":memory:")
    store.save_settings(Settings(min_measured=1))
    service = make_test_service(seg=seg, store=store)
    app = create_app(service)
    client = TestClient(app)

    resp = client.post("/api/samples", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
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
    assert "outline" in data["shrimp"][0]
    assert isinstance(data["shrimp"][0]["outline"], list)
    assert len(data["shrimp"][0]["outline"]) > 0
    assert all(isinstance(pt, list) and len(pt) == 2 for pt in data["shrimp"][0]["outline"])


def test_samples_route_with_day():
    # POST /api/samples accepts optional day form parameter
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = np.zeros((300, 300), bool)
    shrimp[100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [shrimp]})
    store = Store(":memory:")
    store.save_settings(Settings(min_measured=1))
    service = make_test_service(seg=seg, store=store)
    app = create_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/samples",
        files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")},
        data={"day": "2026-11-05"},
    )
    assert resp.status_code == 200
    samples = store.samples()
    assert len(samples) == 1
    assert samples[0].day == date(2026, 11, 5)


def test_samples_route_bad_day():
    # POST /api/samples returns 422 when day parameter is malformed
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/samples",
        files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")},
        data={"day": "not-a-valid-date"},
    )
    assert resp.status_code == 422
    assert "error" in resp.json()


def test_samples_route_segmentation_error():
    # POST /api/samples returns 502 with error message on SegmentationError
    seg = FakeSegmenter(exc=SegmentationError("SAM API connection failed"))
    service = make_test_service(seg=seg)
    app = create_app(service)
    client = TestClient(app)

    resp = client.post("/api/samples", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
    assert resp.status_code == 502
    data = resp.json()
    assert "error" in data
    assert "SAM API connection failed" in data["error"]


def test_samples_route_sync():
    # Route is a plain def and returns 200 with status for fake segmenter
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = np.zeros((300, 300), bool)
    shrimp[100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [shrimp]})
    store = Store(":memory:")
    store.save_settings(Settings(min_measured=1))
    service = make_test_service(seg=seg, store=store)
    app = create_app(service)
    route = next(r for r in app.routes if getattr(r, "path", None) == "/api/samples")
    assert not inspect.iscoroutinefunction(route.endpoint)

    client = TestClient(app)
    resp = client.post("/api/samples", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_samples_route_too_few():
    # POST /api/samples returns too_few and does not save sample when below min_measured
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp1 = np.zeros((300, 300), bool)
    shrimp1[100:110, 50:150] = True
    shrimp2 = np.zeros((300, 300), bool)
    shrimp2[150:160, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [shrimp1, shrimp2]})
    service = make_test_service(seg=seg)
    app = create_app(service)
    client = TestClient(app)

    resp = client.post("/api/samples", files={"photo": ("tray.jpg", b"fake_bytes", "image/jpeg")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "too_few"

    dash_resp = client.get("/api/dashboard")
    assert dash_resp.status_code == 200
    assert dash_resp.json()["empty"] is True


def test_samples_route_upload_too_large():
    # Large photo upload returns 413 without invoking segmenter
    def failing_segmenter(photo: bytes, prompt: str):
        raise AssertionError("Segmenter should not be called")

    service = make_test_service(seg=failing_segmenter)
    app = create_app(service)
    client = TestClient(app)
    too_large_bytes = b"x" * (15 * 1024 * 1024 + 1)
    resp = client.post(
        "/api/samples",
        files={"photo": ("tray.jpg", too_large_bytes, "image/jpeg")},
    )
    assert resp.status_code == 413
    assert resp.json() == {"error": "photo too large"}


def test_root_page():
    # GET / serves index.html with required UI elements and status messages
    service = make_test_service()
    app = create_app(service)
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
    assert "/api/samples" in html
    assert "/api/analyze" not in html


def test_dashboard_route_empty():
    # GET /api/dashboard returns empty dashboard model on fresh store
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["empty"] is True
    assert data["rows"] == []
    assert data["chart"] == []


def test_dashboard_route_with_data():
    # GET /api/dashboard returns populated rows and chart with ISO dates
    store = Store(":memory:")
    service = make_test_service(store=store)
    store.seed_demo(date(2026, 11, 2))
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["empty"] is False
    assert len(data["rows"]) == 5
    for row in data["rows"]:
        assert isinstance(row["day"], str)
        assert len(row["day"]) == 10
    for pt in data["chart"]:
        assert isinstance(pt["day"], str)


def test_feed_route_ok():
    # POST /api/feed stores valid feed entry and returns 200
    store = Store(":memory:")
    service = make_test_service(store=store)
    app = create_app(service)
    client = TestClient(app)

    payload = {"day": "2026-11-02", "kg_per_day": 100.0, "price_vnd": 45000.0}
    resp = client.post("/api/feed", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {}
    feeds = store.feeds()
    assert len(feeds) == 1
    assert feeds[0].day == date(2026, 11, 2)
    assert feeds[0].kg_per_day == 100.0
    assert feeds[0].price_vnd == 45000


@pytest.mark.parametrize(
    "payload",
    [
        {"day": "2026-11-02", "kg_per_day": -10.0, "price_vnd": 45000},
        {"day": "2026-11-02", "kg_per_day": 0.0, "price_vnd": 45000},
        {"day": "2026-11-02", "kg_per_day": "100", "price_vnd": 45000},
        {"day": "2026-11-02", "kg_per_day": 100.0, "price_vnd": -1},
        {"day": "2026-11-02", "kg_per_day": 100.0, "price_vnd": 0},
        {"day": "2026-11-02", "kg_per_day": 100.0, "price_vnd": "45000"},
        {"day": "bad-date", "kg_per_day": 100.0, "price_vnd": 45000},
    ],
)
def test_feed_route_invalid(payload):
    # POST /api/feed rejects invalid feed values with 422
    store = Store(":memory:")
    service = make_test_service(store=store)
    app = create_app(service)
    client = TestClient(app)

    resp = client.post("/api/feed", json=payload)
    assert resp.status_code == 422
    assert "error" in resp.json()
    assert len(store.feeds()) == 0


def test_settings_routes():
    # GET and PUT /api/settings read and update settings or reject invalid values
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["feed_price_vnd"] == 45000

    data["stall_mm_per_day"] = 0.25
    data["pond_name"] = "Pond Delta"
    put_resp = client.put("/api/settings", json=data)
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["stall_mm_per_day"] == 0.25
    assert updated["pond_name"] == "Pond Delta"
    assert service.settings().stall_mm_per_day == 0.25

    invalid_put = client.put("/api/settings", json={**data, "stall_mm_per_day": -0.5})
    assert invalid_put.status_code == 422
    assert "error" in invalid_put.json()


def test_settings_partial_update_preserves_omitted_fields():
    # PUT /api/settings applies only provided fields and rejects unknown keys
    store = Store(":memory:")
    service = make_test_service(store=store)
    s = service.settings()
    s.ruler_mm = 200.0
    service.save_settings(s)

    app = create_app(service)
    client = TestClient(app)

    put_resp = client.put("/api/settings", json={"pond_name": "B"})
    assert put_resp.status_code == 200
    assert put_resp.json()["pond_name"] == "B"
    assert put_resp.json()["ruler_mm"] == 200.0

    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    assert get_resp.json()["ruler_mm"] == 200.0
    assert get_resp.json()["pond_name"] == "B"

    bad_put = client.put("/api/settings", json={"unknown_key": "val"})
    assert bad_put.status_code == 422


def test_settings_route_huge_numbers():
    # PUT /api/settings rejects huge numbers with 422 and saves nothing
    store = Store(":memory:")
    service = make_test_service(store=store)
    app = create_app(service)
    client = TestClient(app)
    original = service.settings()

    for val in (10**400, 1e30, 2**63):
        for field_name in ("ruler_mm", "feed_price_vnd", "card_mm", "stall_mm_per_day", "harvest_per_kg", "min_measured"):
            resp = client.put("/api/settings", json={field_name: val})
            assert resp.status_code == 422
            assert "error" in resp.json()
            assert service.settings() == original


def test_settings_route_invalid_pond_name_and_feed_price():
    # PUT /api/settings rejects invalid types for pond_name and feed_price_vnd
    store = Store(":memory:")
    service = make_test_service(store=store)
    app = create_app(service)
    client = TestClient(app)
    original = service.settings()

    for payload in ({"pond_name": {"a": 1}}, {"a": 1}, {"pond_name": None}, {"feed_price_vnd": 45000.5}):
        resp = client.put("/api/settings", json=payload)
        assert resp.status_code == 422
        assert "error" in resp.json()
        assert service.settings() == original


def test_feed_route_huge_numbers():
    # POST /api/feed rejects huge numbers with 422 and saves nothing
    store = Store(":memory:")
    service = make_test_service(store=store)
    app = create_app(service)
    client = TestClient(app)

    for val in (10**400, 1e30, 2**63):
        resp_kg = client.post("/api/feed", json={"day": "2026-11-02", "kg_per_day": val, "price_vnd": 45000})
        assert resp_kg.status_code == 422
        assert "error" in resp_kg.json()
        assert len(store.feeds()) == 0

        resp_price = client.post("/api/feed", json={"day": "2026-11-02", "kg_per_day": 100.0, "price_vnd": val})
        assert resp_price.status_code == 422
        assert "error" in resp_price.json()
        assert len(store.feeds()) == 0
