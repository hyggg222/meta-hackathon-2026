# Draw measured shrimp on tray photo and encode as JPEG
from typing import List, Tuple
import cv2
import numpy as np

from shrimp.models import TrayResult

# Drawing colours in BGR
COLOR_GREEN = (54, 92, 10)  # #0a5c36
COLOR_RED = (20, 26, 209)  # #d11a14
COLOR_GREY = (107, 107, 107)  # #6b6b6b
COLOR_DARK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)


def _draw_dashed_polygon(
    img: np.ndarray,
    pts: List[Tuple[float, float]],
    color: Tuple[int, int, int],
    thickness: int,
    dash_len: float,
    gap_len: float,
) -> None:
    # Draw dashed outline around polygon vertices
    n = len(pts)
    if n < 2:
        return

    edges = []
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = float(np.hypot(dx, dy))
        if dist > 1e-6:
            edges.append((p1, dist, dx, dy))

    is_dash = True
    dist_left = float(dash_len)

    for p1, dist, dx, dy in edges:
        curr = 0.0
        while curr < dist:
            step = min(dist - curr, dist_left)
            t1 = curr / dist
            t2 = (curr + step) / dist
            if is_dash:
                pt1 = (int(round(p1[0] + dx * t1)), int(round(p1[1] + dy * t1)))
                pt2 = (int(round(p1[0] + dx * t2)), int(round(p1[1] + dy * t2)))
                cv2.line(img, pt1, pt2, color, thickness=thickness)
            curr += step
            dist_left -= step
            if dist_left <= 1e-4:
                is_dash = not is_dash
                dist_left = float(dash_len if is_dash else gap_len)


def render_reply(photo: bytes, tray: TrayResult) -> bytes:
    # Render measured shrimp annotations on photo and return JPEG bytes
    if not isinstance(photo, (bytes, bytearray, memoryview)) or len(photo) == 0:
        raise ValueError("cannot decode photo")

    buf = np.frombuffer(photo, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise ValueError("cannot decode photo")

    h, w = img.shape[:2]
    long_side = max(h, w)

    # Scaling metrics from long side
    line_thick = max(2, int(round(long_side / 700.0)))
    # sized to stay readable when Messenger shows the 1280 px photo at about 400 px
    badge_radius = max(12, int(round(long_side * 0.028)))
    badge_font_scale = max(0.5, badge_radius * 0.034)
    badge_font_thick = max(2, int(round(badge_radius * 0.12)))
    badge_ring = max(2, int(round(badge_radius * 0.12)))

    text_font_scale = max(0.6, 1.0 * (long_side / 700.0))
    text_thin_thick = max(2, int(round(line_thick * 1.5)))
    text_thick_thick = text_thin_thick + max(3, 2 * line_thick)

    dash_len = max(8.0, 4.0 * line_thick)
    gap_len = max(6.0, 3.0 * line_thick)

    included_set = set(tray.included or [])

    # Step 1: fills (translucent green for counted shrimp)
    overlay = img.copy()
    has_fill = False
    for s in tray.shrimp:
        if s.index in included_set and len(s.outline) >= 3:
            pts = np.array(s.outline, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], COLOR_GREEN)
            has_fill = True
    if has_fill:
        cv2.addWeighted(overlay, 0.25, img, 0.75, 0.0, img)

    # Step 2: outlines (solid green for counted, grey dashed for left-out)
    for s in tray.shrimp:
        if len(s.outline) >= 3:
            if s.index in included_set:
                pts = np.array(s.outline, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(img, [pts], isClosed=True, color=COLOR_GREEN, thickness=line_thick)
            else:
                _draw_dashed_polygon(img, s.outline, COLOR_GREY, line_thick, dash_len, gap_len)

    # Step 3: body lines (red for counted, none for left-out)
    for s in tray.shrimp:
        if s.index in included_set and len(s.path) >= 2:
            pts = np.array(s.path, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=False, color=COLOR_RED, thickness=line_thick)

    # Step 4: badges (dark circle for counted, grey circle for left-out)
    for s in tray.shrimp:
        if s.path:
            cx = int(round(s.path[0][0]))
            cy = int(round(s.path[0][1]))
            circle_color = COLOR_DARK if s.index in included_set else COLOR_GREY
            cv2.circle(img, (cx, cy), badge_radius, circle_color, -1)
            cv2.circle(img, (cx, cy), badge_radius, COLOR_WHITE, badge_ring, cv2.LINE_AA)

            text = str(s.index + 1)
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, badge_font_scale, badge_font_thick)
            tx = int(round(cx - tw / 2.0))
            ty = int(round(cy + th / 2.0))
            cv2.putText(
                img,
                text,
                (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                badge_font_scale,
                COLOR_WHITE,
                badge_font_thick,
                cv2.LINE_AA,
            )

    # Step 5: texts (length text for counted shrimp with length_mm)
    for s in tray.shrimp:
        if s.index in included_set and s.length_mm is not None and s.path:
            mid_idx = len(s.path) // 2
            mx, my = s.path[mid_idx]
            length_cm = s.length_mm / 10.0
            label = f"{length_cm:.1f}"
            offset_x = int(round(badge_radius * 0.6))
            offset_y = -int(round(badge_radius * 0.4))
            tx = int(round(mx + offset_x))
            ty = int(round(my + offset_y))
            cv2.putText(
                img,
                label,
                (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                text_font_scale,
                COLOR_DARK,
                text_thick_thick,
                cv2.LINE_AA,
            )
            cv2.putText(
                img,
                label,
                (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                text_font_scale,
                COLOR_WHITE,
                text_thin_thick,
                cv2.LINE_AA,
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
