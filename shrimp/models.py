# Data models and exceptions for shrimp measurement
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, List, Optional, Tuple
import numpy as np


class SegmentationError(Exception):
    # Raised when SAM segmentation or decoding fails
    pass


class AnalysisNotFound(Exception):
    # Raised when analysis ID is unknown or expired
    pass


Segmenter = Callable[[bytes, str], List[np.ndarray]]


@dataclass
class Settings:
    # Pond and calibration settings
    pond_name: str = ""
    ruler_mm: float = 150.0
    card_mm: float = 85.6
    feed_price_vnd: int = 45000
    stall_mm_per_day: float = 0.33
    harvest_per_kg: float = 50.0
    min_measured: int = 5


@dataclass
class ShrimpMeasure:
    # Measured shrimp properties
    index: int
    length_px: float
    length_mm: Optional[float]
    overlapped: bool
    path: List[Tuple[float, float]]
    outline: List[Tuple[float, float]] = field(default_factory=list)


@dataclass(frozen=True)
class Analysis:
    # Intermediate analysis data needed for summary
    reference: str
    scale_px_per_mm: Optional[float]
    shrimp: List[ShrimpMeasure]


@dataclass
class TrayResult:
    # Full analysis result for one tray photo
    status: str
    reference: str
    scale_px_per_mm: Optional[float]
    shrimp: List[ShrimpMeasure]
    n_measured: int
    n_left_out: int
    mean_length_mm: Optional[float]
    size_per_kg: Optional[float] = None
    notices: List[str] = field(default_factory=list)
    included: List[int] = field(default_factory=list)


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
    growth_mm_per_day: Optional[float]


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
    growth_mm_per_day: Optional[float]
    stall_threshold_mm_per_day: float
    harvest_threshold_per_kg: float
    min_measured: int
