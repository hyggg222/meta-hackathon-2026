import cv2
import numpy as np
import pytest

from shrimp.models import ShrimpMeasure, TrayResult
from shrimp.render import place_labels, render_reply


def make_plain_jpeg(width: int = 800, height: int = 600, color: int = 128) -> bytes:
    # Build a plain mid-grey JPEG photo
    img = np.full((height, width, 3), color, dtype=np.uint8)
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    assert ok
    return enc.tobytes()


def make_tray(shrimp=None, included=None) -> TrayResult:
    # Helper to construct a TrayResult for rendering
    shrimp_list = shrimp if shrimp is not None else []
    inc = included if included is not None else [s.index for s in shrimp_list]
    return TrayResult(
        status="ok",
        reference="card",
        scale_px_per_mm=1.0,
        shrimp=shrimp_list,
        n_measured=len(inc),
        n_left_out=len(shrimp_list) - len(inc),
        mean_length_mm=100.0,
        included=inc,
    )


def test_jpeg_format_and_scaling():
    # 4000x3000 input -> long side 1280, aspect ratio kept (±1 px)
    photo_4000 = make_plain_jpeg(width=4000, height=3000)
    shrimp = [
        ShrimpMeasure(
            index=0,
            length_px=200.0,
            length_mm=100.0,
            overlapped=False,
            path=[(500.0, 500.0), (1000.0, 500.0)],
            outline=[(400.0, 400.0), (1100.0, 400.0), (1100.0, 600.0), (400.0, 600.0)],
        )
    ]
    tray = make_tray(shrimp=shrimp, included=[0])
    out_4000 = render_reply(photo_4000, tray)
    assert out_4000.startswith(b"\xff\xd8")
    dec_4000 = cv2.imdecode(np.frombuffer(out_4000, np.uint8), cv2.IMREAD_COLOR)
    assert dec_4000 is not None
    h4, w4 = dec_4000.shape[:2]
    assert max(h4, w4) == 1280
    assert abs(w4 - 1280) <= 1
    assert abs(h4 - 960) <= 1

    # 800x600 input -> not enlarged
    photo_800 = make_plain_jpeg(width=800, height=600)
    out_800 = render_reply(photo_800, tray)
    assert out_800.startswith(b"\xff\xd8")
    dec_800 = cv2.imdecode(np.frombuffer(out_800, np.uint8), cv2.IMREAD_COLOR)
    assert dec_800 is not None
    h8, w8 = dec_800.shape[:2]
    assert (w8, h8) == (800, 600)


def test_counted_vs_left_out_shrimp_fill():
    photo = make_plain_jpeg(width=800, height=600, color=128)
    plain_dec = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)

    # Shrimp 0 is counted, shrimp 1 is left out
    shrimp = [
        ShrimpMeasure(
            index=0,
            length_px=100.0,
            length_mm=80.0,
            overlapped=False,
            path=[(100.0, 150.0), (200.0, 150.0)],
            outline=[(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)],
        ),
        ShrimpMeasure(
            index=1,
            length_px=100.0,
            length_mm=80.0,
            overlapped=False,
            path=[(400.0, 150.0), (500.0, 150.0)],
            outline=[(400.0, 100.0), (500.0, 100.0), (500.0, 200.0), (400.0, 200.0)],
        ),
    ]
    tray = make_tray(shrimp=shrimp, included=[0])
    out = render_reply(photo, tray)
    dec = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert dec is not None

    # Counted shrimp interior patch (away from path and outline)
    counted_patch = dec[115:125, 145:155]
    b, g, r = counted_patch.mean(axis=(0, 1))
    assert g > r + 10
    assert g > b + 5

    # Left-out shrimp interior patch (unchanged within JPEG noise, tolerance 6)
    left_patch = dec[115:125, 445:455]
    plain_patch = plain_dec[115:125, 445:455]
    diff = np.abs(left_patch.mean(axis=(0, 1)) - plain_patch.mean(axis=(0, 1)))
    assert np.max(diff) <= 6.0


def test_body_line_present_counted_absent_left_out():
    photo = make_plain_jpeg(width=800, height=600, color=128)
    shrimp = [
        ShrimpMeasure(
            index=0,
            length_px=100.0,
            length_mm=80.0,
            overlapped=False,
            # long body line: the label sits in the middle (x=300), the left part stays visible
            path=[(100.0, 150.0), (500.0, 150.0)],
            outline=[(100.0, 100.0), (500.0, 100.0), (500.0, 200.0), (100.0, 200.0)],
        ),
        ShrimpMeasure(
            index=1,
            length_px=100.0,
            length_mm=80.0,
            overlapped=False,
            path=[(400.0, 350.0), (500.0, 350.0)],
            outline=[(400.0, 300.0), (500.0, 300.0), (500.0, 400.0), (400.0, 400.0)],
        ),
    ]
    tray = make_tray(shrimp=shrimp, included=[0])
    out = render_reply(photo, tray)
    dec = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert dec is not None

    # Inspect a segment of path between x=120 and x=135, y=149..152
    counted_line_patch = dec[149:152, 120:135]
    # Strongly red pixels: R > 170, G < 60, B < 60
    counted_red = np.sum(
        (counted_line_patch[:, :, 2] > 170)
        & (counted_line_patch[:, :, 1] < 60)
        & (counted_line_patch[:, :, 0] < 60)
    )
    assert counted_red > 0

    # Along left-out shrimp path, strongly red pixels are absent
    left_line_patch = dec[349:352, 420:435]
    left_red = np.sum(
        (left_line_patch[:, :, 2] > 170)
        & (left_line_patch[:, :, 1] < 60)
        & (left_line_patch[:, :, 0] < 60)
    )
    assert left_red == 0


def _two_shrimp():
    # Two counted shrimp side by side; body lines 100 px long, middle at (150, 150) and (450, 150)
    return [
        ShrimpMeasure(
            index=0,
            length_px=100.0,
            length_mm=80.0,
            overlapped=False,
            path=[(100.0, 150.0), (200.0, 150.0)],
            outline=[(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)],
        ),
        ShrimpMeasure(
            index=1,
            length_px=100.0,
            length_mm=80.0,
            overlapped=False,
            path=[(400.0, 150.0), (500.0, 150.0)],
            outline=[(400.0, 100.0), (500.0, 100.0), (500.0, 200.0), (400.0, 200.0)],
        ),
    ]


def _decode(jpeg: bytes) -> np.ndarray:
    dec = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert dec is not None
    return dec


def _darkness_change(photo: bytes, out: bytes, x: int, y: int, half_w: int = 30, half_h: int = 10) -> float:
    # How much darker the output is than the plain photo in a box around (x, y)
    before = _decode(photo)[y - half_h : y + half_h, x - half_w : x + half_w].mean()
    after = _decode(out)[y - half_h : y + half_h, x - half_w : x + half_w].mean()
    return float(before - after)


def _pixel_change(photo: bytes, out: bytes, x: int, y: int, half_w: int = 30, half_h: int = 10) -> float:
    # Mean absolute change of the pixels in a box around (x, y), whatever the colour of the label
    before = _decode(photo)[y - half_h : y + half_h, x - half_w : x + half_w].astype(float)
    after = _decode(out)[y - half_h : y + half_h, x - half_w : x + half_w].astype(float)
    return float(np.abs(after - before).mean())


def test_label_sits_at_the_middle_of_the_body_line():
    # One pill per counted shrimp, at the middle of its body line, not at its start
    photo = make_plain_jpeg(width=800, height=600, color=128)
    tray = make_tray(shrimp=_two_shrimp(), included=[0, 1])
    out = render_reply(photo, tray)
    assert _darkness_change(photo, out, 150, 150) > 25
    assert _darkness_change(photo, out, 450, 150) > 25


def test_left_out_shrimp_has_no_label_in_the_main_view():
    # Left-out shrimp are only faintly outlined: no number pill, nothing at the middle of the line
    photo = make_plain_jpeg(width=800, height=600, color=128)
    tray = make_tray(shrimp=_two_shrimp(), included=[0])
    out = render_reply(photo, tray)
    assert _darkness_change(photo, out, 150, 150) > 25
    assert abs(_darkness_change(photo, out, 450, 150)) < 6


def test_left_out_view_numbers_the_left_out_shrimp_only():
    # show="left_out": the left-out shrimp get a pill, the counted ones are only faintly outlined
    photo = make_plain_jpeg(width=800, height=600, color=128)
    tray = make_tray(shrimp=_two_shrimp(), included=[0])
    out = render_reply(photo, tray, show="left_out")
    assert _pixel_change(photo, out, 150, 150) < 6
    assert _pixel_change(photo, out, 450, 150) > 20


def test_unknown_view_is_refused():
    photo = make_plain_jpeg()
    with pytest.raises(ValueError):
        render_reply(photo, make_tray(shrimp=_two_shrimp()), show="everything")


def _rects_overlap(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _rect(center, size):
    return (center[0] - size[0] / 2, center[1] - size[1] / 2, center[0] + size[0] / 2, center[1] + size[1] / 2)


def test_place_labels_keeps_labels_apart_and_inside_the_image():
    # Two shrimp with the same body line: the second label moves along the line, none overlap
    path = [(100.0, 100.0), (300.0, 100.0)]
    sizes = [(80, 30), (80, 30)]
    centers = place_labels([path, path], sizes, width=400, height=300)
    assert centers[0] == (200, 100)  # the first label takes the middle
    r0, r1 = _rect(centers[0], sizes[0]), _rect(centers[1], sizes[1])
    assert not _rects_overlap(r0, r1)
    for r in (r0, r1):
        assert r[0] >= 0 and r[1] >= 0 and r[2] <= 400 and r[3] <= 300


def test_place_labels_pulls_a_label_back_from_the_image_edge():
    # A body line at the very edge still gets a label that is fully inside the image
    path = [(0.0, 100.0), (10.0, 100.0)]
    centers = place_labels([path], [(80, 30)], width=400, height=300)
    r = _rect(centers[0], (80, 30))
    assert r[0] >= 0 and r[2] <= 400


def test_place_labels_without_a_path_returns_nothing_for_that_shrimp():
    centers = place_labels([[], [(50.0, 50.0), (150.0, 50.0)]], [(60, 20), (60, 20)], width=300, height=200)
    assert centers[0] is None
    assert centers[1] == (100, 50)


def test_undecodable_photo_raises_value_error():
    tray = make_tray()
    with pytest.raises(ValueError, match="cannot decode photo"):
        render_reply(b"not an image", tray)


def test_empty_tray_returns_decodable_jpeg_resized():
    photo_800 = make_plain_jpeg(800, 600)
    tray = make_tray(shrimp=[], included=[])
    out_800 = render_reply(photo_800, tray)
    dec_800 = cv2.imdecode(np.frombuffer(out_800, np.uint8), cv2.IMREAD_COLOR)
    assert dec_800 is not None
    assert dec_800.shape[:2] == (600, 800)

    photo_4000 = make_plain_jpeg(4000, 3000)
    out_4000 = render_reply(photo_4000, tray)
    dec_4000 = cv2.imdecode(np.frombuffer(out_4000, np.uint8), cv2.IMREAD_COLOR)
    assert dec_4000 is not None
    assert dec_4000.shape[:2] == (960, 1280)


def test_length_none_does_not_raise():
    photo = make_plain_jpeg(800, 600)
    shrimp = [
        ShrimpMeasure(
            index=0,
            length_px=100.0,
            length_mm=None,
            overlapped=False,
            path=[(100.0, 100.0), (200.0, 100.0)],
            outline=[(90.0, 90.0), (210.0, 90.0), (210.0, 110.0), (90.0, 110.0)],
        )
    ]
    tray = make_tray(shrimp=shrimp, included=[0])
    out = render_reply(photo, tray)
    assert out.startswith(b"\xff\xd8")


def test_no_shrimp_status():
    photo = make_plain_jpeg(800, 600)
    tray = TrayResult(
        status="no_shrimp",
        reference="card",
        scale_px_per_mm=None,
        shrimp=[],
        n_measured=0,
        n_left_out=0,
        mean_length_mm=None,
        included=[],
    )
    out = render_reply(photo, tray)
    assert out.startswith(b"\xff\xd8")
    dec = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert dec is not None
    assert dec.shape[:2] == (600, 800)
