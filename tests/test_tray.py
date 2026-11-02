# Tests for tray analysis
from typing import List
import numpy as np

from shrimp.models import Settings
from shrimp.tray import analyze_tray
from tests.conftest import FakeSegmenter


def make_rect_mask(h: int, w: int, top: int, left: int, shape=(600, 600)) -> np.ndarray:
    # Create rectangular boolean mask on blank canvas
    m = np.zeros(shape, bool)
    m[top:top + h, left:left + w] = True
    return m


def make_shrimp_masks(n: int) -> List[np.ndarray]:
    # Create n separate shrimp-like masks
    masks = []
    for i in range(n):
        m = np.zeros((600, 600), bool)
        top = 100 + i * 40
        m[top:top + 12, 100:220] = True
        masks.append(m)
    return masks


def test_scale_ruler(fake_photo: bytes):
    # Ruler determines scale in px per mm within 1 percent
    ruler = make_rect_mask(30, 300, 20, 20)
    shrimp = make_shrimp_masks(10)
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.status == "ok"
    assert res.reference == "ruler"
    assert res.scale_px_per_mm is not None
    assert abs(res.scale_px_per_mm - 2.0) / 2.0 < 0.01
    assert res.n_measured == 10
    assert res.n_left_out == 0
    assert res.size_per_kg is None
    assert res.mean_length_mm is not None
    assert len(res.shrimp) == 10


def test_scale_card(fake_photo: bytes):
    # Credit card sets scale from 85.6 mm side when no ruler is present
    card = make_rect_mask(108, 171, 20, 20)
    shrimp = make_shrimp_masks(2)
    seg = FakeSegmenter({"credit card": [card], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.status == "ok"
    assert res.reference == "card"
    assert res.scale_px_per_mm is not None
    assert abs(res.scale_px_per_mm - (171.0 / 85.6)) < 0.02


def test_ruler_beats_card(fake_photo: bytes):
    # Ruler takes precedence over card when both are detected
    ruler = make_rect_mask(30, 300, 20, 20)
    card = make_rect_mask(108, 171, 100, 20)
    shrimp = make_shrimp_masks(1)
    seg = FakeSegmenter({"ruler": [ruler], "credit card": [card], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.reference == "ruler"
    assert res.scale_px_per_mm is not None
    assert abs(res.scale_px_per_mm - 2.0) / 2.0 < 0.01


def test_no_reference(fake_photo: bytes):
    # When no reference is found status is no_reference with no millimetres
    shrimp = make_shrimp_masks(3)
    seg = FakeSegmenter({"shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.status == "no_reference"
    assert res.reference == "none"
    assert res.scale_px_per_mm is None
    assert res.mean_length_mm is None
    assert res.size_per_kg is None
    assert len(res.shrimp) == 3
    for s in res.shrimp:
        assert s.length_mm is None
        assert s.length_px > 0


def test_no_shrimp(fake_photo: bytes):
    # When SAM finds no shrimp status is no_shrimp
    ruler = make_rect_mask(30, 300, 20, 20)
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": []})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.status == "no_shrimp"
    assert res.size_per_kg is None
    assert res.n_measured == 0
    assert len(res.shrimp) == 0


def test_drop_lookalike(fake_photo: bytes):
    # Shrimp masks mostly inside reference mask are discarded
    ruler = make_rect_mask(30, 300, 20, 20)
    lookalike = make_rect_mask(28, 280, 21, 25)
    real_shrimp = make_shrimp_masks(1)[0]
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [lookalike, real_shrimp]})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.n_measured == 1
    assert len(res.shrimp) == 1
