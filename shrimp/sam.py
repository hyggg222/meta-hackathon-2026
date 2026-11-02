# SAM 3.1 segmentation client with Node mask decoder and disk caching
import base64
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import requests

from shrimp.models import Segmenter, SegmentationError


def upload_part(photo: bytes) -> Tuple[str, bytes, str]:
    # Select filename, content, and mime type based on image magic bytes
    if photo.startswith(b"\x89PNG"):
        return ("photo.png", photo, "image/png")
    img = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise SegmentationError("Failed to decode image bytes")
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        raise SegmentationError("Failed to encode image to JPEG")
    return ("photo.jpg", enc.tobytes(), "image/jpeg")


def masks_from_records(
    records: List[Dict[str, Any]],
    height: int,
    width: int,
) -> List[np.ndarray]:
    # Reconstruct boolean masks from bounding boxes and base64 rasters
    masks: List[np.ndarray] = []
    for rec in records:
        bounds = rec.get("bounds", {})
        top = bounds.get("top", 0)
        bottom = bounds.get("bottom", 0)
        left = bounds.get("left", 0)
        right = bounds.get("right", 0)

        if top < 0 or bottom < 0 or left < 0 or right < 0:
            raise SegmentationError(f"Bounds cannot be negative: {bounds}")
        if top > height or bottom > height or left > width or right > width:
            raise SegmentationError(
                f"Bounds {bounds} outside image dimensions {height}x{width}"
            )
        if bottom < top or right < left:
            raise SegmentationError(f"Invalid bounds ordering: {bounds}")

        h = bottom - top
        w = right - left

        rec_w = rec.get("width")
        rec_h = rec.get("height")
        has_dims = (
            isinstance(rec_w, int)
            and not isinstance(rec_w, bool)
            and isinstance(rec_h, int)
            and not isinstance(rec_h, bool)
            and rec_w > 0
            and rec_h > 0
        )

        raw_bytes = base64.b64decode(rec.get("b64", ""))
        if has_dims:
            if len(raw_bytes) != rec_w * rec_h:
                raise SegmentationError(
                    f"Raster length {len(raw_bytes)} does not match mask dimensions {rec_h}*{rec_w}={rec_h * rec_w}"
                )
        elif rec_w is not None or rec_h is not None:
            raise SegmentationError(
                f"Invalid mask dimensions: width={rec_w}, height={rec_h}"
            )
        else:
            if len(raw_bytes) != h * w:
                raise SegmentationError(
                    f"Raster length {len(raw_bytes)} does not match bounds size {h}*{w}={h * w}"
                )

        if h <= 0 or w <= 0:
            continue

        if has_dims:
            ras = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((rec_h, rec_w))
            if (rec_w, rec_h) != (w, h):
                ras = cv2.resize(ras, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            ras = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w))

        mask = np.zeros((height, width), dtype=bool)
        mask[top:bottom, left:right] = ras > 0
        masks.append(mask)
    return masks


def make_sam_segmenter(
    api_key: str,
    decode_script: str,
    cache_dir: Optional[str] = None,
) -> Segmenter:
    # Build a segmenter function backed by SAM 3.1 API and Node decoder
    file_ids: Dict[str, str] = {}
    upload_lock = threading.Lock()
    script_path = os.path.abspath(decode_script)
    script_dir = os.path.dirname(script_path)

    if cache_dir is not None:
        os.makedirs(cache_dir, exist_ok=True)

    def segment(photo: bytes, prompt: str) -> List[np.ndarray]:
        # Segment objects from photo bytes given a text prompt
        img = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise SegmentationError("Failed to decode image bytes")
        height, width = img.shape[:2]

        photo_hash = hashlib.sha256(photo).hexdigest()
        prompt_slug = "".join(c if c.isalnum() else "_" for c in prompt.strip())

        if cache_dir is not None:
            cache_file = os.path.join(cache_dir, f"{photo_hash}_{prompt_slug}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_records = json.load(f)
                    return masks_from_records(cached_records, height, width)
                except Exception:
                    pass

        with upload_lock:
            if photo_hash in file_ids:
                file_id = file_ids[photo_hash]
            else:
                try:
                    part = upload_part(photo)
                    upload_resp = requests.post(
                        "https://api.meta.ai/v1/files",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"file": part},
                        data={"purpose": "user_data"},
                        timeout=60,
                    )
                    if upload_resp.status_code != 200:
                        raise SegmentationError(
                            f"Photo upload failed with status code {upload_resp.status_code}"
                        )
                    file_id = upload_resp.json().get("id")
                    if not file_id:
                        raise SegmentationError("Photo upload did not return a file id")
                    file_ids[photo_hash] = file_id
                except SegmentationError:
                    raise
                except Exception as exc:
                    raise SegmentationError(f"Photo upload request failed: {exc}") from exc

        try:
            resp = requests.post(
                "https://api.meta.ai/v1/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "sam-3.1",
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {"type": "input_image", "file_id": file_id},
                            ],
                        }
                    ],
                    "stream": True,
                    "metadata": {"mask_encoding": "one_bit"},
                },
                stream=True,
                timeout=60,
            )
            if resp.status_code != 200:
                raise SegmentationError(
                    f"SAM API request failed with status code {resp.status_code}"
                )
        except SegmentationError:
            raise
        except Exception as exc:
            raise SegmentationError(f"SAM API connection failed: {exc}") from exc

        tmp_kwargs = {"dir": cache_dir} if cache_dir is not None else {}
        with tempfile.TemporaryDirectory(**tmp_kwargs) as tmp_dir:
            raw_path = os.path.join(tmp_dir, "stream.raw.txt")
            tmp_json_path = os.path.join(tmp_dir, "decoded.json")

            try:
                with open(raw_path, "w", encoding="utf-8") as f:
                    for line in resp.iter_lines():
                        if line:
                            f.write(line.decode("utf-8") + "\n")
            except Exception as exc:
                raise SegmentationError(f"Failed to read streaming response: {exc}") from exc

            env = dict(os.environ)
            if "NODE_PATH" not in env:
                node_modules = os.path.join(script_dir, "node_modules")
                if os.path.exists(node_modules):
                    env["NODE_PATH"] = node_modules

            try:
                proc = subprocess.run(
                    ["node", script_path, raw_path, tmp_json_path],
                    cwd=script_dir,
                    env=env,
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
                if proc.returncode != 0:
                    err_msg = proc.stderr.decode("utf-8", errors="replace").strip()
                    raise SegmentationError(f"Node decoder failed: {err_msg}")
            except subprocess.TimeoutExpired as exc:
                raise SegmentationError("Node decoder timed out") from exc
            except SegmentationError:
                raise
            except Exception as exc:
                raise SegmentationError(f"Failed to run node decoder: {exc}") from exc

            try:
                with open(tmp_json_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception as exc:
                raise SegmentationError(f"Failed to parse decoder output JSON: {exc}") from exc

            if cache_dir is not None:
                if records:
                    os.replace(tmp_json_path, cache_file)
                elif os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                    except OSError:
                        pass

        return masks_from_records(records, height, width)

    return segment
