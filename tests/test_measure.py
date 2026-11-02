# Tests for centerline measurement
import math
from typing import List, Tuple
import cv2
import numpy as np

from shrimp.measure import measure


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
