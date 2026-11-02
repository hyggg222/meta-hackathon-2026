# Tests for SAM mask reconstruction
import base64
import concurrent.futures
import hashlib
import json
import os
import time
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
    # JPEG bytes map to photo.jpg, image/jpeg, and decode to the same shape
    assert upload_part is not None, "upload_part must be defined"
    img = np.zeros((20, 30, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".jpg", img)
    assert ok
    photo = enc.tobytes()
    name, data, mime = upload_part(photo)
    assert name == "photo.jpg"
    assert mime == "image/jpeg"
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == img.shape


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


def test_masks_from_records_invalid_raster_length():
    # Raster length mismatch with bounds raises SegmentationError
    rec = [{"id": 1, "bounds": {"top": 0, "bottom": 2, "left": 0, "right": 3}, "b64": base64.b64encode(b"12345").decode("ascii")}]
    with pytest.raises(SegmentationError):
        masks_from_records(rec, 10, 10)


def test_masks_from_records_bounds_out_of_range():
    # Negative bounds or bounds outside height and width raise SegmentationError
    rec_neg = [{"id": 1, "bounds": {"top": -1, "bottom": 2, "left": 0, "right": 2}, "b64": base64.b64encode(b"123456").decode("ascii")}]
    with pytest.raises(SegmentationError):
        masks_from_records(rec_neg, 10, 10)

    rec_out_h = [{"id": 1, "bounds": {"top": 0, "bottom": 12, "left": 0, "right": 2}, "b64": base64.b64encode(b"0" * 24).decode("ascii")}]
    with pytest.raises(SegmentationError):
        masks_from_records(rec_out_h, 10, 10)

    rec_out_w = [{"id": 1, "bounds": {"top": 0, "bottom": 2, "left": 0, "right": 15}, "b64": base64.b64encode(b"0" * 30).decode("ascii")}]
    with pytest.raises(SegmentationError):
        masks_from_records(rec_out_w, 10, 10)


def test_sam_cache_hit_no_post(tmp_path):
    # Good cache file avoids network calls
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    photo = enc.tobytes()
    photo_hash = hashlib.sha256(photo).hexdigest()
    prompt = "shrimp"
    cache_file = tmp_path / f"{photo_hash}_{prompt}.json"

    ras = np.ones((4, 4), dtype=np.uint8)
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    records = [{"id": 1, "bounds": {"top": 1, "bottom": 5, "left": 1, "right": 5}, "b64": b64}]
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(records, f)

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    segmenter = make_sam_segmenter(api_key="k", decode_script=script, cache_dir=str(tmp_path))
    with unittest.mock.patch("shrimp.sam.requests.post") as mock_post:
        masks = segmenter(photo, prompt)
        assert len(masks) == 1
        assert masks[0].shape == (10, 10)
        assert mock_post.call_count == 0


def test_sam_cache_truncated_miss(tmp_path):
    # Truncated cache file is treated as a miss and replaced
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    photo = enc.tobytes()
    photo_hash = hashlib.sha256(photo).hexdigest()
    prompt = "shrimp"
    cache_file = tmp_path / f"{photo_hash}_{prompt}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write('{"id": 1, "bounds":')

    ras = np.ones((2, 2), dtype=np.uint8)
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    records = [{"id": 1, "bounds": {"top": 1, "bottom": 3, "left": 1, "right": 3}, "b64": b64}]

    def fake_post(url, *args, **kwargs):
        resp = unittest.mock.MagicMock()
        resp.status_code = 200
        if "files" in url:
            resp.json.return_value = {"id": "file_test_id"}
        else:
            resp.iter_lines.return_value = []
        return resp

    def fake_subproc_run(cmd, **kwargs):
        with open(cmd[3], "w", encoding="utf-8") as f:
            json.dump(records, f)
        proc = unittest.mock.MagicMock()
        proc.returncode = 0
        return proc

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    segmenter = make_sam_segmenter(api_key="k", decode_script=script, cache_dir=str(tmp_path))
    with unittest.mock.patch("shrimp.sam.requests.post", side_effect=fake_post), \
         unittest.mock.patch("shrimp.sam.subprocess.run", side_effect=fake_subproc_run):
        masks = segmenter(photo, prompt)
        assert len(masks) == 1

    with open(cache_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == records


def test_sam_cache_empty_not_cached(tmp_path):
    # Empty decoded list leaves no cache file
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    photo = enc.tobytes()
    photo_hash = hashlib.sha256(photo).hexdigest()
    prompt = "shrimp"
    cache_file = tmp_path / f"{photo_hash}_{prompt}.json"

    def fake_post(url, *args, **kwargs):
        resp = unittest.mock.MagicMock()
        resp.status_code = 200
        if "files" in url:
            resp.json.return_value = {"id": "file_test_id"}
        else:
            resp.iter_lines.return_value = []
        return resp

    def fake_subproc_run(cmd, **kwargs):
        with open(cmd[3], "w", encoding="utf-8") as f:
            json.dump([], f)
        proc = unittest.mock.MagicMock()
        proc.returncode = 0
        return proc

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    segmenter = make_sam_segmenter(api_key="k", decode_script=script, cache_dir=str(tmp_path))
    with unittest.mock.patch("shrimp.sam.requests.post", side_effect=fake_post), \
         unittest.mock.patch("shrimp.sam.subprocess.run", side_effect=fake_subproc_run):
        masks = segmenter(photo, prompt)
        assert masks == []

    assert not os.path.exists(cache_file)


def test_sam_concurrent_upload_once(tmp_path):
    # Concurrent first calls for same photo upload file exactly once
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    photo = enc.tobytes()

    post_calls = []

    def fake_post(url, *args, **kwargs):
        post_calls.append((url, kwargs))
        if "files" in url:
            time.sleep(0.05)
            resp = unittest.mock.MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"id": "file_concurrent_id"}
            return resp
        resp = unittest.mock.MagicMock()
        resp.status_code = 200
        resp.iter_lines.return_value = []
        return resp

    def fake_subproc_run(cmd, **kwargs):
        with open(cmd[3], "w", encoding="utf-8") as f:
            json.dump([], f)
        proc = unittest.mock.MagicMock()
        proc.returncode = 0
        return proc

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    segmenter = make_sam_segmenter(api_key="k", decode_script=script)

    with unittest.mock.patch("shrimp.sam.requests.post", side_effect=fake_post), \
         unittest.mock.patch("shrimp.sam.subprocess.run", side_effect=fake_subproc_run):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(segmenter, photo, f"prompt_{i}") for i in range(3)]
            for f in futures:
                f.result()

    file_uploads = [c for c in post_calls if "files" in c[0]]
    assert len(file_uploads) == 1


def test_sam_cache_temp_dir_in_cache_dir(tmp_path):
    # When cache_dir is set, temporary directory is created inside it
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    photo = enc.tobytes()

    cache_dir = tmp_path / "custom_cache"
    cache_dir.mkdir()

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    subproc_calls = []

    def fake_post(url, *args, **kwargs):
        resp = unittest.mock.MagicMock()
        resp.status_code = 200
        if "files" in url:
            resp.json.return_value = {"id": "file_id"}
        else:
            resp.iter_lines.return_value = []
        return resp

    def fake_subproc_run(cmd, **kwargs):
        subproc_calls.append(cmd)
        with open(cmd[3], "w", encoding="utf-8") as f:
            f.write("[]")
        proc = unittest.mock.MagicMock()
        proc.returncode = 0
        return proc

    segmenter = make_sam_segmenter(api_key="k", decode_script=script, cache_dir=str(cache_dir))

    with unittest.mock.patch("shrimp.sam.requests.post", side_effect=fake_post), \
         unittest.mock.patch("shrimp.sam.subprocess.run", side_effect=fake_subproc_run):
        segmenter(photo, "shrimp")

    assert len(subproc_calls) == 1
    output_path = subproc_calls[0][3]
    assert os.path.abspath(output_path).startswith(os.path.abspath(str(cache_dir)))


def test_masks_resize_smaller_raster():
    # Resize smaller raster to bounding box dimensions
    ras = np.zeros((10, 20), dtype=np.uint8)
    ras[:5, :] = 255
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    records = [{
        "id": 1,
        "bounds": {"top": 5, "bottom": 25, "left": 10, "right": 50},
        "width": 20,
        "height": 10,
        "b64": b64,
    }]
    masks = masks_from_records(records, 40, 60)
    assert len(masks) == 1
    mask = masks[0]
    assert mask.shape == (40, 60)
    assert np.all(mask[5:15, 10:50])
    assert not np.any(mask[15:25, 10:50])
    assert mask.sum() == 400


def test_masks_matching_dimensions_no_resize():
    # Matching width and height produces same mask without resizing
    ras = np.array([
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
        [1, 1, 0, 0, 1],
        [0, 0, 1, 1, 0],
    ], dtype=np.uint8)
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    bounds = {"top": 10, "bottom": 14, "left": 20, "right": 25}
    rec_plain = [{"id": 1, "bounds": bounds, "b64": b64}]
    rec_dims = [{
        "id": 1,
        "bounds": bounds,
        "width": 5,
        "height": 4,
        "b64": b64,
    }]
    mask_plain = masks_from_records(rec_plain, 50, 50)
    mask_dims = masks_from_records(rec_dims, 50, 50)
    assert np.array_equal(mask_dims[0], mask_plain[0])


def test_masks_dimension_length_mismatch():
    # Raster length mismatch against width and height raises SegmentationError
    b64 = base64.b64encode(b"\x00" * 199).decode("ascii")
    rec = [{
        "id": 1,
        "bounds": {"top": 5, "bottom": 25, "left": 10, "right": 50},
        "width": 20,
        "height": 10,
        "b64": b64,
    }]
    with pytest.raises(SegmentationError):
        masks_from_records(rec, 40, 60)


def test_sam_cache_with_dimensions(tmp_path):
    # Cache records with width and height are read back into matching masks
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    photo = enc.tobytes()
    photo_hash = hashlib.sha256(photo).hexdigest()
    prompt = "shrimp"
    cache_file = tmp_path / f"{photo_hash}_{prompt}.json"

    ras = np.ones((2, 2), dtype=np.uint8)
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    records = [{
        "id": 1,
        "bounds": {"top": 2, "bottom": 6, "left": 2, "right": 6},
        "width": 2,
        "height": 2,
        "b64": b64,
    }]
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(records, f)

    script = str(tmp_path / "decode.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write("// stub")

    segmenter = make_sam_segmenter(
        api_key="k",
        decode_script=script,
        cache_dir=str(tmp_path),
    )
    with unittest.mock.patch("shrimp.sam.requests.post") as mock_post:
        masks = segmenter(photo, prompt)
        assert len(masks) == 1
        assert masks[0].shape == (20, 20)
        assert np.array_equal(masks[0], masks_from_records(records, 20, 20)[0])
        assert mock_post.call_count == 0

