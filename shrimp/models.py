from dataclasses import dataclass
from datetime import date
from typing import Optional


# Pond settings and thresholds.
@dataclass
class Settings:
    pond_name: str = ""
    ruler_mm: float = 150.0
    card_mm: float = 85.6
    feed_price_vnd: int = 45000
    stall_mm_per_day: float = 0.33
    harvest_per_kg: float = 50.0
    min_measured: int = 5


# Stored shrimp tray measurement.
@dataclass
class SampleRecord:
    id: int
    day: date
    n_measured: int
    n_left_out: int
    mean_length_mm: Optional[float]
    demo: bool
    photo_path: Optional[str]


# Daily feed record.
@dataclass
class FeedEntry:
    day: date
    kg_per_day: float
    price_vnd: int
