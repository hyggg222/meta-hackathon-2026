import cv2
import numpy as np
import pytest

from shrimp.models import ShrimpMeasure, TrayResult
from shrimp.render import render_reply


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
    left_line_patch = dec[149:152, 420:435]
    left_red = np.sum(
        (left_line_patch[:, :, 2] > 170)
        & (left_line_patch[:, :, 1] < 60)
        & (left_line_patch[:, :, 0] < 60)
    )
    assert left_red == 0


def test_badge_drawn_for_shrimp():
    photo = make_plain_jpeg(width=800, height=600, color=128)
    plain_dec = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)

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
    tray = make_tray(shrimp=shrimp, included=[0, 1])
    out = render_reply(photo, tray)
    dec = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert dec is not None

    # Patch around shrimp 1 first point (400, 150) is dark, not grey-mid
    badge_patch = dec[147:154, 397:404]
    plain_patch = plain_dec[147:154, 397:404]
    assert abs(plain_patch.mean() - 128) < 6
    assert badge_patch.mean() < 85


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
