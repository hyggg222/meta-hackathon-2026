# Tests for SAM mask reconstruction
import base64
import unittest.mock
import cv2
import numpy as np
import pytest

from shrimp.models import SegmentationError
from shrimp.sam import make_sam_segmenter, masks_from_records

try:
    from shrimp.sam import upload_part
except ImportError:
    upload_part = None


def test_masks_from_records():
    # Rebuild full-size boolean masks from bounds and base64 raster
    ras = np.array([
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
        [1, 1, 0, 0, 1],
        [0, 0, 1, 1, 0],
    ], dtype=np.uint8)
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    records = [{"id": 1, "bounds": {"top": 10, "bottom": 14, "left": 20, "right": 25}, "b64": b64}]
    masks = masks_from_records(records, 100, 100)
    assert len(masks) == 1
    assert masks[0].shape == (100, 100)
    assert masks[0].dtype == bool
    assert np.array_equal(masks[0][10:14, 20:25], ras > 0)
    assert masks[0][:10, :].sum() == 0
    assert masks[0][14:, :].sum() == 0
    assert masks[0][:, :20].sum() == 0
    assert masks[0][:, 25:].sum() == 0


def test_masks_empty():
    # Return empty list when records are empty
    masks = masks_from_records([], 50, 50)
    assert masks == []


def test_upload_part_png():
    # PNG bytes map to photo.png and image/png
    assert upload_part is not None, "upload_part must be defined"
    photo = b"\x89PNG\r\n\x1a\nfake_png_bytes"
    name, data, mime = upload_part(photo)
    assert name == "photo.png"
    assert data == photo
    assert mime == "image/png"


def test_upload_part_jpeg():
    # JPEG bytes map to photo.jpg and image/jpeg
    assert upload_part is not None, "upload_part must be defined"
    photo = b"\xff\xd8\xff\xe0fake_jpeg_bytes"
    name, data, mime = upload_part(photo)
    assert name == "photo.jpg"
    assert data == photo
    assert mime == "image/jpeg"


def test_upload_part_webp():
    # WebP bytes are decoded and re-encoded to JPEG
    assert upload_part is not None, "upload_part must be defined"
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".webp", img)
    assert ok
    photo = enc.tobytes()
    name, data, mime = upload_part(photo)
    assert name == "photo.jpg"
    assert mime == "image/jpeg"
    assert data.startswith(b"\xff\xd8")


def test_upload_part_garbage():
    # Undecodable bytes raise SegmentationError
    assert upload_part is not None, "upload_part must be defined"
    with pytest.raises(SegmentationError):
        upload_part(b"not_an_image")


def test_sam_upload_png_and_cache(tmp_path):
    # First call uploads PNG as image/png, second prompt reuses uploaded file
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    png_bytes = enc.tobytes()

    post_calls = []

    def fake_post(url, *args, **kwargs):
        post_calls.append((url, kwargs))
        resp = unittest.mock.MagicMock()
        resp.status_code = 200
        if "files" in url:
            resp.json.return_value = {"id": "file_test_id"}
        else:
            resp.iter_lines.return_value = []
        return resp

    def fake_subproc_run(cmd, **kwargs):
        with open(cmd[3], "w", encoding="utf-8") as f:
            f.write("[]")
        proc = unittest.mock.MagicMock()
        proc.returncode = 0
        return proc

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    segmenter = make_sam_segmenter(
        api_key="fake_key",
        decode_script=script,
    )

    with unittest.mock.patch("shrimp.sam.requests.post", side_effect=fake_post), \
         unittest.mock.patch("shrimp.sam.subprocess.run", side_effect=fake_subproc_run):
        res1 = segmenter(png_bytes, "prompt1")
        assert res1 == []
        res2 = segmenter(png_bytes, "prompt2")
        assert res2 == []

    file_uploads = [c for c in post_calls if "files" in c[0]]
    assert len(file_uploads) == 1
    files_kw = file_uploads[0][1].get("files", {})
    assert "file" in files_kw
    name, data, mime = files_kw["file"]
    assert name == "photo.png"
    assert data == png_bytes
    assert mime == "image/png"

    response_calls = [c for c in post_calls if "responses" in c[0]]
    assert len(response_calls) == 2
