# Draw measured shrimp on tray photo and encode as JPEG
from typing import List, Optional, Sequence, Tuple
import cv2
import numpy as np

from shrimp.models import ShrimpMeasure, TrayResult

# Drawing colours in BGR
COLOR_GREEN = (54, 92, 10)  # #0a5c36 counted shrimp
COLOR_AMBER = (0, 119, 199)  # #c77700 left-out shrimp in the left-out view
COLOR_RED = (20, 26, 209)  # #d11a14 body line
COLOR_FAINT = (200, 200, 200)  # the shrimp that are not the point of this view
COLOR_DARK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)

VIEWS = ("counted", "left_out")
# Places along the body line to try for a label, middle first
_FRACTIONS = (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9)
_LABEL_GAP = 4


def _point_along(path: Sequence[Tuple[float, float]], fraction: float) -> Tuple[float, float]:
    # Point at the given fraction of the length of a polyline
    if len(path) == 1:
        return path[0]
    seg = [float(np.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])) for i in range(len(path) - 1)]
    total = sum(seg)
    if total <= 0:
        return path[0]
    target = fraction * total
    for i, s in enumerate(seg):
        if target <= s or i == len(seg) - 1:
            t = 0.0 if s <= 0 else min(1.0, target / s)
            return (path[i][0] + (path[i + 1][0] - path[i][0]) * t, path[i][1] + (path[i + 1][1] - path[i][1]) * t)
        target -= s
    return path[-1]


def _rect(centre: Tuple[int, int], size: Tuple[int, int]) -> Tuple[float, float, float, float]:
    return (
        centre[0] - size[0] / 2.0,
        centre[1] - size[1] / 2.0,
        centre[0] + size[0] / 2.0,
        centre[1] + size[1] / 2.0,
    )


def _overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], gap: float) -> bool:
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def place_labels(
    paths: Sequence[Sequence[Tuple[float, float]]],
    sizes: Sequence[Tuple[int, int]],
    width: int,
    height: int,
) -> List[Optional[Tuple[int, int]]]:
    # Centre for each label: on its body line (middle first), never over a label placed before,
    # always inside the image. A shrimp with no body line gets None.
    placed: List[Tuple[float, float, float, float]] = []
    centres: List[Optional[Tuple[int, int]]] = []
    for path, size in zip(paths, sizes):
        if not path:
            centres.append(None)
            continue
        half_w, half_h = size[0] / 2.0, size[1] / 2.0
        candidates: List[Tuple[int, int]] = []
        for dy in (0, -(size[1] + _LABEL_GAP), size[1] + _LABEL_GAP):
            for f in _FRACTIONS:
                x, y = _point_along(path, f)
                candidates.append((int(round(x)), int(round(y + dy))))

        def inside(c: Tuple[int, int]) -> bool:
            return c[0] - half_w >= 0 and c[0] + half_w <= width and c[1] - half_h >= 0 and c[1] + half_h <= height

        chosen: Optional[Tuple[int, int]] = None
        for c in candidates:
            if inside(c) and not any(_overlap(_rect(c, size), p, _LABEL_GAP) for p in placed):
                chosen = c
                break
        if chosen is None:
            # no free place: keep the middle, pulled back inside the image
            x0, y0 = candidates[0]
            chosen = (
                int(min(max(x0, half_w), max(half_w, width - half_w))),
                int(min(max(y0, half_h), max(half_h, height - half_h))),
            )
        placed.append(_rect(chosen, size))
        centres.append(chosen)
    return centres


def _capsule(img: np.ndarray, x0: int, x1: int, cy: int, r: int, color: Tuple[int, int, int]) -> None:
    # Filled capsule: a rectangle with a half circle on each end
    cv2.rectangle(img, (x0, cy - r), (x1, cy + r), color, -1)
    cv2.circle(img, (x0, cy), r, color, -1, cv2.LINE_AA)
    cv2.circle(img, (x1, cy), r, color, -1, cv2.LINE_AA)


def _label_text(s: ShrimpMeasure) -> Tuple[str, Optional[str]]:
    # Shrimp number and, when known, its length in centimetres
    length = None if s.length_mm is None else f"{s.length_mm / 10.0:.1f}"
    return str(s.index + 1), length


def render_reply(photo: bytes, tray: TrayResult, show: str = "counted") -> bytes:
    # Render measured shrimp on the photo and return JPEG bytes.
    # show="counted": counted shrimp outlined, with body line, number and length; the others only faint.
    # show="left_out": the left-out shrimp are outlined and numbered so the farmer can add one.
    if show not in VIEWS:
        raise ValueError(f"unknown view: {show}")
    if not isinstance(photo, (bytes, bytearray, memoryview)) or len(photo) == 0:
        raise ValueError("cannot decode photo")

    buf = np.frombuffer(photo, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise ValueError("cannot decode photo")

    h, w = img.shape[:2]
    long_side = max(h, w)

    # Sizes follow the long side, so they look the same after the final resize. Readable when
    # Messenger shows the 1280 px photo at about 400 px.
    line_thick = max(2, int(round(long_side / 700.0)))
    faint_thick = max(1, line_thick // 2)
    pill_h = max(26, int(round(long_side * 0.04)))
    r = pill_h // 2
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, pill_h * 0.027)
    font_thick = max(2, int(round(pill_h * 0.07)))
    ring = max(2, int(round(pill_h * 0.07)))
    gap = max(6, int(round(pill_h * 0.3)))

    included_set = set(tray.included or [])
    if show == "counted":
        focus = [s for s in tray.shrimp if s.index in included_set]
        others = [s for s in tray.shrimp if s.index not in included_set]
        focus_color = COLOR_GREEN
    else:
        focus = [s for s in tray.shrimp if s.index not in included_set]
        others = [s for s in tray.shrimp if s.index in included_set]
        focus_color = COLOR_AMBER

    # Step 1: translucent fill of the shrimp this view is about
    overlay = img.copy()
    has_fill = False
    for s in focus:
        if len(s.outline) >= 3:
            pts = np.array(s.outline, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], focus_color)
            has_fill = True
    if has_fill:
        cv2.addWeighted(overlay, 0.25, img, 0.75, 0.0, img)

    # Step 2: outlines: faint for the others, solid for the focus
    for s in others:
        if len(s.outline) >= 3:
            pts = np.array(s.outline, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=True, color=COLOR_FAINT, thickness=faint_thick, lineType=cv2.LINE_AA)
    for s in focus:
        if len(s.outline) >= 3:
            pts = np.array(s.outline, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=True, color=focus_color, thickness=line_thick, lineType=cv2.LINE_AA)

    # Step 3: body lines of the focus (red)
    if show == "counted":
        for s in focus:
            if len(s.path) >= 2:
                pts = np.array(s.path, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(img, [pts], isClosed=False, color=COLOR_RED, thickness=line_thick, lineType=cv2.LINE_AA)

    # Step 4: one label per focus shrimp: a capsule with the number in a circle and the length beside it
    texts = [_label_text(s) for s in focus]
    sizes: List[Tuple[int, int]] = []
    for number, length in texts:
        if length is None:
            sizes.append((pill_h, pill_h))
        else:
            (tw, _), _ = cv2.getTextSize(length, font, font_scale, font_thick)
            sizes.append((pill_h + gap + tw + gap, pill_h))
    centres = place_labels([s.path for s in focus], sizes, w, h)
    for s, (number, length), size, centre in zip(focus, texts, sizes, centres):
        if centre is None:
            continue
        cx, cy = centre
        left = cx - size[0] // 2 + r
        right = cx + size[0] // 2 - r
        _capsule(img, left, right, cy, r + ring, COLOR_WHITE)
        _capsule(img, left, right, cy, r, COLOR_DARK if show == "counted" else COLOR_AMBER)
        (nw, nh), _ = cv2.getTextSize(number, font, font_scale, font_thick)
        cv2.putText(
            img, number, (int(left - nw / 2.0), int(cy + nh / 2.0)), font, font_scale, COLOR_WHITE, font_thick, cv2.LINE_AA
        )
        if length is not None:
            # a thin divider so a two-digit number never runs into the length
            divider_x = left + r + gap // 2
            cv2.line(img, (divider_x, cy - r + 2 * ring), (divider_x, cy + r - 2 * ring), COLOR_WHITE, max(1, ring // 2))
            cv2.putText(
                img, length, (int(left + r + gap), int(cy + nh / 2.0)), font, font_scale, COLOR_WHITE, font_thick, cv2.LINE_AA
            )

    # Resize so long side is at most 1280 px (no upscaling)
    if long_side > 1280:
        scale = 1280.0 / long_side
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise ValueError("cannot encode photo")
    return enc.tobytes()
