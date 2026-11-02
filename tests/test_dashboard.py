from datetime import date
import pytest

from shrimp.dashboard import build_dashboard
from shrimp.models import FeedEntry, SampleRecord, Settings


class FakeTable:
    # Fake size table for tests
    def __init__(self, mapping=None, temporary=True):
        self._mapping = mapping or {}
        self.temporary = temporary

    def per_kg(self, length_mm):
        # Look up size per kg
        return self._mapping.get(length_mm)


def test_empty_input():
    # Empty inputs give empty dashboard
    d = build_dashboard([], [], Settings(), FakeTable())
    assert d.empty is True
    assert d.latest_length_mm is None
    assert d.latest_size_per_kg is None
    assert d.n_latest is None
    assert d.change_length_mm is None
    assert d.change_size_per_kg is None
    assert d.n_previous is None
    assert d.days_between is None
    assert d.stall is None
    assert d.at_harvest is False
    assert d.stall_day_cost_vnd is None
    assert d.chart == []
    assert d.rows == []
    assert d.notices == []


def test_single_sample_no_change_and_no_flag():
    # Single sample shows no change and no stall flag
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    table = FakeTable({80.0: 60.0})
    d = build_dashboard([s1], [], Settings(), table)
    assert d.empty is False
    assert d.latest_length_mm == 80.0
    assert d.latest_size_per_kg == 60.0
    assert d.n_latest == 8
    assert d.change_length_mm is None
    assert d.change_size_per_kg is None
    assert d.n_previous is None
    assert d.days_between is None
    assert d.stall is None
    assert d.at_harvest is False
    assert d.stall_day_cost_vnd is None
    assert d.notices == ["no_feed", "temporary_table", "rough_estimate"]
    assert len(d.rows) == 1
    assert len(d.chart) == 1
    assert d.chart[0].stall is False


def test_two_samples_changes_and_counts():
    # Two samples report length and size changes and counts
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 9, 0, 84.0, False, None)
    table = FakeTable({80.0: 70.0, 84.0: 62.0})
    d = build_dashboard([s1, s2], [], Settings(), table)
    assert d.latest_length_mm == 84.0
    assert d.latest_size_per_kg == 62.0
    assert d.n_latest == 9
    assert d.n_previous == 8
    assert d.days_between == 3
    assert d.change_length_mm == pytest.approx(4.0)
    assert d.change_size_per_kg == pytest.approx(-8.0)
    assert d.stall is False


def test_stall_below_threshold():
    # Growth below stall threshold flags a stall
    s1 = SampleRecord(1, date(2026, 11, 1), 6, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 7, 0, 90.5, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.stall is True


def test_no_stall_at_threshold_and_one_mm_over_three_days():
    # Growth exactly at threshold or 1 mm in 3 days is not a stall
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 91.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.stall is False

    s3 = SampleRecord(3, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s4 = SampleRecord(4, date(2026, 11, 2), 8, 0, 90.33, False, None)
    d2 = build_dashboard([s3, s4], [], Settings(), FakeTable())
    assert d2.stall is False


def test_stall_shrinking_mean():
    # Shrinking mean length is a stall
    s1 = SampleRecord(1, date(2026, 11, 1), 6, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 6, 0, 89.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.stall is True


def test_min_measured_threshold():
    # Samples below minimum measured give stall None and notice
    s1 = SampleRecord(1, date(2026, 11, 1), 4, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 92.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.stall is None
    assert "not_enough_shrimp" in d.notices

    s3 = SampleRecord(3, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s4 = SampleRecord(4, date(2026, 11, 4), 4, 0, 92.0, False, None)
    d2 = build_dashboard([s3, s4], [], Settings(), FakeTable())
    assert d2.stall is None
    assert "not_enough_shrimp" in d2.notices

    s5 = SampleRecord(5, date(2026, 11, 1), 5, 0, 90.0, False, None)
    s6 = SampleRecord(6, date(2026, 11, 3), 5, 0, 92.0, False, None)
    d3 = build_dashboard([s5, s6], [], Settings(), FakeTable())
    assert d3.stall is False
    assert "not_enough_shrimp" not in d3.notices


def test_same_day_samples():
    # Samples on same day give stall None and notice same_day
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 1), 8, 0, 91.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.days_between == 0
    assert d.stall is None
    assert "same_day" in d.notices
    assert d.change_length_mm == pytest.approx(1.0)


def test_harvest_size_threshold():
    # Harvest flag is True at or below threshold and False above
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 110.0, False, None)
    table_at = FakeTable({110.0: 50.0})
    d_at = build_dashboard([s1], [], Settings(harvest_per_kg=50.0), table_at)
    assert d_at.at_harvest is True

    table_above = FakeTable({110.0: 51.0})
    d_above = build_dashboard([s1], [], Settings(harvest_per_kg=50.0), table_above)
    assert d_above.at_harvest is False

    table_below = FakeTable({110.0: 45.0})
    d_below = build_dashboard([s1], [], Settings(harvest_per_kg=50.0), table_below)
    assert d_below.at_harvest is True


def test_feed_cost_calculation():
    # Cost uses latest feed on or before latest sample day
    s1 = SampleRecord(1, date(2026, 11, 4), 8, 0, 90.0, False, None)
    f1 = FeedEntry(date(2026, 11, 1), 100.0, 45000)
    f2 = FeedEntry(date(2026, 11, 3), 100.0, 45000)
    f_after = FeedEntry(date(2026, 11, 5), 200.0, 50000)
    d = build_dashboard([s1], [f1, f_after, f2], Settings(), FakeTable())
    assert d.stall_day_cost_vnd == 4500000
    assert "no_feed" not in d.notices


def test_no_qualifying_feed():
    # Missing qualifying feed gives cost None and notice no_feed
    s1 = SampleRecord(1, date(2026, 11, 4), 8, 0, 90.0, False, None)
    d = build_dashboard([s1], [], Settings(), FakeTable())
    assert d.stall_day_cost_vnd is None
    assert "no_feed" in d.notices

    f_after = FeedEntry(date(2026, 11, 5), 100.0, 45000)
    d2 = build_dashboard([s1], [f_after], Settings(), FakeTable())
    assert d2.stall_day_cost_vnd is None
    assert "no_feed" in d2.notices


def test_outside_table_range():
    # Mean length outside range keeps sample with size None and notice
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 150.0, False, None)
    d = build_dashboard([s1], [], Settings(), FakeTable())
    assert d.latest_length_mm == 150.0
    assert d.latest_size_per_kg is None
    assert "outside_table_range" in d.notices
    assert "temporary_table" not in d.notices
    assert "rough_estimate" not in d.notices
    assert len(d.rows) == 1
    assert d.rows[0].mean_length_mm == 150.0
    assert d.rows[0].size_per_kg is None


def test_temporary_table_notices():
    # Temporary table adds notices only when size is present
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    d_temp = build_dashboard([s1], [], Settings(), FakeTable({90.0: 75.0}, temporary=True))
    assert "temporary_table" in d_temp.notices
    assert "rough_estimate" in d_temp.notices

    d_perm = build_dashboard([s1], [], Settings(), FakeTable({90.0: 75.0}, temporary=False))
    assert "temporary_table" not in d_perm.notices
    assert "rough_estimate" not in d_perm.notices


def test_chart_marks():
    # Chart marks stall on points matching the rule
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 80.5, False, None)
    s3 = SampleRecord(3, date(2026, 11, 7), 8, 0, 83.0, False, None)
    d = build_dashboard([s1, s2, s3], [], Settings(), FakeTable())
    assert len(d.chart) == 3
    assert d.chart[0].stall is False
    assert d.chart[1].stall is True
    assert d.chart[2].stall is False
    assert d.chart[2].stall == (d.stall is True)


def test_inputs_given_in_any_order():
    # Inputs in arbitrary order are sorted by day then id
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 84.0, False, None)
    s3 = SampleRecord(3, date(2026, 11, 7), 8, 0, 86.0, False, None)
    f1 = FeedEntry(date(2026, 11, 2), 80.0, 45000)
    f2 = FeedEntry(date(2026, 11, 5), 100.0, 45000)

    d = build_dashboard([s3, s1, s2], [f2, f1], Settings(), FakeTable())
    assert [r.day for r in d.rows] == [
        date(2026, 11, 1),
        date(2026, 11, 4),
        date(2026, 11, 7),
    ]
    assert d.latest_length_mm == 86.0
    assert d.n_latest == 8
    assert d.n_previous == 8
    assert d.days_between == 3
    assert d.stall_day_cost_vnd == 4500000


def test_notice_order():
    # Notices appear in the required order
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 1), 8, 0, 81.0, False, None)
    table = FakeTable({81.0: 75.0}, temporary=True)
    d = build_dashboard([s1, s2], [], Settings(), table)
    assert d.notices == ["same_day", "no_feed", "temporary_table", "rough_estimate"]


def test_stall_float_guard():
    # Stall calculation uses float guard rather than rounding
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 2), 8, 0, 90.32996, False, None)
    d1 = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d1.stall is True

    s3 = SampleRecord(3, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s4 = SampleRecord(4, date(2026, 11, 4), 8, 0, 90.99, False, None)
    d2 = build_dashboard([s3, s4], [], Settings(), FakeTable())
    assert d2.stall is False

    s5 = SampleRecord(5, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s6 = SampleRecord(6, date(2026, 11, 4), 8, 0, 91.0, False, None)
    d3 = build_dashboard([s5, s6], [], Settings(), FakeTable())
    assert d3.stall is False


def test_chart_marks_real_predecessor():
    # Chart marks pair with real predecessor not previous sample with mean
    s_a = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    s_b = SampleRecord(2, date(2026, 11, 4), 8, 0, None, False, None)
    s_c = SampleRecord(3, date(2026, 11, 7), 8, 0, 80.5, False, None)
    d = build_dashboard([s_a, s_b, s_c], [], Settings(), FakeTable())
    assert len(d.chart) == 2
    assert d.chart[0].stall is False
    assert d.chart[1].stall is False
    assert d.chart[1].stall == (d.stall is True)


def test_feed_entries_same_day_later_wins():
    # Later feed entry in input list wins on same latest day
    s1 = SampleRecord(1, date(2026, 11, 4), 8, 0, 90.0, False, None)
    f1 = FeedEntry(date(2026, 11, 3), 100.0, 40000)
    f2 = FeedEntry(date(2026, 11, 3), 120.0, 50000)
    d1 = build_dashboard([s1], [f1, f2], Settings(), FakeTable())
    assert d1.stall_day_cost_vnd == 6000000

    d2 = build_dashboard([s1], [f2, f1], Settings(), FakeTable())
    assert d2.stall_day_cost_vnd == 4000000

