# Tests for error table script comparing hand measurements against the pipeline
from datetime import date
from pathlib import Path
import pytest

from shrimp.models import Analysis, Settings, ShrimpMeasure, TrayResult
from shrimp.store import Store
from tests.conftest import FakeSegmenter

from scripts.error_table import (
    ComparisonReport,
    HandRow,
    compare,
    format_sample_list,
    parse_csv,
    render_markdown,
    run_error_table,
)


def _make_measure(idx: int, length_mm: float, overlapped: bool = False) -> ShrimpMeasure:
    # Build a simple ShrimpMeasure helper
    return ShrimpMeasure(
        index=idx,
        length_px=length_mm * 2.0,
        length_mm=length_mm,
        overlapped=overlapped,
        path=[(0.0, 0.0), (1.0, 1.0)],
    )


def test_compare_exact_error_numbers_known_case():
    # Hand 100, 90, 80 against pipeline 104, 90, 76 gives MAE 2.667 mm and 3.00%
    rows = [
        HandRow(sample_id=1, shrimp=1, length_mm=100.0),
        HandRow(sample_id=1, shrimp=2, length_mm=90.0),
        HandRow(sample_id=1, shrimp=3, length_mm=80.0),
    ]
    shrimp = [
        _make_measure(0, 104.0),
        _make_measure(1, 90.0),
        _make_measure(2, 76.0),
    ]
    analysis = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp)
    report = compare(rows, {1: analysis})

    assert report.total_shrimp == 3
    assert abs(report.mean_abs_error_mm - (8.0 / 3.0)) < 1e-4
    assert f"{report.mean_abs_error_mm:.3f}" == "2.667"
    assert abs(report.mean_abs_error_pct - 3.0) < 1e-4
    assert report.largest_error_mm == 4.0

    assert len(report.trays) == 1
    t = report.trays[0]
    assert t.sample_id == 1
    assert t.n_hand == 3
    assert t.n_pipeline_default == 3
    assert t.mean_hand_mm == 90.0
    assert t.mean_pipeline_mm == 90.0
    assert abs(t.mae_mm - (8.0 / 3.0)) < 1e-4
    assert abs(t.mae_pct - 3.0) < 1e-4


def test_compare_wrongly_left_out_shrimp():
    # Hand measured shrimp omitted by pipeline default choice is reported
    rows = [
        HandRow(sample_id=1, shrimp=1, length_mm=100.0),
        HandRow(sample_id=1, shrimp=2, length_mm=90.0),
    ]
    shrimp = [
        _make_measure(0, 102.0, overlapped=False),
        _make_measure(1, 88.0, overlapped=True),
    ]
    analysis = Analysis(reference="ruler", scale_px_per_mm=2.0, shrimp=shrimp)
    report = compare(rows, {1: analysis})

    assert report.wrongly_left_out == [(1, 2)]
    md = render_markdown(report)
    assert "Sample 1, shrimp #2" in md or "sample 1 #2" in md.lower() or "1 #2" in md


def test_compare_skipped_rows_listed():
    # Unknown sample id, number out of range, and length_mm None are counted and listed
    rows = [
        HandRow(sample_id=99, shrimp=1, length_mm=100.0),
        HandRow(sample_id=1, shrimp=5, length_mm=90.0),
        HandRow(sample_id=1, shrimp=1, length_mm=80.0),
    ]
    s1 = _make_measure(0, 0.0)
    s1.length_mm = None
    analysis = Analysis(reference="none", scale_px_per_mm=None, shrimp=[s1])

    report = compare(rows, {1: analysis})
    assert len(report.skipped_rows) == 3

    reasons = [r.reason for r in report.skipped_rows]
    assert any("unknown sample id" in r for r in reasons)
    assert any("out of range" in r for r in reasons)
    assert any("length_mm is None" in r or "no reference" in r for r in reasons)

    md = render_markdown(report)
    assert "Sample 99" in md
    assert "Sample 1, shrimp #5" in md or "shrimp #5" in md
    assert "length_mm is None" in md or "no reference" in md


def test_target_line_met_and_not_met():
    # 5.0% error is MET; 5.1% error is NOT MET
    rows_met = [HandRow(sample_id=1, shrimp=1, length_mm=100.0)]
    analysis_met = Analysis(reference="ruler", scale_px_per_mm=1.0, shrimp=[_make_measure(0, 105.0)])
    report_met = compare(rows_met, {1: analysis_met})
    assert report_met.target_met is True
    md_met = render_markdown(report_met)
    last_line_met = md_met.strip().splitlines()[-1]
    assert last_line_met == "Target: mean error at most 5%: MET (measured 5.0%, n=1)"
    assert "hand measurements by the author, n=1, market shrimp laid flat" in md_met

    rows_not_met = [HandRow(sample_id=1, shrimp=1, length_mm=100.0)]
    analysis_not_met = Analysis(
        reference="ruler",
        scale_px_per_mm=1.0,
        shrimp=[_make_measure(0, 105.1)],
    )
    report_not_met = compare(rows_not_met, {1: analysis_not_met})
    assert report_not_met.target_met is False
    md_not_met = render_markdown(report_not_met)
    last_line_not_met = md_not_met.strip().splitlines()[-1]
    assert last_line_not_met == "Target: mean error at most 5%: NOT MET (measured 5.1%, n=1)"
    assert "hand measurements by the author, n=1, market shrimp laid flat" in md_not_met


def test_length_factor_suggestion_four_and_five_rows():
    # 4 rows reports not enough; 5 rows reports postorbital and pipeline ratios
    rows_4 = [
        HandRow(sample_id=1, shrimp=i, length_mm=100.0, length_postorbital_mm=90.0)
        for i in range(1, 5)
    ]
    shrimp_4 = [_make_measure(i - 1, 100.0) for i in range(1, 5)]
    analysis_4 = Analysis(reference="ruler", scale_px_per_mm=1.0, shrimp=shrimp_4)
    report_4 = compare(rows_4, {1: analysis_4})
    assert report_4.length_factor.has_enough_rows is False
    md_4 = render_markdown(report_4)
    assert "not enough rows" in md_4.lower()

    rows_5 = [
        HandRow(sample_id=1, shrimp=1, length_mm=100.0, length_postorbital_mm=90.0),
        HandRow(sample_id=1, shrimp=2, length_mm=100.0, length_postorbital_mm=92.0),
        HandRow(sample_id=1, shrimp=3, length_mm=100.0, length_postorbital_mm=88.0),
        HandRow(sample_id=1, shrimp=4, length_mm=100.0, length_postorbital_mm=91.0),
        HandRow(sample_id=1, shrimp=5, length_mm=100.0, length_postorbital_mm=89.0),
    ]
    shrimp_5 = [
        _make_measure(0, 101.0),
        _make_measure(1, 99.0),
        _make_measure(2, 100.0),
        _make_measure(3, 102.0),
        _make_measure(4, 98.0),
    ]
    analysis_5 = Analysis(reference="ruler", scale_px_per_mm=1.0, shrimp=shrimp_5)
    report_5 = compare(rows_5, {1: analysis_5})
    assert report_5.length_factor.has_enough_rows is True
    assert report_5.length_factor.mean_postorbital_rostrum_ratio is not None
    assert abs(report_5.length_factor.mean_postorbital_rostrum_ratio - 0.90) < 1e-4
    assert report_5.length_factor.mean_pipeline_hand_ratio is not None
    assert abs(report_5.length_factor.mean_pipeline_hand_ratio - 1.00) < 1e-4
    md_5 = render_markdown(report_5)
    assert "0.900" in md_5
    assert "1.000" in md_5


def test_csv_parser_valid_and_errors():
    # Blank postorbital, spaces in header, and clear line-numbered error on bad numbers
    csv_text = (
        "  sample_id , shrimp , length_mm , length_postorbital_mm  \n"
        " 1 , 1 , 105.5 , \n"
        " 1 , 2 , 92.0 , 85.0 \n"
    )
    rows = parse_csv(csv_text)
    assert len(rows) == 2
    assert rows[0] == HandRow(
        sample_id=1, shrimp=1, length_mm=105.5, length_postorbital_mm=None, line_no=2
    )
    assert rows[1] == HandRow(
        sample_id=1, shrimp=2, length_mm=92.0, length_postorbital_mm=85.0, line_no=3
    )

    bad_csv = (
        "sample_id,shrimp,length_mm,length_postorbital_mm\n"
        "1,1,105.5,\n"
        "1,invalid_shrimp,92.0,\n"
    )
    with pytest.raises(ValueError) as exc:
        parse_csv(bad_csv)
    assert "line 3" in str(exc.value).lower()


def test_list_output_in_memory_store():
    # Only real (non-demo) samples appear in the formatted list
    store = Store(":memory:")
    fake_tray = TrayResult(
        status="ok",
        reference="ruler",
        scale_px_per_mm=2.0,
        shrimp=[],
        n_measured=8,
        n_left_out=2,
        mean_length_mm=85.0,
    )
    store.save_sample(date(2026, 11, 1), fake_tray, photo_path="data/photos/demo.jpg", demo=True)
    sid1 = store.save_sample(
        date(2026, 11, 2), fake_tray, photo_path="data/photos/tray1.jpg", demo=False
    )
    sid2 = store.save_sample(
        date(2026, 11, 3), fake_tray, photo_path="data/photos/tray2.jpg", demo=False
    )

    output = format_sample_list(store)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert len(lines) == 2
    assert "demo.jpg" not in output
    assert f"{sid1} 2026-11-02 8 tray1.jpg" in lines[0]
    assert f"{sid2} 2026-11-03 8 tray2.jpg" in lines[1]
