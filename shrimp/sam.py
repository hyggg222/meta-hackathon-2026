# SAM 3.1 segmentation client with Node mask decoder and disk caching
import base64
import hashlib
import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
import requests

from shrimp.models import Segmenter, SegmentationError


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
        h = bottom - top
        w = right - left
        if h <= 0 or w <= 0:
            continue
        raw_bytes = base64.b64decode(rec["b64"])
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
                except Exception as exc:
                    raise SegmentationError(f"Failed to read cached records: {exc}") from exc

        if photo_hash in file_ids:
            file_id = file_ids[photo_hash]
        else:
            try:
                upload_resp = requests.post(
                    "https://api.meta.ai/v1/files",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("photo.jpg", photo, "image/jpeg")},
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_path = os.path.join(tmp_dir, "stream.raw.txt")
            json_path = (
                os.path.join(cache_dir, f"{photo_hash}_{prompt_slug}.json")
                if cache_dir is not None
                else os.path.join(tmp_dir, "decoded.json")
            )

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
                    ["node", script_path, raw_path, json_path],
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
                with open(json_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception as exc:
                raise SegmentationError(f"Failed to parse decoder output JSON: {exc}") from exc

        return masks_from_records(records, height, width)

    return segment
