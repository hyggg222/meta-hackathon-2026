# Measurement along shrimp body using skeleton graph
import math
from typing import Any, List, Optional, Tuple
import cv2
import networkx as nx
import numpy as np
from skimage.morphology import skeletonize

from shrimp.models import ShrimpMeasure


def largest(mask: np.ndarray) -> np.ndarray:
    # Keep largest connected component of binary mask
    m = mask.astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n <= 1:
        return np.zeros_like(m)
    if n > 2:
        m = (lab == 1 + np.argmax(stats[1:, 4])).astype(np.uint8)
    return m


def centerline(mask: np.ndarray, smooth: int = 7) -> Tuple[float, np.ndarray]:
    # Extract centerline length and smoothed coordinates along body
    m = largest(mask)
    if not np.any(m):
        return 0.0, np.empty((0, 2), float)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    sk = skeletonize(m > 0)
    ys, xs = np.nonzero(sk)
    if len(xs) == 0:
        return 0.0, np.empty((0, 2), float)
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
        k = np.ones(smooth) / smooth
        pad = smooth // 2
        padded = np.vstack([np.repeat(pts[:1], pad, 0), pts, np.repeat(pts[-1:], pad, 0)])
        sm = np.stack(
            [np.convolve(padded[:, 0], k, "valid"), np.convolve(padded[:, 1], k, "valid")],
            1,
        )
        sm[0], sm[-1] = pts[0], pts[-1]
    else:
        sm = pts
    seg = float(np.hypot(*np.diff(sm, axis=0).T).sum()) if len(sm) > 1 else 0.0
    ha = float(dt[int(pts[0][1]), int(pts[0][0])])
    hb = float(dt[int(pts[-1][1]), int(pts[-1][0])])
    return seg + ha + hb, sm


def measure(
    shrimp_masks: List[np.ndarray],
    px_per_mm: Optional[float],
    rule: Any = None,
) -> List[ShrimpMeasure]:
    # Measure shrimp masks along centerline in pixels and millimetres
    results: List[ShrimpMeasure] = []
    for idx, mask in enumerate(shrimp_masks):
        length_px, sm = centerline(mask)
        length_mm = float(length_px / px_per_mm) if px_per_mm is not None else None
        path = [(float(x), float(y)) for x, y in sm]
        results.append(
            ShrimpMeasure(
                index=idx,
                length_px=float(length_px),
                length_mm=length_mm,
                overlapped=False,
                path=path,
            )
        )
    return results
