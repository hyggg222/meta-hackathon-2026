import json
from pathlib import Path
import pytest
from shrimp.sizing import SizeTable
from scripts.make_size_table import build_size_table

REAL_TABLE_PATH = Path(__file__).resolve().parent.parent / "shrimp" / "size_table.json"


# Check lookup on real size table
def test_real_table_lookup():
    table = SizeTable.load(REAL_TABLE_PATH)
    assert table.per_kg(60) == 328
    assert table.per_kg(100) == 71
    assert table.per_kg(140) == 26


# Check linear interpolation between rows
def test_interpolation(tmp_path):
    path = tmp_path / "table.json"
    data = {
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 328], [100, 71], [140, 26]],
    }
    path.write_text(json.dumps(data))
    table = SizeTable.load(path)
    assert table.per_kg(80) == 199.5


# Check boundaries and out of range returns None
def test_range_boundaries(tmp_path):
    path = tmp_path / "table.json"
    data = {
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 328], [100, 71], [140, 26]],
    }
    path.write_text(json.dumps(data))
    table = SizeTable.load(path)
    assert table.per_kg(59.9) is None
    assert table.per_kg(140.1) is None
    assert table.per_kg(60) == 328
    assert table.per_kg(140) == 26
    assert table.min_mm == 60
    assert table.max_mm == 140


# Check temporary and source attributes
def test_table_metadata():
    table = SizeTable.load(REAL_TABLE_PATH)
    assert table.temporary is True
    assert isinstance(table.source, str)
    assert len(table.source.strip()) > 0


# Check replacing table file changes values
def test_table_replacement(tmp_path):
    path = tmp_path / "table.json"
    data1 = {
        "source": "table 1",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 300], [140, 30]],
    }
    path.write_text(json.dumps(data1))
    t1 = SizeTable.load(path)
    assert t1.per_kg(60) == 300
    assert t1.temporary is True

    data2 = {
        "source": "table 2",
        "temporary": False,
        "length_factor": 1.0,
        "rows": [[60, 400], [140, 50]],
    }
    path.write_text(json.dumps(data2))
    t2 = SizeTable.load(path)
    assert t2.per_kg(60) == 400
    assert t2.temporary is False


# Check length factor shifts lookup
def test_length_factor(tmp_path):
    path = tmp_path / "table.json"
    data = {
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.05,
        "rows": [[60, 328], [100, 71], [140, 26]],
    }
    path.write_text(json.dumps(data))
    table = SizeTable.load(path)
    assert table.per_kg(100) == 65.375


# Check bad file with fewer than 2 rows raises ValueError
def test_bad_file_fewer_rows(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 328]],
    }))
    with pytest.raises(ValueError):
        SizeTable.load(path)


# Check bad file with non-increasing lengths raises ValueError
def test_bad_file_not_increasing(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 328], [60, 300]],
    }))
    with pytest.raises(ValueError):
        SizeTable.load(path)

    path.write_text(json.dumps({
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[70, 328], [60, 300]],
    }))
    with pytest.raises(ValueError):
        SizeTable.load(path)


# Check bad file with missing keys raises ValueError
def test_bad_file_missing_keys(tmp_path):
    keys = ["source", "temporary", "length_factor", "rows"]
    base = {
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 328], [100, 71]],
    }
    for k in keys:
        bad = dict(base)
        del bad[k]
        path = tmp_path / f"missing_{k}.json"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            SizeTable.load(path)


# Check generated table equals build_size_table computation
def test_generated_file_matches():
    computed = build_size_table()
    with open(REAL_TABLE_PATH, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk == computed


# Check read-only attributes cannot be mutated
def test_readonly_attributes(tmp_path):
    path = tmp_path / "table.json"
    data = {
        "source": "fixture",
        "temporary": True,
        "length_factor": 1.0,
        "rows": [[60, 328], [100, 71]],
    }
    path.write_text(json.dumps(data))
    table = SizeTable.load(path)
    with pytest.raises(AttributeError):
        table.temporary = False
    with pytest.raises(AttributeError):
        table.source = "new"
    with pytest.raises(AttributeError):
        table.min_mm = 50
    with pytest.raises(AttributeError):
        table.max_mm = 150
