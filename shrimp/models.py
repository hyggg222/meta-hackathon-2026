from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class Settings:
    # Pond settings and threshold constants
    pond_name: str = ""
    ruler_mm: float = 150.0
    card_mm: float = 85.6
    feed_price_vnd: int = 45000
    stall_mm_per_day: float = 0.33
    harvest_per_kg: float = 50.0
    min_measured: int = 5


@dataclass
class SampleRecord:
    # Stored tray sample record
    id: int
    day: date
    n_measured: int
    n_left_out: int
    mean_length_mm: Optional[float]
    demo: bool
    photo_path: Optional[str]


@dataclass
class FeedEntry:
    # Daily feed input record
    day: date
    kg_per_day: float
    price_vnd: int


@dataclass
class ChartPoint:
    # Point on sample length trend chart
    day: date
    mean_length_mm: float
    stall: bool


@dataclass
class SampleRow:
    # Row in dashboard sample history table
    day: date
    n_measured: int
    mean_length_mm: Optional[float]
    size_per_kg: Optional[float]
    demo: bool


@dataclass
class Dashboard:
    # Complete dashboard view model
    empty: bool
    latest_length_mm: Optional[float]
    latest_size_per_kg: Optional[float]
    n_latest: Optional[int]
    change_length_mm: Optional[float]
    change_size_per_kg: Optional[float]
    n_previous: Optional[int]
    days_between: Optional[int]
    stall: Optional[bool]
    at_harvest: bool
    stall_day_cost_vnd: Optional[int]
    chart: List[ChartPoint]
    rows: List[SampleRow]
    notices: List[str]
