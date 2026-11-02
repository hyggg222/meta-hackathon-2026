# Tests for shrimp pricing, next class, growth and feed break-even
import json
from pathlib import Path
import pytest

from shrimp.pricing import (
    PriceTable,
    breakeven_growth_mm_per_day,
    days_to_next_class,
    grams_per_mm,
    next_class,
    weight_g,
)

REAL_PRICE_TABLE_PATH = (
    Path(__file__).resolve().parent.parent / "shrimp" / "price_table.json"
)


class StubSizeTable:
    # Stub size table with linear weight growth (0.5 g per mm)
    def per_kg(self, length_mm):
        if length_mm is None or length_mm < 76 or length_mm > 150:
            return None
        return 1000.0 / (0.5 * length_mm - 37.5)


def test_price_table_load_and_interpolate():
    # PriceTable loads file, interpolates between sizes and returns None outside range
    table = PriceTable.load(REAL_PRICE_TABLE_PATH)
    assert "Tepbac national median" in table.source

    price_35 = table.price_per_kg(35)
    assert price_35 is not None
    assert abs(price_35 - 143500) <= 1

    assert table.price_per_kg(10) is None
    assert table.price_per_kg(150) is None


def test_price_table_validation(tmp_path):
    # PriceTable rejects unsorted sizes, non-positive price, and missing keys
    base_data = {
        "source": "test",
        "rows": [[20, 200000], [30, 155000], [40, 132000]],
    }

    # Missing key
    for k in ("source", "rows"):
        bad = dict(base_data)
        del bad[k]
        p = tmp_path / f"missing_{k}.json"
        p.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            PriceTable.load(p)

    # Unsorted sizes
    bad_order = {
        "source": "test",
        "rows": [[40, 132000], [30, 155000]],
    }
    p_order = tmp_path / "bad_order.json"
    p_order.write_text(json.dumps(bad_order))
    with pytest.raises(ValueError):
        PriceTable.load(p_order)

    # Equal sizes
    bad_equal = {
        "source": "test",
        "rows": [[30, 155000], [30, 132000]],
    }
    p_equal = tmp_path / "bad_equal.json"
    p_equal.write_text(json.dumps(bad_equal))
    with pytest.raises(ValueError):
        PriceTable.load(p_equal)

    # Non-positive or non-finite price
    for bad_price in (0, -100, float("nan"), float("inf"), "bad", True):
        bad_p_data = {
            "source": "test",
            "rows": [[20, 200000], [30, bad_price]],
        }
        p_price = tmp_path / "bad_price.json"
        p_price.write_text(json.dumps(bad_p_data))
        with pytest.raises(ValueError):
            PriceTable.load(p_price)

    # Non-positive or non-finite size
    for bad_size in (0, -20, float("nan"), float("inf"), "bad", False):
        bad_s_data = {
            "source": "test",
            "rows": [[bad_size, 200000], [30, 155000]],
        }
        p_size = tmp_path / "bad_size.json"
        p_size.write_text(json.dumps(bad_s_data))
        with pytest.raises(ValueError):
            PriceTable.load(p_size)


def test_next_class():
    # next_class finds next larger class and price, None at or below 20 and above 100
    table = PriceTable.load(REAL_PRICE_TABLE_PATH)

    res_36 = next_class(36, table)
    assert res_36 == (30, 155000)

    assert next_class(20, table) is None
    assert next_class(15, table) is None

    res_100 = next_class(100, table)
    assert res_100 == (80, 107000)

    assert next_class(101, table) is None


def test_weight_g():
    # weight_g computes 1000 / size_per_kg
    assert weight_g(40) == 25.0
    assert abs(weight_g(30) - 33.333333) < 1e-4


def test_grams_per_mm():
    # grams_per_mm returns weight gain for one mm from size table
    stub = StubSizeTable()
    res = grams_per_mm(100.0, stub)
    assert res is not None
    assert abs(res - 0.5) < 1e-6

    # None when stub returns None
    assert grams_per_mm(50.0, stub) is None
    assert grams_per_mm(150.0, stub) is None


def test_days_to_next_class():
    # days_to_next_class computes days to gain weight to next size class
    stub = StubSizeTable()
    table = PriceTable.load(REAL_PRICE_TABLE_PATH)

    days = days_to_next_class(115.0, 40.0, 1.0, stub, prices=table)
    assert days == 17

    # Growth 0 or negative gives None
    assert days_to_next_class(115.0, 40.0, 0.0, stub, prices=table) is None
    assert days_to_next_class(115.0, 40.0, -1.0, stub, prices=table) is None

    # No next class gives None
    assert days_to_next_class(115.0, 20.0, 1.0, stub, prices=table) is None

    # Out of range stub gives None
    assert days_to_next_class(50.0, 40.0, 1.0, stub, prices=table) is None


def test_breakeven_growth_mm_per_day():
    # breakeven_growth_mm_per_day calculates break-even daily growth in mm
    stub = StubSizeTable()
    res = breakeven_growth_mm_per_day(115.0, 40.0, 35000, 130000, 1.5, stub)
    assert res is not None
    assert round(res, 4) == 0.2019

    # Docstring specifies feed cost only
    doc = breakeven_growth_mm_per_day.__doc__ or ""
    assert "Feed cost only (no power, labour, interest, mortality or price steps)" in doc

    # Returns None when grams_per_mm is None
    assert breakeven_growth_mm_per_day(50.0, 40.0, 35000, 130000, 1.5, stub) is None
