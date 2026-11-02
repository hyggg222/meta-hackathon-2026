# Tray analysis orchestrating reference detection, scaling, and shrimp measurement
import concurrent.futures
from typing import Any, List, Optional, Tuple
import cv2
import numpy as np

from shrimp.measure import largest, measure
from shrimp.models import Analysis, Segmenter, Settings, TrayResult


def rect_sides(mask: np.ndarray) -> Tuple[float, float]:
    # Return long and short sides of minimum bounding rectangle
    m = largest(mask)
    if not np.any(m):
        return 0.0, 0.0
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return 0.0, 0.0
    c = max(cnts, key=cv2.contourArea)
    (_, _), (w, h), _ = cv2.minAreaRect(c)
    return float(max(w, h)), float(min(w, h))


def is_valid_ref(mask: np.ndarray) -> bool:
    # Reference mask counts only if long side is at least 5% of longer image side
    if not np.any(mask):
        return False
    long_side, _ = rect_sides(mask)
    return long_side >= 0.05 * max(mask.shape)


def analyze_shrimp(
    photo: bytes,
    settings: Settings,
    segmenter: Segmenter,
) -> Analysis:
    # Segment photo and measure detected shrimp
    prompts = ["shrimp", "ruler", "credit card"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(segmenter, photo, p): p for p in prompts}
        results = {}
        for future in concurrent.futures.as_completed(futures):
            prompt = futures[future]
            results[prompt] = future.result()

    shrimp_raw = results["shrimp"]
    ruler_raw = results["ruler"]
    card_raw = results["credit card"]

    valid_rulers = [m for m in ruler_raw if is_valid_ref(m)]
    valid_cards = [m for m in card_raw if is_valid_ref(m)]

    if valid_rulers:
        reference = "ruler"
        ref_mask = max(valid_rulers, key=lambda m: int(np.sum(m)))
        long_side, _ = rect_sides(ref_mask)
        scale_px_per_mm = float(long_side / settings.ruler_mm)
    elif valid_cards:
        reference = "card"
        ref_mask = max(valid_cards, key=lambda m: int(np.sum(m)))
        long_side, _ = rect_sides(ref_mask)
        scale_px_per_mm = float(long_side / settings.card_mm)
    else:
        reference = "none"
        ref_mask = None
        scale_px_per_mm = None

    all_refs = valid_rulers + valid_cards
    filtered_shrimp: List[np.ndarray] = []
    for sm in shrimp_raw:
        area = int(np.sum(sm))
        if area == 0:
            continue
        is_lookalike = False
        for rm in all_refs:
            overlap = int(np.sum(sm & rm))
            if overlap / area > 0.5:
                is_lookalike = True
                break
        if not is_lookalike:
            filtered_shrimp.append(sm)

    shrimp_measures = measure(filtered_shrimp, scale_px_per_mm) if filtered_shrimp else []

    return Analysis(
        reference=reference,
        scale_px_per_mm=scale_px_per_mm,
        shrimp=shrimp_measures,
    )


def summarize(
    analysis: Analysis,
    include: Optional[List[int]],
    settings: Settings,
    table: Any,
) -> TrayResult:
    # Build TrayResult from Analysis and optional included shrimp indices
    total = len(analysis.shrimp)
    if include is None:
        chosen = [s.index for s in analysis.shrimp if not s.overlapped]
    else:
        if not isinstance(include, list):
            raise ValueError("include must be a list of ints or None")
        seen = set()
        chosen = []
        for idx in include:
            if isinstance(idx, bool) or not isinstance(idx, int):
                raise ValueError(f"invalid shrimp index: {idx}")
            if idx not in range(total):
                raise ValueError(f"shrimp index out of range: {idx}")
            if idx in seen:
                raise ValueError(f"duplicate shrimp index: {idx}")
            seen.add(idx)
            chosen.append(idx)

    if not analysis.shrimp:
        return TrayResult(
            status="no_shrimp",
            reference=analysis.reference,
            scale_px_per_mm=analysis.scale_px_per_mm,
            shrimp=[],
            n_measured=0,
            n_left_out=0,
            mean_length_mm=None,
            size_per_kg=None,
            notices=[],
            included=[],
        )

    n_measured = len(chosen)
    n_left_out = total - n_measured

    if analysis.scale_px_per_mm is None:
        return TrayResult(
            status="no_reference",
            reference="none",
            scale_px_per_mm=None,
            shrimp=analysis.shrimp,
            n_measured=n_measured,
            n_left_out=n_left_out,
            mean_length_mm=None,
            size_per_kg=None,
            notices=[],
            included=chosen,
        )

    chosen_shrimp = [analysis.shrimp[i] for i in chosen]
    measured_lengths = [
        s.length_mm for s in chosen_shrimp if s.length_mm is not None
    ]
    mean_len = float(np.mean(measured_lengths)) if measured_lengths else None

    if n_measured < settings.min_measured:
        status = "too_few"
        size_per_kg = None
        notices: List[str] = []
    else:
        status = "ok"
        size_per_kg = None
        notices = []
        if table is not None and mean_len is not None:
            size_per_kg = table.per_kg(mean_len)
            if getattr(table, "temporary", False) and size_per_kg is not None:
                notices.append("temporary_table")
                notices.append("rough_estimate")
            elif size_per_kg is None:
                notices.append("outside_table_range")

    return TrayResult(
        status=status,
        reference=analysis.reference,
        scale_px_per_mm=analysis.scale_px_per_mm,
        shrimp=analysis.shrimp,
        n_measured=n_measured,
        n_left_out=n_left_out,
        mean_length_mm=mean_len,
        size_per_kg=size_per_kg,
        notices=notices,
        included=chosen,
    )


def analyze_tray(
    photo: bytes,
    settings: Settings,
    table: Any,
    segmenter: Segmenter,
) -> TrayResult:
    # Analyze tray photo to detect reference, scale, and shrimp lengths
    return summarize(analyze_shrimp(photo, settings, segmenter), None, settings, table)
