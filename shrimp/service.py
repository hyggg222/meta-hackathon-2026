# Service orchestration for shrimp measurement analysis, feeds, and settings
from datetime import date
import hashlib
import math
from pathlib import Path
from typing import Any, Optional, Union

from shrimp.dashboard import build_dashboard
from shrimp.models import Dashboard, FeedEntry, Settings, TrayResult
from shrimp.tray import analyze_tray


def _is_positive_finite(val: Any) -> bool:
    # Check value is a positive finite number and not a boolean
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return math.isfinite(val) and val > 0


class Service:
    # Service facade coordinating analysis, storage, and reporting

    def __init__(
        self,
        segmenter: Any,
        store: Any,
        table: Any,
        photos_dir: Optional[Union[str, Path]] = None,
    ):
        # Initialize service dependencies
        self.segmenter = segmenter
        self.store = store
        self.table = table
        self.photos_dir = Path(photos_dir) if photos_dir is not None else None

    def settings(self) -> Settings:
        # Load persisted settings with default fallbacks
        return self.store.load_settings(Settings())

    def save_settings(self, s: Settings) -> Settings:
        # Validate settings thresholds and save to store
        for f in ("ruler_mm", "card_mm", "stall_mm_per_day", "harvest_per_kg", "feed_price_vnd"):
            val = getattr(s, f)
            if not _is_positive_finite(val):
                raise ValueError(f"invalid {f}")
        if isinstance(s.min_measured, bool) or not isinstance(s.min_measured, int) or s.min_measured < 1:
            raise ValueError("invalid min_measured")
        self.store.save_settings(s)
        return self.settings()

    def add_sample(self, photo: bytes, day: date) -> TrayResult:
        # Analyze tray photo and persist sample if ok
        tray = analyze_tray(photo, self.settings(), self.table, self.segmenter)
        if tray.status == "ok":
            photo_path: Optional[str] = None
            if self.photos_dir is not None:
                sha = hashlib.sha256(photo).hexdigest()[:8]
                img_path = self.photos_dir / f"{day.isoformat()}-{sha}.img"
                img_path.parent.mkdir(parents=True, exist_ok=True)
                img_path.write_bytes(photo)
                photo_path = str(img_path)
            self.store.save_sample(day, tray, photo_path=photo_path)
        return tray

    def add_feed(self, day: date, kg_per_day: float, price_vnd: float) -> None:
        # Validate daily feed parameters and persist entry
        if not _is_positive_finite(kg_per_day):
            raise ValueError("invalid kg_per_day")
        if not _is_positive_finite(price_vnd):
            raise ValueError("invalid price_vnd")
        self.store.add_feed(FeedEntry(day=day, kg_per_day=float(kg_per_day), price_vnd=int(round(price_vnd))))

    def dashboard(self) -> Dashboard:
        # Build dashboard summary from stored samples and feeds
        return build_dashboard(self.store.samples(), self.store.feeds(), self.settings(), self.table)
