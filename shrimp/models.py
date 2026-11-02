# Data models and exceptions for shrimp measurement
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
import numpy as np


class SegmentationError(Exception):
    # Raised when SAM segmentation or decoding fails
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
