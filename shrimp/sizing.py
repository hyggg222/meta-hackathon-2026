import json
import math
from pathlib import Path
from typing import List, Optional, Tuple, Union


# Check value is a positive finite number
def _is_positive_number(val: object) -> bool:
    return (
        isinstance(val, (int, float))
        and not isinstance(val, bool)
        and math.isfinite(val)
        and val > 0
    )


class SizeTable:
    # Length to shrimp per kg lookup table

    def __init__(
        self,
        source: str,
        temporary: bool,
        length_factor: float,
        rows: List[Tuple[float, float]],
    ):
        # Initialize table attributes
        self._source = source
        self._temporary = temporary
        self._length_factor = float(length_factor)
        self._rows = rows

    @property
    def source(self) -> str:
        # Source note for the table
        return self._source

    @property
    def temporary(self) -> bool:
        # Flag indicating temporary table
        return self._temporary

    @property
    def min_mm(self) -> float:
        # Minimum supported length in mm
        return self._rows[0][0]

    @property
    def max_mm(self) -> float:
        # Maximum supported length in mm
        return self._rows[-1][0]

    @property
    def length_factor(self) -> float:
        # Multiplier applied to input length
        return self._length_factor

    @classmethod
    def load(cls, path: Union[str, Path]) -> "SizeTable":
        # Load table from json file with validation
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("table root must be a dict")

        for key in ("source", "temporary", "length_factor", "rows"):
            if key not in data:
                raise ValueError(f"missing key: {key}")

        if not isinstance(data["temporary"], bool):
            raise ValueError("temporary must be a bool")

        if not _is_positive_number(data["length_factor"]):
            raise ValueError("invalid length_factor")

        raw_rows = data["rows"]
        if not isinstance(raw_rows, list) or len(raw_rows) < 2:
            raise ValueError("fewer than 2 rows")

        parsed_rows: List[Tuple[float, float]] = []
        prev_len: Optional[float] = None
        for row in raw_rows:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                raise ValueError("invalid row format")
            raw_len, raw_count = row[0], row[1]
            if not _is_positive_number(raw_len):
                raise ValueError("invalid row length")
            if not _is_positive_number(raw_count):
                raise ValueError("invalid row count")
            length = float(raw_len)
            count = float(raw_count)
            if prev_len is not None and length <= prev_len:
                raise ValueError("lengths not strictly increasing")
            prev_len = length
            parsed_rows.append((length, count))

        return cls(
            source=str(data["source"]),
            temporary=data["temporary"],
            length_factor=float(data["length_factor"]),
            rows=parsed_rows,
        )

    def per_kg(self, length_mm: float) -> Optional[float]:
        # Look up shrimp per kg using straight-line interpolation
        lookup_len = float(length_mm) * self._length_factor
        if lookup_len < self._rows[0][0] or lookup_len > self._rows[-1][0]:
            return None

        if lookup_len == self._rows[0][0]:
            return self._rows[0][1]
        if lookup_len == self._rows[-1][0]:
            return self._rows[-1][1]

        for i in range(len(self._rows) - 1):
            x0, y0 = self._rows[i]
            x1, y1 = self._rows[i + 1]
            if x0 <= lookup_len <= x1:
                return y0 + (lookup_len - x0) * (y1 - y0) / (x1 - x0)

        return None
