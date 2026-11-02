# Shrimp farm-gate price lookup, next size class, growth steps and feed break-even
import json
import math
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union


def _is_positive_number(val: object) -> bool:
    # Check value is a positive finite number and not a boolean
    return (
        isinstance(val, (int, float))
        and not isinstance(val, bool)
        and math.isfinite(val)
        and val > 0
    )


class PriceTable:
    # Farm-gate price lookup table by shrimp count per kg

    def __init__(self, source: str, rows: List[Tuple[float, float]]):
        # Initialize price table attributes
        self._source = source
        self._rows = rows

    @property
    def source(self) -> str:
        # Source note for the price table
        return self._source

    @property
    def rows(self) -> List[Tuple[float, float]]:
        # Rows of (size_per_kg, price_vnd)
        return self._rows

    @classmethod
    def load(cls, path: Union[str, Path]) -> "PriceTable":
        # Load price table from json file with validation
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("table root must be a dict")

        for key in ("source", "rows"):
            if key not in data:
                raise ValueError(f"missing key: {key}")

        raw_rows = data["rows"]
        if not isinstance(raw_rows, list) or len(raw_rows) < 2:
            raise ValueError("fewer than 2 rows")

        parsed_rows: List[Tuple[float, float]] = []
        prev_size: Optional[float] = None
        for row in raw_rows:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                raise ValueError("invalid row format")
            raw_size, raw_price = row[0], row[1]
            if not _is_positive_number(raw_size):
                raise ValueError("invalid row size")
            if not _is_positive_number(raw_price):
                raise ValueError("invalid row price")
            size = float(raw_size)
            price = float(raw_price)
            if prev_size is not None and size <= prev_size:
                raise ValueError("sizes not strictly increasing")
            prev_size = size
            parsed_rows.append((size, price))

        return cls(source=str(data["source"]), rows=parsed_rows)

    def price_per_kg(self, size_per_kg: float) -> Optional[float]:
        # Linear interpolation of price between listed sizes; None outside table
        val = float(size_per_kg)
        if val < self._rows[0][0] or val > self._rows[-1][0]:
            return None

        if val == self._rows[0][0]:
            return self._rows[0][1]
        if val == self._rows[-1][0]:
            return self._rows[-1][1]

        for i in range(len(self._rows) - 1):
            x0, y0 = self._rows[i]
            x1, y1 = self._rows[i + 1]
            if x0 <= val <= x1:
                return y0 + (val - x0) * (y1 - y0) / (x1 - x0)

        return None

    def next_class(self, size_per_kg: float) -> Optional[Tuple[int, float]]:
        # Next larger class (smaller count per kg) and its price; None <= 20 or > 100
        val = float(size_per_kg)
        if val <= self._rows[0][0] or val > self._rows[-1][0]:
            return None

        candidates = [(s, p) for s, p in self._rows if s < val]
        if not candidates:
            return None

        best_size, best_price = max(candidates, key=lambda item: item[0])
        return (int(round(best_size)), float(best_price))


DEFAULT_PRICE_TABLE_PATH = (
    Path(__file__).resolve().parent / "price_table.json"
)


def next_class(
    size_per_kg: float, prices: Optional[PriceTable] = None
) -> Optional[Tuple[int, float]]:
    # Module-level next_class lookup with optional price table
    if prices is None:
        prices = PriceTable.load(DEFAULT_PRICE_TABLE_PATH)
    return prices.next_class(size_per_kg)


def weight_g(size_per_kg: float) -> float:
    # Individual shrimp weight in grams from shrimp per kg
    return 1000.0 / float(size_per_kg)


def grams_per_mm(mean_length_mm: float, size_table: Any) -> Optional[float]:
    # Weight gained by one more millimetre from size table
    w1_count = size_table.per_kg(float(mean_length_mm) + 1.0)
    w0_count = size_table.per_kg(float(mean_length_mm))
    if w1_count is None or w0_count is None or w1_count <= 0 or w0_count <= 0:
        return None
    return (1000.0 / w1_count) - (1000.0 / w0_count)


def days_to_next_class(
    mean_length_mm: float,
    size_per_kg: float,
    growth_mm_per_day: float,
    size_table: Any,
    prices: Optional[PriceTable] = None,
) -> Optional[int]:
    # Days needed to reach next size class at measured growth rate
    if growth_mm_per_day is None or growth_mm_per_day <= 0:
        return None

    nc = next_class(size_per_kg, prices)
    if nc is None:
        return None

    next_class_size, _ = nc
    grams_step = grams_per_mm(mean_length_mm, size_table)
    if grams_step is None or grams_step <= 0:
        return None

    target_g = 1000.0 / float(next_class_size)
    cur_g = 1000.0 / float(size_per_kg)
    gain_g = target_g - cur_g
    if gain_g <= 0:
        return None

    adg_g = float(growth_mm_per_day) * grams_step
    return math.ceil(gain_g / adg_g)


def breakeven_growth_mm_per_day(
    mean_length_mm: float,
    size_per_kg: float,
    feed_price_vnd: float,
    price_per_kg_vnd: float,
    ration_pct: float,
    size_table: Any,
) -> Optional[float]:
    """Feed cost only (no power, labour, interest, mortality or price steps)."""
    grams_step = grams_per_mm(mean_length_mm, size_table)
    if grams_step is None or grams_step <= 0:
        return None
    if size_per_kg <= 0 or price_per_kg_vnd <= 0:
        return None

    w = 1000.0 / float(size_per_kg)
    adg_g = w * (float(ration_pct) / 100.0) * float(feed_price_vnd) / float(price_per_kg_vnd)
    return adg_g / grams_step
