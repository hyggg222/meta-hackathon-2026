# Tests for Service orchestration layer
from datetime import date
import hashlib
from typing import Optional
import numpy as np
import pytest

from shrimp.models import SegmentationError, Settings, ShrimpMeasure, TrayResult
from shrimp.service import Service
from shrimp.store import Store
from tests.conftest import FakeSegmenter


# Stub size table for service tests
class FakeTable:
    def __init__(self, temporary: bool = False, per_kg_val: Optional[float] = 50.0):
        # Store temporary flag and per_kg return value
        self.temporary = temporary
        self.per_kg_val = per_kg_val

    def per_kg(self, length_mm: float) -> Optional[float]:
        # Return mock size per kg
        return self.per_kg_val


# Build TrayResult with specified status
def make_tray(status: str, mean_length_mm: Optional[float] = 100.0, n: int = 5) -> TrayResult:
    # Construct mock tray result
    shrimp = [
        ShrimpMeasure(index=i, length_px=200.0, length_mm=mean_length_mm, overlapped=False, path=[(0.0, 0.0), (1.0, 1.0)])
        for i in range(n)
    ]
    return TrayResult(
        status=status,
        reference="ruler" if status != "no_reference" else "none",
        scale_px_per_mm=2.0 if status != "no_reference" else None,
        shrimp=shrimp if status != "no_shrimp" else [],
        n_measured=n if status not in ("no_shrimp", "no_reference") else 0,
        n_left_out=0,
        mean_length_mm=mean_length_mm if status == "ok" else None,
        size_per_kg=None,
        notices=[status] if status != "ok" else [],
    )


def test_add_sample_unsaved_statuses(monkeypatch, tmp_path):
    # Unsaved statuses save nothing and write no photo file
    photos_dir = tmp_path / "photos"
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable(), photos_dir=photos_dir)

    for status in ("too_few", "no_reference", "no_shrimp"):
        monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray(status))
        res = service.add_sample(b"photo_bytes", date(2026, 11, 2))
        assert res.status == status
        assert len(store.samples()) == 0
        assert not photos_dir.exists() or not list(photos_dir.iterdir())


def test_add_sample_segmentation_error(monkeypatch, tmp_path):
    # SegmentationError raises and saves nothing
    photos_dir = tmp_path / "photos"
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable(), photos_dir=photos_dir)

    def failing_analyze(*args, **kwargs):
        raise SegmentationError("sam failure")

    monkeypatch.setattr("shrimp.service.analyze_tray", failing_analyze)
    with pytest.raises(SegmentationError):
        service.add_sample(b"photo_bytes", date(2026, 11, 2))
    assert len(store.samples()) == 0
    assert not photos_dir.exists() or not list(photos_dir.iterdir())


def test_add_sample_saved_ok(monkeypatch, tmp_path):
    # Status ok is saved and writes photo file with sha hash
    photos_dir = tmp_path / "photos"
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable(), photos_dir=photos_dir)

    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=100.0, n=5))
    photo = b"sample_photo_content"
    day = date(2026, 11, 2)
    res = service.add_sample(photo, day)

    assert res.status == "ok"
    samples = store.samples()
    assert len(samples) == 1
    sha = hashlib.sha256(photo).hexdigest()[:8]
    expected_path = photos_dir / f"{day.isoformat()}-{sha}.img"
    assert expected_path.exists()
    assert expected_path.read_bytes() == photo
    assert samples[0].photo_path == str(expected_path)


def test_dashboard_one_and_two_samples(monkeypatch):
    # Dashboard flags and deltas appear after two samples
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable())

    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=80.0, n=5))
    service.add_sample(b"p1", date(2026, 11, 1))

    dash1 = service.dashboard()
    assert dash1.empty is False
    assert dash1.change_length_mm is None
    assert dash1.change_size_per_kg is None
    assert dash1.stall is None
    assert dash1.n_latest == 5
    assert dash1.n_previous is None

    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=82.0, n=6))
    service.add_sample(b"p2", date(2026, 11, 4))

    dash2 = service.dashboard()
    assert dash2.change_length_mm == pytest.approx(2.0)
    assert dash2.n_latest == 6
    assert dash2.n_previous == 5


def test_feed_cost_and_no_feed_notice(monkeypatch):
    # Feed cost calculates from latest feed or shows no feed notice
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable())
    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=90.0, n=5))
    service.add_sample(b"p", date(2026, 11, 2))

    dash_no_feed = service.dashboard()
    assert dash_no_feed.stall_day_cost_vnd is None
    assert "no_feed" in dash_no_feed.notices

    service.add_feed(date(2026, 11, 1), 100.0, 45000.0)
    dash_feed = service.dashboard()
    assert dash_feed.stall_day_cost_vnd == 4500000
    assert "no_feed" not in dash_feed.notices


def test_feed_validation():
    # Invalid feed values raise ValueError and save nothing
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable())
    day = date(2026, 11, 2)

    invalid_cases = [
        (-10.0, 45000.0),
        (0.0, 45000.0),
        (float("nan"), 45000.0),
        (float("inf"), 45000.0),
        ("100", 45000.0),
        (True, 45000.0),
        (100.0, -1.0),
        (100.0, 0.0),
        (100.0, float("nan")),
        (100.0, float("inf")),
        (100.0, "45000"),
        (100.0, False),
    ]

    for kg, price in invalid_cases:
        with pytest.raises(ValueError):
            service.add_feed(day, kg, price)
        assert len(store.feeds()) == 0


def test_settings_save_and_stall_threshold_flip(monkeypatch):
    # Updated stall threshold flips stall flag in dashboard
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable())

    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=70.0, n=5))
    service.add_sample(b"p1", date(2026, 11, 1))
    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=70.75, n=5))
    service.add_sample(b"p2", date(2026, 11, 4))

    dash = service.dashboard()
    assert dash.stall is True

    s = service.settings()
    s.stall_mm_per_day = 0.20
    saved = service.save_settings(s)
    assert saved.stall_mm_per_day == 0.20

    dash_new = service.dashboard()
    assert dash_new.stall is False


def test_settings_validation():
    # Zero negative nan thresholds and bad min_measured raise ValueError
    store = Store(":memory:")
    service = Service(FakeSegmenter(), store, FakeTable())
    base = service.settings()

    invalid_thresholds = [0.0, -1.0, float("nan"), float("inf"), "abc", True]
    fields = ["ruler_mm", "card_mm", "stall_mm_per_day", "harvest_per_kg", "feed_price_vnd"]

    for f in fields:
        for val in invalid_thresholds:
            s = Settings(**{**base.__dict__, f: val})
            with pytest.raises(ValueError) as excinfo:
                service.save_settings(s)
            assert f in str(excinfo.value)
            assert service.settings() == base

    for val in (0, -1, 1.5, "5", True, False):
        s = Settings(**{**base.__dict__, "min_measured": val})
        with pytest.raises(ValueError) as excinfo:
            service.save_settings(s)
        assert "min_measured" in str(excinfo.value)
        assert service.settings() == base


def test_service_persistence_across_instances(monkeypatch, tmp_path):
    # Samples and settings persist across service instances on same store file
    db_file = tmp_path / "test.db"
    store1 = Store(db_file)
    service1 = Service(FakeSegmenter(), store1, FakeTable())

    s = service1.settings()
    s.pond_name = "Pond Beta"
    s.ruler_mm = 200.0
    service1.save_settings(s)

    monkeypatch.setattr("shrimp.service.analyze_tray", lambda *args, **kwargs: make_tray("ok", mean_length_mm=85.0, n=5))
    service1.add_sample(b"photo1", date(2026, 11, 2))
    store1.close()

    store2 = Store(db_file)
    service2 = Service(FakeSegmenter(), store2, FakeTable())
    assert service2.settings().pond_name == "Pond Beta"
    assert service2.settings().ruler_mm == 200.0
    dash = service2.dashboard()
    assert len(dash.rows) == 1
    assert dash.rows[0].day == date(2026, 11, 2)
    store2.close()


def test_seed_demo_marked_in_dashboard():
    # Seeded demo rows in dashboard have demo flag set to True
    store = Store(":memory:")
    today = date(2026, 11, 2)
    store.seed_demo(today)
    service = Service(FakeSegmenter(), store, FakeTable())

    dash = service.dashboard()
    assert len(dash.rows) == 5
    assert all(r.demo is True for r in dash.rows)


def test_real_analyze_tray_flow():
    # Service calls real analyze_tray with fake segmenter
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = [np.zeros((300, 300), bool) for _ in range(5)]
    for i, s in enumerate(shrimp):
        s[100 + i * 20 : 110 + i * 20, 50:150] = True

    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    store = Store(":memory:")
    service = Service(seg, store, FakeTable())

    res = service.add_sample(b"dummy_bytes", date(2026, 11, 2))
    assert res.status == "ok"
    assert res.n_measured == 5
    assert len(store.samples()) == 1
