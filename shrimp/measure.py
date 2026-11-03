# Measurement along shrimp body using skeleton graph
from dataclasses import dataclass
import math
from typing import Any, List, Optional, Tuple
import cv2
import networkx as nx
import numpy as np
from skimage.morphology import skeletonize

from shrimp.models import ShrimpMeasure


@dataclass
class OverlapRule:
    # Rule parameters for shrimp overlap detection
    touch_px: float = 1.0
    edge_px: float = 2.0


def largest(mask: np.ndarray) -> np.ndarray:
    # Keep largest connected component of binary mask
    m = mask.astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n <= 1:
        return np.zeros_like(m)
    if n > 2:
        m = (lab == 1 + np.argmax(stats[1:, 4])).astype(np.uint8)
    return m


def outline_of(mask: np.ndarray) -> List[Tuple[float, float]]:
    # Extract simplified outer contour of mask
    if mask.size == 0 or not np.any(mask):
        return []
    m = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return []
    contour = max(contours, key=cv2.contourArea)
    arc_len = float(cv2.arcLength(contour, True))
    epsilon = max(1.0, 0.002 * arc_len)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return [(float(x), float(y)) for x, y in approx.reshape(-1, 2)]


def longest_side_branch(
    g_or_mask: Any,
    main_path: Optional[List[int]] = None,
) -> Any:
    # Find length of longest side branch from main path to skeleton endpoint
    if main_path is not None:
        if not main_path:
            return 0.0
        main_set = set(main_path)
        endpoints = [
            n
            for n in g_or_mask.nodes
            if g_or_mask.degree(n) == 1 and n not in main_set
        ]
        if not endpoints:
            return 0.0
        dists, _ = nx.multi_source_dijkstra(g_or_mask, main_set)
        return float(
            max((dists[ep] for ep in endpoints if ep in dists), default=0.0)
        )

    _, _, _, _, branch_len, main_len = centerline(g_or_mask, return_branch=True)
    return branch_len, main_len


def centerline(
    mask: np.ndarray, smooth: int = 7, return_branch: bool = False
) -> Any:
    # Extract centerline length, smoothed coordinates, tip half-widths, and optional branch info
    m = largest(mask)
    if not np.any(m):
        if return_branch:
            return 0.0, np.empty((0, 2), float), 0.0, 0.0, 0.0, 0.0
        return 0.0, np.empty((0, 2), float), 0.0, 0.0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)

    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m_skel = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_open)
    m_skel = largest(m_skel)
    if not np.any(m_skel):
        m_skel = m

    sk = skeletonize(m_skel > 0)
    ys, xs = np.nonzero(sk)
    if len(xs) == 0:
        if return_branch:
            return 0.0, np.empty((0, 2), float), 0.0, 0.0, 0.0, 0.0
        return 0.0, np.empty((0, 2), float), 0.0, 0.0
    idx = {(y, x): i for i, (y, x) in enumerate(zip(ys, xs))}
    g = nx.Graph()
    for (y, x), i in idx.items():
        g.add_node(i)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            j = idx.get((y + dy, x + dx))
            if j is not None:
                g.add_edge(i, j, weight=math.hypot(dy, dx))
    comp = max(nx.connected_components(g), key=len)
    start = next(iter(comp))
    d1 = nx.single_source_dijkstra_path_length(g, start)
    a = max(d1, key=d1.get)
    d2, paths = nx.single_source_dijkstra(g, a)
    b = max(d2, key=d2.get)
    main_path = paths[b]
    main_len = float(d2[b])
    branch_len = longest_side_branch(g, main_path)
    pts = np.array([(xs[i], ys[i]) for i in main_path], float)
    if len(pts) > smooth:
        k_smooth = np.ones(smooth) / smooth
        pad = smooth // 2
        padded = np.vstack([np.repeat(pts[:1], pad, 0), pts, np.repeat(pts[-1:], pad, 0)])
        sm = np.stack(
            [np.convolve(padded[:, 0], k_smooth, "valid"), np.convolve(padded[:, 1], k_smooth, "valid")],
            1,
        )
        sm[0], sm[-1] = pts[0], pts[-1]
    else:
        sm = pts
    seg = float(np.hypot(*np.diff(sm, axis=0).T).sum()) if len(sm) > 1 else 0.0
    ha = float(dt[int(pts[0][1]), int(pts[0][0])])
    hb = float(dt[int(pts[-1][1]), int(pts[-1][0])])
    if return_branch:
        return seg + ha + hb, sm, ha, hb, branch_len, main_len
    return seg + ha + hb, sm, ha, hb


# A whole shrimp is slender: length squared over area was 5.7 to 11.7 on three real photos,
# while pieces (hidden by a hand or another shrimp, cut by the frame) were 2.5 to 6.3.
PARTIAL_ELONGATION = 5.5
# A mask that touches the image border over this share of the long side is cut by the frame.
PARTIAL_BORDER_FRACTION = 0.03


def _is_partial(mask: np.ndarray, length_px: float, h: int, w: int) -> bool:
    # True for a piece of a shrimp: too squat for a whole shrimp, or cut by the image frame
    body = largest(mask)
    area = int(body.sum())
    if area == 0 or length_px <= 0:
        return False
    if (length_px * length_px) / area < PARTIAL_ELONGATION:
        return True
    border = int(mask[0, :].sum() + mask[-1, :].sum() + mask[:, 0].sum() + mask[:, -1].sum())
    return border >= PARTIAL_BORDER_FRACTION * max(h, w)


def measure(
    shrimp_masks: List[np.ndarray],
    px_per_mm: Optional[float],
    rule: Any = None,
) -> List[ShrimpMeasure]:
    # Measure shrimp masks along centerline in pixels and millimetres
    active_rule = rule if rule is not None else OverlapRule()
    touch_px = float(active_rule.touch_px)
    edge_px = float(active_rule.edge_px)

    parsed = []
    for idx, mask in enumerate(shrimp_masks):
        length_px, sm, ha, hb, branch_len, main_len = centerline(
            mask, return_branch=True
        )
        length_mm = (
            float(length_px / px_per_mm)
            if (px_per_mm is not None and px_per_mm > 0)
            else None
        )
        path = [(float(x), float(y)) for x, y in sm]
        outline = outline_of(mask)
        branch_ratio = float(branch_len / main_len) if main_len > 0 else 0.0
        parsed.append(
            (idx, length_px, length_mm, path, sm, ha, hb, mask, outline, branch_ratio)
        )

    results: List[ShrimpMeasure] = []
    n_masks = len(parsed)
    lengths = [p[1] for p in parsed]
    max_len = max(lengths) if lengths else 0.0

    for i in range(n_masks):
        idx, length_px, length_mm, path, sm, ha, hb, mask, outline, branch_ratio = parsed[i]
        if len(sm) == 0:
            results.append(
                ShrimpMeasure(
                    index=idx,
                    length_px=float(length_px),
                    length_mm=length_mm,
                    overlapped=False,
                    path=path,
                    outline=outline,
                    merged=False,
                )
            )
            continue

        is_branching = branch_ratio >= 0.35
        other_lens = [
            lengths[j]
            for j in range(n_masks)
            if j != i and lengths[j] >= 0.40 * max_len
        ]
        if len(other_lens) >= 3:
            med_len = float(np.median(other_lens))
            is_much_longer = length_px >= 1.6 * med_len
        else:
            is_much_longer = False

        is_merged = is_branching or is_much_longer

        h, w = mask.shape[:2]
        is_partial = _is_partial(mask, length_px, h, w)
        ends = [(sm[0][0], sm[0][1], ha), (sm[-1][0], sm[-1][1], hb)]
        is_overlapped = False

        for ex, ey, half_w in ends:
            r_touch = half_w + touch_px
            r_edge = half_w + edge_px

            if (
                ex <= r_edge
                or ey <= r_edge
                or (w - 1 - ex) <= r_edge
                or (h - 1 - ey) <= r_edge
            ):
                is_overlapped = True
                break

            r_touch_sq = r_touch * r_touch
            xmin = max(0, int(math.floor(ex - r_touch)))
            xmax = min(w - 1, int(math.ceil(ex + r_touch)))
            ymin = max(0, int(math.floor(ey - r_touch)))
            ymax = min(h - 1, int(math.ceil(ey + r_touch)))

            touch_other = False
            for j in range(n_masks):
                if j == i:
                    continue
                other_sub = parsed[j][7][ymin : ymax + 1, xmin : xmax + 1]
                if np.any(other_sub):
                    ys, xs = np.nonzero(other_sub)
                    dist_sq = (xs + xmin - ex) ** 2 + (ys + ymin - ey) ** 2
                    if np.any(dist_sq <= r_touch_sq):
                        touch_other = True
                        break

            if touch_other:
                is_overlapped = True
                break

        results.append(
            ShrimpMeasure(
                index=idx,
                length_px=float(length_px),
                length_mm=length_mm,
                overlapped=is_overlapped,
                path=path,
                outline=outline,
                merged=is_merged,
                partial=is_partial,
            )
        )

    return results
