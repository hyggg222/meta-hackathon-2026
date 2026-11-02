# FastAPI application routes for shrimp analysis and dashboard
from dataclasses import asdict, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import Body, FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from shrimp.models import SegmentationError
from shrimp.service import Service

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _to_json_dict(obj: Any) -> Any:
    # Convert dataclass instance and dates recursively to json-serializable dict
    def _convert(v: Any) -> Any:
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: _convert(val) for k, val in v.items()}
        if isinstance(v, list):
            return [_convert(item) for item in v]
        return v

    return _convert(asdict(obj))


def create_app(service: Service) -> FastAPI:
    # Build and configure FastAPI application with service endpoints
    app = FastAPI(title="Shrimp Measurement")

    @app.post("/api/samples")
    def post_sample(
        photo: UploadFile = File(...),
        day: Optional[str] = Form(None),
    ):
        # Process uploaded tray photo and optional sample date
        content = photo.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"error": "photo too large"})

        if day is not None and day != "":
            try:
                sample_day = date.fromisoformat(day)
            except (ValueError, TypeError):
                return JSONResponse(status_code=422, content={"error": "invalid day"})
        else:
            sample_day = date.today()

        try:
            tray = service.add_sample(content, sample_day)
            return JSONResponse(content=_to_json_dict(tray))
        except SegmentationError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})

    @app.get("/api/dashboard")
    def get_dashboard():
        # Retrieve current dashboard summary
        return JSONResponse(content=_to_json_dict(service.dashboard()))

    @app.post("/api/feed")
    def post_feed(payload: Dict[str, Any] = Body(...)):
        # Record daily feed entry
        if not isinstance(payload, dict):
            return JSONResponse(status_code=422, content={"error": "invalid payload"})
        day_str = payload.get("day")
        if not day_str or not isinstance(day_str, str):
            return JSONResponse(status_code=422, content={"error": "invalid day"})
        try:
            feed_day = date.fromisoformat(day_str)
        except (ValueError, TypeError):
            return JSONResponse(status_code=422, content={"error": "invalid day"})

        kg = payload.get("kg_per_day")
        price = payload.get("price_vnd")
        try:
            service.add_feed(feed_day, kg, price)
            return JSONResponse(content={})
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

    @app.get("/api/settings")
    def get_settings():
        # Retrieve active settings
        return JSONResponse(content=_to_json_dict(service.settings()))

    @app.put("/api/settings")
    def put_settings(payload: Dict[str, Any] = Body(...)):
        # Update settings with validation
        if not isinstance(payload, dict):
            return JSONResponse(status_code=422, content={"error": "invalid payload"})
        try:
            s = replace(service.settings(), **payload)
            saved = service.save_settings(s)
            return JSONResponse(content=_to_json_dict(saved))
        except (ValueError, TypeError) as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

    @app.get("/", response_class=HTMLResponse)
    def index():
        # Serve main capture HTML page
        static_file = Path(__file__).resolve().parent / "static" / "index.html"
        with open(static_file, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)

    return app
