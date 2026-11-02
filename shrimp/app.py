# FastAPI application routes for shrimp analysis
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from shrimp.models import Segmenter, Settings, SegmentationError
from shrimp.tray import analyze_tray


def create_app(segmenter: Segmenter, settings: Optional[Settings] = None) -> FastAPI:
    # Build and configure FastAPI application
    app = FastAPI(title="Shrimp Measurement")
    active_settings = settings if settings is not None else Settings()

    @app.post("/api/analyze")
    async def analyze(photo: UploadFile = File(...)):
        # Analyze uploaded tray photo
        try:
            content = await photo.read()
            tray = analyze_tray(content, active_settings, None, segmenter)
            return JSONResponse(content=asdict(tray))
        except SegmentationError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})

    @app.get("/", response_class=HTMLResponse)
    def index():
        # Serve main capture HTML page
        static_file = Path(__file__).resolve().parent / "static" / "index.html"
        with open(static_file, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)

    return app
