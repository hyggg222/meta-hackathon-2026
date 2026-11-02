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
    touch_px: float = 3.0
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


def centerline(mask: np.ndarray, smooth: int = 7) -> Tuple[float, np.ndarray, float, float]:
    # Extract centerline length, smoothed coordinates, and tip half-widths
    m = largest(mask)
    if not np.any(m):
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
    pts = np.array([(xs[i], ys[i]) for i in paths[b]], float)
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
    return seg + ha + hb, sm, ha, hb


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
        length_px, sm, ha, hb = centerline(mask)
        length_mm = (
            float(length_px / px_per_mm)
            if (px_per_mm is not None and px_per_mm > 0)
            else None
        )
        path = [(float(x), float(y)) for x, y in sm]
        parsed.append((idx, length_px, length_mm, path, sm, ha, hb, mask))

    results: List[ShrimpMeasure] = []
    n_masks = len(parsed)

    for i in range(n_masks):
        idx, length_px, length_mm, path, sm, ha, hb, mask = parsed[i]
        if len(sm) == 0:
            results.append(
                ShrimpMeasure(
                    index=idx,
                    length_px=float(length_px),
                    length_mm=length_mm,
                    overlapped=False,
                    path=path,
                )
            )
            continue

        h, w = mask.shape[:2]
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
            )
        )

    return results
