# Entry point factory for building the FastAPI app
import os
from pathlib import Path
from fastapi import FastAPI

from shrimp.app import create_app
from shrimp.sam import make_sam_segmenter


def build() -> FastAPI:
    # Build FastAPI app with SAM segmenter configured from environment
    api_key = os.environ.get("META_API_KEY")
    repo_root = Path(__file__).resolve().parent.parent
    env_file = repo_root / ".env"

    if not api_key and env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("META_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip("\"'")
                    break

    if not api_key:
        raise RuntimeError("META_API_KEY is required but not found in environment or .env file")

    decode_script = repo_root / "node" / "decode.mjs"
    cache_dir = repo_root / "data" / "cache"

    segmenter = make_sam_segmenter(
        api_key=api_key,
        decode_script=str(decode_script),
        cache_dir=str(cache_dir),
    )
    return create_app(segmenter)
