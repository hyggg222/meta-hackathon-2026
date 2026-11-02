# Tests for centerline measurement
import math
from typing import List, Tuple
import cv2
import numpy as np

from shrimp.measure import OverlapRule, centerline, longest_side_branch, measure


def make_synth_mask(arc: float, r_curve: float, r0: float, r1: float, noise: int = 0) -> Tuple[np.ndarray, float]:
    # Generate synthetic curved mask with known centerline length
    scale = 2
    size = int(max(2 * min(r_curve, 800) + 100, arc + 120)) if r_curve < 1e5 else int(arc + 120)
    size = min(size, 450)
    canvas = np.zeros((size * scale, size * scale), np.uint8)
    phi = arc / r_curve
    cx, cy = (size * scale) / 2.0, (size * scale) / 2.0
    steps = 400
    for t in np.linspace(0, 1, steps):
        ang = -phi / 2.0 + phi * t
        if r_curve < 1e5:
            x = cx + r_curve * scale * math.sin(ang)
            y = cy + r_curve * scale * (1.0 - math.cos(ang)) - r_curve * scale * (1.0 - math.cos(phi / 2.0)) * 0.5
        else:
            x = cx - arc * scale / 2.0 + arc * scale * t
            y = cy
        r = (r0 + (r1 - r0) * t) * scale
        cv2.circle(canvas, (int(round(x)), int(round(y))), int(round(r)), 255, -1)
    mask = cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA) > 127
    if noise:
        rng = np.random.default_rng(42)
        n = cv2.GaussianBlur(rng.random(mask.shape).astype(np.float32), (0, 0), 2.0)
        bl = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 1.0)
        mask = (bl + (n - n.mean()) * 1.2) > 0.5
    true_len = arc + r0 + r1
    return mask, true_len


def test_synth_length():
    # Recover known centerline length within 3% individual and 1% mean error
    errs: List[float] = []
    for arc in (120, 250):
        for r_curve in (60, 100, 200, 400, 1e6):
            if arc / r_curve > 5.5:
                continue
            for r0, r1 in ((18, 8), (10, 5)):
                for noise in (0, 1):
                    mask, true_len = make_synth_mask(arc, r_curve, r0, r1, noise)
                    results = measure([mask], px_per_mm=None)
                    assert len(results) == 1
                    measured = results[0].length_px
                    err = 100.0 * abs(measured - true_len) / true_len
                    assert err < 3.0
                    errs.append(err)
    assert len(errs) >= 30
    assert np.mean(errs) < 1.0


def test_curved_vs_bbox():
    # Curved mask length follows arc and exceeds bounding-box diagonal
    mask, _ = make_synth_mask(arc=250, r_curve=60, r0=10, r1=10, noise=0)
    ys, xs = np.nonzero(mask)
    bbox_diag = math.hypot(xs.max() - xs.min(), ys.max() - ys.min())
    results = measure([mask], px_per_mm=2.0)
    assert len(results) == 1
    shrimp = results[0]
    assert shrimp.length_px > 1.3 * bbox_diag
    assert shrimp.length_mm is not None
    assert abs(shrimp.length_mm - shrimp.length_px / 2.0) < 1e-4
    assert shrimp.overlapped is False


def test_measure_zero_or_negative_scale():
    # Scale 0.0 or negative yields length_mm None without ZeroDivisionError
    mask, _ = make_synth_mask(arc=120, r_curve=60, r0=10, r1=5, noise=0)
    res_zero = measure([mask], px_per_mm=0.0)
    assert len(res_zero) == 1
    assert res_zero[0].length_mm is None

    res_neg = measure([mask], px_per_mm=-1.5)
    assert len(res_neg) == 1
    assert res_neg[0].length_mm is None


def make_straight_shrimp(x0: int, x1: int, y: int, r: int, shape=(400, 400)) -> np.ndarray:
    # Create horizontal capsule shrimp mask from x0 to x1 with radius r
    canvas = np.zeros(shape, np.uint8)
    cv2.line(canvas, (x0, y), (x1, y), 255, thickness=2 * r)
    cv2.circle(canvas, (x0, y), r, 255, -1)
    cv2.circle(canvas, (x1, y), r, 255, -1)
    return canvas > 127


def add_antenna(mask: np.ndarray, path: List[Tuple[float, float]], length_ratio: float = 0.3, thickness: int = 1) -> np.ndarray:
    # Add thin antenna line sticking out from mask end
    m = mask.astype(np.uint8).copy()
    p0 = np.array(path[0])
    p1 = np.array(path[1]) if len(path) > 1 else p0 + np.array([1.0, 0.0])
    v = p0 - p1
    v_norm = float(np.hypot(v[0], v[1]))
    v = v / v_norm if v_norm > 0 else np.array([-1.0, 0.0])
    body_len = float(len(path))
    ant_len = body_len * length_ratio
    p_end = p0 + v * ant_len
    cv2.line(
        m,
        (int(round(p0[0])), int(round(p0[1]))),
        (int(round(p_end[0])), int(round(p_end[1]))),
        1,
        thickness=thickness,
    )
    return m > 0


def test_antenna_length_tolerance():
    # Adding thin antennae changes measured length by less than 3 percent
    base_mask, _ = make_synth_mask(arc=200, r_curve=300, r0=14, r1=7, noise=0)
    base_res = measure([base_mask], px_per_mm=None)
    assert len(base_res) == 1
    base_len = base_res[0].length_px
    path = base_res[0].path

    for thickness in (1, 2):
        ant_mask = add_antenna(base_mask, path, length_ratio=0.3, thickness=thickness)
        ant_res = measure([ant_mask], px_per_mm=None)
        assert len(ant_res) == 1
        ant_len = ant_res[0].length_px
        err = abs(ant_len - base_len) / base_len
        assert err < 0.03


def test_overlap_touching_ends():
    # Shrimp whose ends are 1 px apart are both flagged overlapped with length preserved
    s1 = make_straight_shrimp(50, 150, 100, r=6)
    s2 = make_straight_shrimp(163, 263, 100, r=6)
    results = measure([s1, s2], px_per_mm=2.0)
    assert len(results) == 2
    assert results[0].overlapped is True
    assert results[1].overlapped is True
    assert results[0].length_mm is not None
    assert results[1].length_mm is not None

    s3 = make_straight_shrimp(50, 150, 100, r=6)
    s4 = make_straight_shrimp(220, 320, 250, r=6)
    res_far = measure([s3, s4], px_per_mm=2.0)
    assert res_far[0].overlapped is False
    assert res_far[1].overlapped is False


def test_overlap_image_border():
    # Shrimp touching border with end is overlapped; shrimp 30 px away is not
    s_edge = make_straight_shrimp(6, 120, 100, r=6)
    res_edge = measure([s_edge], px_per_mm=2.0)
    assert res_edge[0].overlapped is True

    s_away = make_straight_shrimp(36, 150, 100, r=6)
    res_away = measure([s_away], px_per_mm=2.0)
    assert res_away[0].overlapped is False


def test_overlap_middle_touch_not_flagged():
    # Touching another mask or border only along the middle does not flag the shrimp
    s_main = make_straight_shrimp(50, 200, 100, r=6)
    s_touch = make_straight_shrimp(125, 125, 120, r=4)
    res = measure([s_main, s_touch], px_per_mm=2.0)
    assert res[0].overlapped is False

    canvas = np.zeros((400, 400), np.uint8)
    cv2.ellipse(canvas, (200, 100), (96, 96), 0, 180, 360, 255, thickness=8)
    res_arch = measure([canvas > 127], px_per_mm=2.0)
    assert res_arch[0].overlapped is False


def test_overlap_custom_rule():
    # OverlapRule parameters are respected
    s1 = make_straight_shrimp(50, 150, 100, r=6)
    s2 = make_straight_shrimp(167, 267, 100, r=6)
    res_default = measure([s1, s2], px_per_mm=1.0)
    assert res_default[0].overlapped is False

    res_custom = measure([s1, s2], px_per_mm=1.0, rule=OverlapRule(touch_px=6.0))
    assert res_custom[0].overlapped is True


def shoelace_area(pts: List[Tuple[float, float]]) -> float:
    # Compute polygon area using shoelace formula
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def test_rectangle_outline():
    # Filled 20x100 rectangle has simplified outline of 4 to 40 points and area within 10%
    mask = np.zeros((200, 200), bool)
    mask[50:70, 50:150] = True
    results = measure([mask], px_per_mm=None)
    assert len(results) == 1
    shrimp = results[0]

    assert 4 <= len(shrimp.outline) <= 40
    for x, y in shrimp.outline:
        assert 49.0 <= x <= 150.0
        assert 49.0 <= y <= 70.0

    area = shoelace_area(shrimp.outline)
    assert 1800.0 <= area <= 2200.0

    expected_len, sm, _, _ = centerline(mask)
    assert shrimp.length_px == expected_len
    assert shrimp.path == [(float(x), float(y)) for x, y in sm]
    assert shrimp.overlapped is False


def test_empty_mask_outline():
    # Empty mask yields empty outline
    empty = np.zeros((200, 200), bool)
    results = measure([empty], px_per_mm=None)
    assert len(results) == 1
    assert results[0].outline == []
    from shrimp.measure import outline_of
    assert outline_of(empty) == []


def make_band_mask(pt1: Tuple[int, int], pt2: Tuple[int, int], thickness: int = 20, shape=(600, 600)) -> np.ndarray:
    # Create straight band mask on canvas
    canvas = np.zeros(shape, np.uint8)
    cv2.line(canvas, pt1, pt2, 255, thickness=thickness)
    return canvas > 127


def make_x_mask(center: Tuple[int, int] = (300, 300), arm: int = 80, thickness: int = 20, shape=(600, 600)) -> np.ndarray:
    # Create X-shaped mask of two crossing bands
    canvas = np.zeros(shape, np.uint8)
    cx, cy = center
    cv2.line(canvas, (cx - arm, cy - arm), (cx + arm, cy + arm), 255, thickness=thickness)
    cv2.line(canvas, (cx - arm, cy + arm), (cx + arm, cy - arm), 255, thickness=thickness)
    return canvas > 127


def make_t_mask(origin: Tuple[int, int] = (200, 200), bar_len: int = 160, stem_len: int = 120, thickness: int = 20, shape=(600, 600)) -> np.ndarray:
    # Create T-shaped mask
    canvas = np.zeros(shape, np.uint8)
    x0, y0 = origin
    cv2.line(canvas, (x0, y0), (x0 + bar_len, y0), 255, thickness=thickness)
    cv2.line(canvas, (x0 + bar_len // 2, y0), (x0 + bar_len // 2, y0 + stem_len), 255, thickness=thickness)
    return canvas > 127


def test_branch_helper_curve_x_t():
    # Single curved band has longest side branch < 0.35; X and T shapes have >= 0.35
    curve, _ = make_synth_mask(arc=200, r_curve=300, r0=10, r1=10, noise=0)
    branch_curve, main_curve = longest_side_branch(curve)
    ratio_curve = branch_curve / main_curve if main_curve > 0 else 0.0
    assert ratio_curve < 0.35

    mask_x = make_x_mask(center=(200, 200), arm=80, thickness=20, shape=(400, 400))
    branch_x, main_x = longest_side_branch(mask_x)
    ratio_x = branch_x / main_x if main_x > 0 else 0.0
    assert ratio_x >= 0.35

    mask_t = make_t_mask(origin=(100, 100), bar_len=160, stem_len=120, thickness=20, shape=(400, 400))
    branch_t, main_t = longest_side_branch(mask_t)
    ratio_t = branch_t / main_t if main_t > 0 else 0.0
    assert ratio_t >= 0.35


def test_measure_branching_and_length_rule():
    # Tray of 5 similar 20x100 bands + 1 X: only X is merged; double length among 5 similar is merged
    bands = [make_band_mask((50, 40 + i * 40), (150, 40 + i * 40), thickness=20) for i in range(5)]
    x_mask = make_x_mask(center=(400, 400), arm=60, thickness=20)
    res_x = measure(bands + [x_mask], px_per_mm=None)
    assert len(res_x) == 6
    for s in res_x[:5]:
        assert s.merged is False
    assert res_x[5].merged is True

    double_band = make_band_mask((50, 300), (250, 300), thickness=20)
    res_double = measure(bands + [double_band], px_per_mm=None)
    assert len(res_double) == 6
    for s in res_double[:5]:
        assert s.merged is False
    assert res_double[5].merged is True


def test_measure_two_masks_length_rule():
    # With only two masks nothing is merged by the length rule
    s1 = make_band_mask((50, 50), (150, 50), thickness=20)
    s2 = make_band_mask((50, 150), (350, 150), thickness=20)
    res = measure([s1, s2], px_per_mm=None)
    assert len(res) == 2
    assert res[0].merged is False
    assert res[1].merged is False


def test_measure_normal_tray_not_merged():
    # Normal tray has no merged shrimp
    bands = [make_band_mask((50, 40 + i * 50), (150, 40 + i * 50), thickness=20) for i in range(6)]
    res = measure(bands, px_per_mm=None)
    assert len(res) == 6
    for s in res:
        assert s.merged is False


