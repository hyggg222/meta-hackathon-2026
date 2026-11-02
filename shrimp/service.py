# Service orchestration for shrimp measurement analysis, feeds, and settings
from collections import OrderedDict
from datetime import date
import hashlib
import math
from pathlib import Path
import threading
from typing import Any, List, Optional, Tuple, Union

from shrimp.dashboard import build_dashboard
from shrimp.models import Analysis, AnalysisNotFound, Dashboard, FeedEntry, Settings, TrayResult
from shrimp.tray import analyze_shrimp, analyze_tray, summarize


def _is_positive_finite(val: Any) -> bool:
    # Check value is a positive finite number and not a boolean
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(val) and val > 0
    except OverflowError:
        return False


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
        self._analyses: OrderedDict[str, Tuple[Analysis, bytes]] = OrderedDict()
        self._lock = threading.Lock()

    def settings(self) -> Settings:
        # Load persisted settings with default fallbacks
        return self.store.load_settings(Settings())

    def save_settings(self, s: Settings) -> Settings:
        # Validate settings thresholds and save to store
        if not isinstance(s.pond_name, str) or len(s.pond_name) > 100:
            raise ValueError("invalid pond_name")
        limits = {
            "ruler_mm": 10000,
            "card_mm": 10000,
            "stall_mm_per_day": 1000,
            "harvest_per_kg": 100000,
        }
        for f, max_val in limits.items():
            val = getattr(s, f)
            if not _is_positive_finite(val) or val > max_val:
                raise ValueError(f"invalid {f}")
        if (
            isinstance(s.feed_price_vnd, bool)
            or not isinstance(s.feed_price_vnd, int)
            or s.feed_price_vnd < 1
            or s.feed_price_vnd > 1_000_000_000
        ):
            raise ValueError("invalid feed_price_vnd")
        if (
            isinstance(s.min_measured, bool)
            or not isinstance(s.min_measured, int)
            or s.min_measured < 1
            or s.min_measured > 100
        ):
            raise ValueError("invalid min_measured")
        self.store.save_settings(s)
        return self.settings()

    def _persist_sample(self, photo: bytes, day: date, tray: TrayResult) -> None:
        # Persist sample and photo if tray status is ok
        if tray.status == "ok":
            img_path: Optional[Path] = None
            if self.photos_dir is not None:
                sha = hashlib.sha256(photo).hexdigest()[:8]
                img_path = self.photos_dir / f"{day.isoformat()}-{sha}.img"
                img_path.parent.mkdir(parents=True, exist_ok=True)
                img_path.write_bytes(photo)
            try:
                self.store.save_sample(day, tray, photo_path=str(img_path) if img_path is not None else None)
            except Exception:
                if img_path is not None:
                    img_path.unlink(missing_ok=True)
                raise

    def add_sample(self, photo: bytes, day: date) -> TrayResult:
        # Analyze tray photo and persist sample if ok
        tray = analyze_tray(photo, self.settings(), self.table, self.segmenter)
        self._persist_sample(photo, day, tray)
        return tray

    def analyze(self, photo: bytes) -> Tuple[str, TrayResult]:
        # Analyze tray photo and cache analysis in memory
        analysis = analyze_shrimp(photo, self.settings(), self.segmenter)
        analysis_id = hashlib.sha256(photo).hexdigest()[:16]
        tray = summarize(analysis, None, self.settings(), self.table)
        with self._lock:
            if analysis_id in self._analyses:
                del self._analyses[analysis_id]
            self._analyses[analysis_id] = (analysis, photo)
            while len(self._analyses) > 8:
                self._analyses.popitem(last=False)
        return analysis_id, tray

    def summary(self, analysis_id: str, include: Optional[List[int]] = None) -> TrayResult:
        # Summarize cached analysis with chosen shrimp
        with self._lock:
            entry = self._analyses.get(analysis_id)
        if entry is None:
            raise AnalysisNotFound(f"analysis {analysis_id} not found")
        analysis, _ = entry
        return summarize(analysis, include, self.settings(), self.table)

    def save(
        self,
        analysis_id: str,
        include: Optional[List[int]] = None,
        day: Optional[date] = None,
    ) -> TrayResult:
        # Summarize analysis and persist sample if ok
        if day is None:
            day = date.today()
        with self._lock:
            entry = self._analyses.get(analysis_id)
        if entry is None:
            raise AnalysisNotFound(f"analysis {analysis_id} not found")
        analysis, photo = entry
        tray = summarize(analysis, include, self.settings(), self.table)
        self._persist_sample(photo, day, tray)
        return tray

    def add_feed(self, day: date, kg_per_day: float, price_vnd: float) -> None:
        # Validate daily feed parameters and persist entry
        if not _is_positive_finite(kg_per_day) or kg_per_day > 1_000_000:
            raise ValueError("invalid kg_per_day")
        if not _is_positive_finite(price_vnd) or price_vnd > 1_000_000_000:
            raise ValueError("invalid price_vnd")
        self.store.add_feed(FeedEntry(day=day, kg_per_day=float(kg_per_day), price_vnd=int(round(price_vnd))))

    def dashboard(self) -> Dashboard:
        # Build dashboard summary from stored samples and feeds
        return build_dashboard(self.store.samples(), self.store.feeds(), self.settings(), self.table)
