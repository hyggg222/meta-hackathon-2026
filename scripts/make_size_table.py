import json
from pathlib import Path
from typing import Any, Dict, List, Union

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "shrimp" / "size_table.json"


# Build size table dictionary from Chow and Sandifer 1991 formula
def build_size_table() -> Dict[str, Any]:
    rows: List[List[int]] = []
    for length in range(60, 145, 5):
        weight = 1.3669e-5 * (length ** 3.0077)
        rows.append([length, round(1000.0 / weight)])

    return {
        "source": (
            "Fitted from Chow and Sandifer 1991 using W = 1.3669e-5 * L^3.0077 (mm, g) "
            "with expected spread of about 20% in weight."
        ),
        "temporary": True,
        "length_factor": 1.0,
        "rows": rows,
    }


# Write size table json to target path
def write_size_table(path: Union[str, Path] = DEFAULT_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = build_size_table()
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    write_size_table()
