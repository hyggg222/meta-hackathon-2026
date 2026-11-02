# Tests for tray analysis
import time
from typing import List, Optional
import cv2
import numpy as np
import pytest

from shrimp.models import Analysis, SegmentationError, Settings, ShrimpMeasure
from shrimp.sizing import SizeTable
from shrimp.tray import analyze_shrimp, analyze_tray, summarize
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
    res = analyze_tray(fake_photo, Settings(min_measured=1), None, seg)
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


def test_tiny_ruler_no_reference(fake_photo: bytes):
    # A 1-pixel ruler mask gives no_reference without exception
    ruler = make_rect_mask(1, 1, 20, 20)
    shrimp = make_shrimp_masks(2)
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.status == "no_reference"
    assert res.reference == "none"
    assert res.scale_px_per_mm is None


def test_tiny_ruler_with_valid_card(fake_photo: bytes):
    # Tiny ruler mask falls through to valid card
    ruler = make_rect_mask(2, 2, 20, 20)
    card = make_rect_mask(108, 171, 20, 20)
    shrimp = make_shrimp_masks(2)
    seg = FakeSegmenter({"ruler": [ruler], "credit card": [card], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(min_measured=1), None, seg)
    assert res.status == "ok"
    assert res.reference == "card"
    assert res.scale_px_per_mm is not None
    assert abs(res.scale_px_per_mm - (171.0 / 85.6)) < 0.02


def test_parallel_calls_timing(fake_photo: bytes):
    # Concurrent segmenter calls finish under 0.7 s when each sleeps 0.3 s
    def slow_segmenter(photo: bytes, prompt: str) -> List[np.ndarray]:
        time.sleep(0.3)
        return []

    t0 = time.perf_counter()
    analyze_tray(fake_photo, Settings(), None, slow_segmenter)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.7


def test_parallel_calls_error_propagation(fake_photo: bytes):
    # SegmentationError raised in any prompt propagates unchanged
    def error_segmenter(photo: bytes, prompt: str) -> List[np.ndarray]:
        if prompt == "ruler":
            raise SegmentationError("ruler failure")
        return []

    with pytest.raises(SegmentationError, match="ruler failure"):
        analyze_tray(fake_photo, Settings(), None, error_segmenter)


class DummyTable:
    # Fake size table with configurable temporary flag and return value
    def __init__(self, temporary: bool, value: Optional[float] = 71.0):
        self.temporary = temporary
        self.value = value

    def per_kg(self, length_mm: float) -> Optional[float]:
        return self.value


def make_capsule_shrimp(x0: int, x1: int, y: int, r: int = 6, shape=(600, 600)) -> np.ndarray:
    # Create horizontal capsule shrimp mask
    canvas = np.zeros(shape, np.uint8)
    cv2.line(canvas, (x0, y), (x1, y), 255, thickness=2 * r)
    cv2.circle(canvas, (x0, y), r, 255, -1)
    cv2.circle(canvas, (x1, y), r, 255, -1)
    return canvas > 127


def test_tray_measured_and_left_out_counts(fake_photo: bytes):
    # Measured and left out counts match flags and mean excludes overlapped shrimp
    ruler = make_rect_mask(30, 300, 20, 20)
    clean = [make_capsule_shrimp(50, 138, 100 + i * 40, r=6) for i in range(4)]
    ov1 = make_capsule_shrimp(50, 150, 300, r=6)
    ov2 = make_capsule_shrimp(163, 263, 300, r=6)
    shrimp = clean + [ov1, ov2]

    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(min_measured=3), None, seg)
    assert res.n_measured == 4
    assert res.n_left_out == 2
    assert len(res.shrimp) == 6
    assert res.mean_length_mm is not None
    assert abs(res.mean_length_mm - 50.0) < 2.0


def test_tray_too_few_shrimp(fake_photo: bytes):
    # 4 measured shrimp with min_measured 5 gives too_few status and size_per_kg None
    ruler = make_rect_mask(30, 300, 20, 20)
    shrimp = [make_capsule_shrimp(50, 150, 100 + i * 40, r=6) for i in range(4)]
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(min_measured=5), DummyTable(temporary=True), seg)
    assert res.status == "too_few"
    assert res.size_per_kg is None
    assert res.n_measured == 4
    assert res.n_left_out == 0
    assert len(res.shrimp) == 4
    assert res.mean_length_mm is not None
    assert res.notices == []


def test_tray_min_measured_custom_setting(fake_photo: bytes):
    # Custom min_measured setting of 3 allows 3 shrimp to reach ok status
    ruler = make_rect_mask(30, 300, 20, 20)
    shrimp = [make_capsule_shrimp(50, 150, 100 + i * 40, r=6) for i in range(3)]
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(min_measured=3), None, seg)
    assert res.status == "ok"
    assert res.n_measured == 3


def test_tray_exact_five_real_table(fake_photo: bytes):
    # Exactly 5 measured shrimp of mean length 100 mm gives ok and size 71 with real table
    ruler = make_rect_mask(30, 300, 20, 20)
    shrimp = [make_capsule_shrimp(50, 237, 100 + i * 40, r=6) for i in range(5)]
    table = SizeTable.load("shrimp/size_table.json")
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(min_measured=5), table, seg)
    assert res.status == "ok"
    assert res.n_measured == 5
    assert res.mean_length_mm is not None
    assert abs(res.mean_length_mm - 100.0) < 1.0
    assert res.size_per_kg == pytest.approx(71.0, abs=2.0)
    assert "temporary_table" in res.notices
    assert "rough_estimate" in res.notices


def test_tray_outside_table_range(fake_photo: bytes):
    # Mean length outside 60-140 mm gives ok status, size None, and outside_table_range notice
    ruler = make_rect_mask(30, 300, 20, 20)
    shrimp = [make_capsule_shrimp(50, 138, 100 + i * 40, r=6) for i in range(5)]
    table = SizeTable.load("shrimp/size_table.json")
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    res = analyze_tray(fake_photo, Settings(min_measured=5), table, seg)
    assert res.status == "ok"
    assert res.mean_length_mm is not None
    assert abs(res.mean_length_mm - 50.0) < 1.0
    assert res.size_per_kg is None
    assert res.notices == ["outside_table_range"]


def test_tray_notices_temporary_vs_permanent(fake_photo: bytes):
    # Temporary table yields temporary_table and rough_estimate notices; permanent yields none
    ruler = make_rect_mask(30, 300, 20, 20)
    shrimp = [make_capsule_shrimp(50, 238, 100 + i * 40, r=6) for i in range(5)]
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})

    res_temp = analyze_tray(fake_photo, Settings(min_measured=5), DummyTable(temporary=True), seg)
    assert res_temp.notices == ["temporary_table", "rough_estimate"]

    res_perm = analyze_tray(fake_photo, Settings(min_measured=5), DummyTable(temporary=False), seg)
    assert res_perm.notices == []

    res_none = analyze_tray(fake_photo, Settings(min_measured=5), None, seg)
    assert res_none.notices == []


def test_summarize_default_equals_analyze_tray(fake_photo: bytes):
    # summarize with include=None gives identical TrayResult as analyze_tray
    ruler = make_rect_mask(30, 300, 20, 20)
    clean = [make_capsule_shrimp(50, 138, 100 + i * 40, r=6) for i in range(4)]
    ov1 = make_capsule_shrimp(50, 150, 300, r=6)
    ov2 = make_capsule_shrimp(163, 263, 300, r=6)
    shrimp = clean + [ov1, ov2]
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    settings = Settings(min_measured=3)
    tray_res = analyze_tray(fake_photo, settings, None, seg)
    analysis = analyze_shrimp(fake_photo, settings, seg)
    sum_res = summarize(analysis, None, settings, None)
    assert sum_res == tray_res


def test_summarize_manual_selection_six_shrimp(fake_photo: bytes):
    # Manual inclusion controls measured count, left out, and size calculation
    ruler = make_rect_mask(30, 300, 20, 20)
    clean = [make_capsule_shrimp(50, 150, 100 + i * 40, r=6) for i in range(5)]
    edge = make_capsule_shrimp(0, 100, 350, r=6)
    shrimp = clean + [edge]
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
    settings = Settings(min_measured=5)
    analysis = analyze_shrimp(fake_photo, settings, seg)

    # Automatic rule leaves one out
    auto_res = summarize(analysis, None, settings, None)
    assert auto_res.n_measured == 5
    assert auto_res.n_left_out == 1

    # Include all 6
    all_res = summarize(analysis, [0, 1, 2, 3, 4, 5], settings, None)
    assert all_res.n_measured == 6
    assert all_res.n_left_out == 0
    all_lens = [s.length_mm for s in analysis.shrimp if s.length_mm is not None]
    assert all_res.mean_length_mm == pytest.approx(float(np.mean(all_lens)))
    assert all_res.included == [0, 1, 2, 3, 4, 5]

    # Include [0, 1] with min_measured=5
    few_res = summarize(analysis, [0, 1], settings, None)
    assert few_res.status == "too_few"
    assert few_res.size_per_kg is None
    assert few_res.n_measured == 2
    assert few_res.included == [0, 1]

    # Empty list gives too_few and None mean
    empty_res = summarize(analysis, [], settings, None)
    assert empty_res.status == "too_few"
    assert empty_res.mean_length_mm is None
    assert empty_res.included == []


def test_summarize_bad_indices(fake_photo: bytes):
    # Non-ints, bools, duplicates, and out-of-range indices raise ValueError
    ruler = make_rect_mask(30, 300, 20, 20)
    clean = [make_capsule_shrimp(50, 150, 100 + i * 40, r=6) for i in range(5)]
    edge = make_capsule_shrimp(0, 100, 350, r=6)
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": clean + [edge]})
    analysis = analyze_shrimp(fake_photo, Settings(), seg)

    for bad in ([7], [-1], [0, 0], [True], ["1"]):
        with pytest.raises(ValueError):
            summarize(analysis, bad, Settings(), None)


def test_tray_fragment_excluded(fake_photo: bytes):
    # Fragment under min length is left out of default choice
    ruler = make_rect_mask(30, 450, 20, 20, shape=(800, 800))
    frag = make_capsule_shrimp(50, 127, 100, r=6, shape=(800, 800))
    s1 = make_capsule_shrimp(50, 307, 180, r=6, shape=(800, 800))
    s2 = make_capsule_shrimp(50, 307, 260, r=6, shape=(800, 800))
    s3 = make_capsule_shrimp(50, 307, 340, r=6, shape=(800, 800))
    s4 = make_capsule_shrimp(50, 307, 420, r=6, shape=(800, 800))
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [frag, s1, s2, s3, s4]})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.n_measured == 4
    assert res.n_left_out == 1
    assert 0 not in res.included
    assert res.included == [1, 2, 3, 4]
    assert res.mean_length_mm == pytest.approx(90.0, abs=1.0)


def test_tray_fragment_included_manually(fake_photo: bytes):
    # Manual include list counts fragment regardless of length
    ruler = make_rect_mask(30, 450, 20, 20, shape=(800, 800))
    frag = make_capsule_shrimp(50, 127, 100, r=6, shape=(800, 800))
    s1 = make_capsule_shrimp(50, 307, 180, r=6, shape=(800, 800))
    s2 = make_capsule_shrimp(50, 307, 260, r=6, shape=(800, 800))
    s3 = make_capsule_shrimp(50, 307, 340, r=6, shape=(800, 800))
    s4 = make_capsule_shrimp(50, 307, 420, r=6, shape=(800, 800))
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [frag, s1, s2, s3, s4]})
    analysis = analyze_shrimp(fake_photo, Settings(), seg)
    res = summarize(analysis, [0, 1, 2, 3, 4], Settings(), None)
    assert res.n_measured == 5
    assert res.n_left_out == 0
    assert 0 in res.included
    assert res.included == [0, 1, 2, 3, 4]


def test_tray_min_length_threshold(fake_photo: bytes):
    # Fragment counts when min length is lower or equal to length
    ruler = make_rect_mask(30, 450, 20, 20, shape=(800, 800))
    frag = make_capsule_shrimp(50, 127, 100, r=6, shape=(800, 800))
    s1 = make_capsule_shrimp(50, 307, 180, r=6, shape=(800, 800))
    s2 = make_capsule_shrimp(50, 307, 260, r=6, shape=(800, 800))
    s3 = make_capsule_shrimp(50, 307, 340, r=6, shape=(800, 800))
    s4 = make_capsule_shrimp(50, 307, 420, r=6, shape=(800, 800))
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": [frag, s1, s2, s3, s4]})
    analysis = analyze_shrimp(fake_photo, Settings(), seg)

    res20 = summarize(analysis, None, Settings(min_length_mm=20.0), None)
    assert res20.n_measured == 5
    assert 0 in res20.included

    frag_len = analysis.shrimp[0].length_mm
    assert frag_len is not None
    assert abs(frag_len - 30.0) < 1.0

    res_exact = summarize(analysis, None, Settings(min_length_mm=frag_len), None)
    assert res_exact.n_measured == 5
    assert 0 in res_exact.included

    res_above = summarize(analysis, None, Settings(min_length_mm=frag_len + 0.1), None)
    assert res_above.n_measured == 4
    assert 0 not in res_above.included


def test_tray_no_reference_length(fake_photo: bytes):
    # When reference is missing no length filtering is applied
    frag = make_capsule_shrimp(50, 127, 100, r=6, shape=(800, 800))
    s1 = make_capsule_shrimp(50, 307, 180, r=6, shape=(800, 800))
    s2 = make_capsule_shrimp(50, 307, 260, r=6, shape=(800, 800))
    s3 = make_capsule_shrimp(50, 307, 340, r=6, shape=(800, 800))
    s4 = make_capsule_shrimp(50, 307, 420, r=6, shape=(800, 800))
    seg = FakeSegmenter({"shrimp": [frag, s1, s2, s3, s4]})
    res = analyze_tray(fake_photo, Settings(), None, seg)
    assert res.status == "no_reference"
    assert res.scale_px_per_mm is None
    assert res.n_measured == 5
    assert res.n_left_out == 0
    assert res.included == [0, 1, 2, 3, 4]


def test_summarize_sd_length():
    # Chosen lengths give sample standard deviation with ddof=1, None for < 2 shrimp
    settings = Settings(min_measured=1, min_length_mm=50.0)
    shrimp = [
        ShrimpMeasure(index=0, length_px=160.0, length_mm=80.0, overlapped=False, path=[]),
        ShrimpMeasure(index=1, length_px=180.0, length_mm=90.0, overlapped=False, path=[]),
        ShrimpMeasure(index=2, length_px=200.0, length_mm=100.0, overlapped=False, path=[]),
    ]
    analysis = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp)

    res = summarize(analysis, [0, 1, 2], settings, None)
    assert res.sd_length_mm == pytest.approx(10.0)

    res_one = summarize(analysis, [0], settings, None)
    assert res_one.sd_length_mm is None

    res_two = summarize(analysis, [0, 1], settings, None)
    assert res_two.sd_length_mm == pytest.approx(7.0710678, rel=1e-4)
    assert res_two.sd_length_mm != res.sd_length_mm


def test_summarize_merged_shrimp():
    # Merged shrimp is excluded by default, but counted when include list names it
    settings = Settings(min_measured=1, min_length_mm=50.0)
    shrimp = [
        ShrimpMeasure(index=0, length_px=200.0, length_mm=100.0, overlapped=False, path=[], merged=False),
        ShrimpMeasure(index=1, length_px=200.0, length_mm=100.0, overlapped=False, path=[], merged=False),
        ShrimpMeasure(index=2, length_px=400.0, length_mm=200.0, overlapped=False, path=[], merged=True),
    ]
    analysis = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp)

    res_default = summarize(analysis, None, settings, None)
    assert res_default.included == [0, 1]
    assert res_default.n_measured == 2
    assert res_default.n_left_out == 1
    assert 2 not in res_default.included

    res_manual = summarize(analysis, [0, 1, 2], settings, None)
    assert res_manual.included == [0, 1, 2]
    assert res_manual.n_measured == 3
    assert res_manual.n_left_out == 0
    assert 2 in res_manual.included
    assert res_manual.mean_length_mm == pytest.approx(400.0 / 3.0)


def test_crowded_notice_tray():
    # Tray of 10 masks with 6 left out is crowded; 3 left out is not; < 8 masks is not; explicit include does not change notice
    settings = Settings(min_measured=1, min_length_mm=50.0)

    # 10 masks where 6 touch each other (overlapped)
    shrimp_10_crowded = [
        ShrimpMeasure(
            index=i,
            length_px=200.0,
            length_mm=100.0,
            overlapped=(i < 6),
            path=[],
            merged=False,
        )
        for i in range(10)
    ]
    analysis_10_crowded = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp_10_crowded)
    res_crowded = summarize(analysis_10_crowded, None, settings, None)
    assert "crowded" in res_crowded.notices

    # Explicit include does not change the crowded notice
    res_crowded_manual = summarize(analysis_10_crowded, list(range(10)), settings, None)
    assert "crowded" in res_crowded_manual.notices

    # 10 masks where only 3 are left out
    shrimp_10_uncrowded = [
        ShrimpMeasure(
            index=i,
            length_px=200.0,
            length_mm=100.0,
            overlapped=(i < 3),
            path=[],
            merged=False,
        )
        for i in range(10)
    ]
    analysis_10_uncrowded = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp_10_uncrowded)
    res_uncrowded = summarize(analysis_10_uncrowded, None, settings, None)
    assert "crowded" not in res_uncrowded.notices

    # Fewer than 8 masks never crowded (e.g. 7 masks with 5 overlapped)
    shrimp_7 = [
        ShrimpMeasure(
            index=i,
            length_px=200.0,
            length_mm=100.0,
            overlapped=(i < 5),
            path=[],
            merged=False,
        )
        for i in range(7)
    ]
    analysis_7 = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp_7)
    res_7 = summarize(analysis_7, None, settings, None)
    assert "crowded" not in res_7.notices


