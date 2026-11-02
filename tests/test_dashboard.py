import math
from datetime import date
import pytest

from shrimp.dashboard import (
    TREND_MIN_SPAN_DAYS,
    TREND_SAMPLES,
    _trend,
    build_dashboard,
)
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
    assert d.growth_se_mm_per_day is None
    assert d.stall_unclear is False
    assert d.days_needed is None
    assert d.shrimp_needed is None
    assert d.trend_samples is None
    assert d.trend_span_days is None


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
    s_d = SampleRecord(4, date(2026, 11, 10), 8, 0, 85.0, False, None)
    d = build_dashboard([s_a, s_b, s_c, s_d], [], Settings(), FakeTable())
    assert len(d.chart) == 3
    assert d.chart[0].stall is False
    assert d.chart[1].stall is False
    assert d.chart[2].stall is False


def test_feed_entries_same_day_later_wins():
    # Later feed entry in input list wins on same latest day
    s1 = SampleRecord(1, date(2026, 11, 4), 8, 0, 90.0, False, None)
    f1 = FeedEntry(date(2026, 11, 3), 100.0, 40000)
    f2 = FeedEntry(date(2026, 11, 3), 120.0, 50000)
    d1 = build_dashboard([s1], [f1, f2], Settings(), FakeTable())
    assert d1.stall_day_cost_vnd == 6000000

    d2 = build_dashboard([s1], [f2, f1], Settings(), FakeTable())
    assert d2.stall_day_cost_vnd == 4000000


def test_growth_mm_per_day():
    # Two samples 3 days apart calculate daily growth rate
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 91.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.growth_mm_per_day == pytest.approx(1 / 3)


def test_growth_same_day():
    # Same day samples give growth None
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 1), 8, 0, 91.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.growth_mm_per_day is None


def test_growth_single_sample():
    # Single sample gives growth None
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    d = build_dashboard([s1], [], Settings(), FakeTable())
    assert d.growth_mm_per_day is None


def test_growth_missing_mean():
    # Sample with no mean length gives growth None
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, None, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 91.0, False, None)
    d1 = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d1.growth_mm_per_day is None

    s3 = SampleRecord(3, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s4 = SampleRecord(4, date(2026, 11, 4), 8, 0, None, False, None)
    d2 = build_dashboard([s3, s4], [], Settings(), FakeTable())
    assert d2.growth_mm_per_day is None


def test_thresholds_copied():
    # Settings thresholds are copied to normal dashboard
    settings = Settings(stall_mm_per_day=0.5, harvest_per_kg=60.0, min_measured=7)
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    d = build_dashboard([s1], [], settings, FakeTable())
    assert d.stall_threshold_mm_per_day == 0.5
    assert d.harvest_threshold_per_kg == 60.0
    assert d.min_measured == 7


def test_empty_thresholds_copied():
    # Settings thresholds are copied to empty dashboard
    settings = Settings(stall_mm_per_day=0.5, harvest_per_kg=60.0, min_measured=7)
    d = build_dashboard([], [], settings, FakeTable())
    assert d.empty is True
    assert d.growth_mm_per_day is None
    assert d.stall_threshold_mm_per_day == 0.5
    assert d.harvest_threshold_per_kg == 60.0
    assert d.min_measured == 7


def test_sample_row_growth():
    # Calculate daily growth per sample row
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 91.0, False, None)
    s3 = SampleRecord(3, date(2026, 11, 5), 8, 0, 93.0, False, None)
    d = build_dashboard([s3, s1, s2], [], Settings(), FakeTable())
    row_by_day = {r.day: r for r in d.rows}
    assert row_by_day[date(2026, 11, 1)].growth_mm_per_day is None
    assert row_by_day[date(2026, 11, 4)].growth_mm_per_day == pytest.approx(1 / 3)
    assert row_by_day[date(2026, 11, 5)].growth_mm_per_day == pytest.approx(2.0)


def test_sample_row_growth_same_day():
    # Same day sample row gives growth None
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 1), 8, 0, 91.0, False, None)
    d = build_dashboard([s1, s2], [], Settings(), FakeTable())
    assert d.rows[0].growth_mm_per_day is None
    assert d.rows[1].growth_mm_per_day is None


def test_sample_row_growth_missing_mean():
    # Missing mean gives growth None for row and follower
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, None, False, None)
    s3 = SampleRecord(3, date(2026, 11, 7), 8, 0, 93.0, False, None)
    d = build_dashboard([s1, s2, s3], [], Settings(), FakeTable())
    row_by_day = {r.day: r for r in d.rows}
    assert row_by_day[date(2026, 11, 4)].growth_mm_per_day is None
    assert row_by_day[date(2026, 11, 7)].growth_mm_per_day is None


def test_sample_row_growth_single_sample():
    # Single sample row gives growth None
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 90.0, False, None)
    d = build_dashboard([s1], [], Settings(), FakeTable())
    assert len(d.rows) == 1
    assert d.rows[0].growth_mm_per_day is None


def test_sample_row_growth_matches_dashboard():
    # Row growth of latest equals dashboard growth
    s1 = SampleRecord(1, date(2026, 11, 1), 8, 0, 80.0, False, None)
    s2 = SampleRecord(2, date(2026, 11, 4), 8, 0, 85.0, False, None)
    s3 = SampleRecord(3, date(2026, 11, 8), 8, 0, 89.0, False, None)
    d = build_dashboard([s1, s2, s3], [], Settings(), FakeTable())
    assert d.rows[-1].growth_mm_per_day == d.growth_mm_per_day
    assert d.growth_mm_per_day == pytest.approx(1.0)


def test_z_confident_constant():
    # Z_CONFIDENT constant is 1.645
    from shrimp.dashboard import Z_CONFIDENT

    assert Z_CONFIDENT == 1.645


def test_dashboard_spread_unclear_slow_growth():
    # Days 3 apart, means 90.0 and 91.0, sd 10.0 and n 10 each: stall unclear
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    s1 = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=10.0)
    s2 = SampleRecord(2, date(2026, 11, 4), 10, 0, 91.0, False, None, sd_length_mm=10.0)
    d = build_dashboard([s1, s2], [], settings, FakeTable())
    assert d.stall is None
    assert d.stall_unclear is True
    assert d.growth_se_mm_per_day == pytest.approx(1.4907, abs=1e-3)
    assert d.days_needed == 23
    assert d.shrimp_needed == 553


def test_dashboard_spread_confident_stall():
    # Days 10 apart, means 90.0 and 90.0, sd 1.0, n 20 each: confident stall
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    s1 = SampleRecord(1, date(2026, 11, 1), 20, 0, 90.0, False, None, sd_length_mm=1.0)
    s2 = SampleRecord(2, date(2026, 11, 11), 20, 0, 90.0, False, None, sd_length_mm=1.0)
    d = build_dashboard([s1, s2], [], settings, FakeTable())
    assert d.stall is True
    assert d.stall_unclear is False
    assert d.growth_se_mm_per_day is not None
    assert d.days_needed is None
    assert d.shrimp_needed is None


def test_dashboard_spread_confident_not_stall():
    # Days 10 apart, means 90.0 and 100.0, sd 1.0, n 20 each: confident not stall
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    s1 = SampleRecord(1, date(2026, 11, 1), 20, 0, 90.0, False, None, sd_length_mm=1.0)
    s2 = SampleRecord(2, date(2026, 11, 11), 20, 0, 100.0, False, None, sd_length_mm=1.0)
    d = build_dashboard([s1, s2], [], settings, FakeTable())
    assert d.stall is False
    assert d.stall_unclear is False
    assert d.growth_se_mm_per_day is not None
    assert d.days_needed is None
    assert d.shrimp_needed is None


def test_dashboard_old_rule_without_sd_length():
    # The same numbers without sd_length_mm behave exactly as before
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    # Means 90.0 and 91.0 over 3 days is not a stall (0.333 is not below 0.33)
    s1 = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=None)
    s2 = SampleRecord(2, date(2026, 11, 4), 10, 0, 91.0, False, None, sd_length_mm=None)
    d1 = build_dashboard([s1, s2], [], settings, FakeTable())
    assert d1.stall is False
    assert d1.stall_unclear is False
    assert d1.growth_se_mm_per_day is None
    assert d1.days_needed is None
    assert d1.shrimp_needed is None

    # Means 90.0 and 90.5 over 3 days is a stall
    s3 = SampleRecord(3, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=None)
    s4 = SampleRecord(4, date(2026, 11, 4), 10, 0, 90.5, False, None, sd_length_mm=None)
    d2 = build_dashboard([s3, s4], [], settings, FakeTable())
    assert d2.stall is True
    assert d2.stall_unclear is False
    assert d2.growth_se_mm_per_day is None
    assert d2.days_needed is None
    assert d2.shrimp_needed is None


def test_dashboard_spread_cannot_tell_cases():
    # Same day, N below min_measured and a missing mean give stall None, stall_unclear False even with sd
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)

    # Same day
    s1 = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=10.0)
    s2 = SampleRecord(2, date(2026, 11, 1), 10, 0, 91.0, False, None, sd_length_mm=10.0)
    d_same_day = build_dashboard([s1, s2], [], settings, FakeTable())
    assert d_same_day.stall is None
    assert d_same_day.stall_unclear is False
    assert d_same_day.growth_se_mm_per_day is None
    assert d_same_day.days_needed is None
    assert d_same_day.shrimp_needed is None

    # N below min_measured
    s3 = SampleRecord(3, date(2026, 11, 1), 4, 0, 90.0, False, None, sd_length_mm=10.0)
    s4 = SampleRecord(4, date(2026, 11, 4), 10, 0, 91.0, False, None, sd_length_mm=10.0)
    d_low_n = build_dashboard([s3, s4], [], settings, FakeTable())
    assert d_low_n.stall is None
    assert d_low_n.stall_unclear is False
    assert d_low_n.growth_se_mm_per_day is None
    assert d_low_n.days_needed is None
    assert d_low_n.shrimp_needed is None

    # Missing mean
    s5 = SampleRecord(5, date(2026, 11, 1), 10, 0, None, False, None, sd_length_mm=10.0)
    s6 = SampleRecord(6, date(2026, 11, 4), 10, 0, 91.0, False, None, sd_length_mm=10.0)
    d_missing_mean = build_dashboard([s5, s6], [], settings, FakeTable())
    assert d_missing_mean.stall is None
    assert d_missing_mean.stall_unclear is False
    assert d_missing_mean.growth_se_mm_per_day is None
    assert d_missing_mean.days_needed is None
    assert d_missing_mean.shrimp_needed is None


def test_empty_dashboard_new_fields():
    # The empty dashboard has the four new fields (None, False, None, None)
    d = build_dashboard([], [], Settings(), FakeTable())
    assert d.empty is True
    assert d.growth_se_mm_per_day is None
    assert d.stall_unclear is False
    assert d.days_needed is None
    assert d.shrimp_needed is None
    assert d.trend_samples is None
    assert d.trend_span_days is None


def test_trend_constants():
    # Verify trend constants
    assert TREND_SAMPLES == 4
    assert TREND_MIN_SPAN_DAYS == 6


def test_trend_maths():
    # Slope and standard error match weighted least squares formulas
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    samples = [
        SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=8.0),
        SampleRecord(2, date(2026, 11, 6), 10, 0, 91.0, False, None, sd_length_mm=8.0),
        SampleRecord(3, date(2026, 11, 11), 10, 0, 92.0, False, None, sd_length_mm=8.0),
        SampleRecord(4, date(2026, 11, 16), 10, 0, 93.0, False, None, sd_length_mm=8.0),
    ]
    res = _trend(samples, settings)
    assert res is not None
    slope, slope_se, n_samples, span = res
    assert slope == pytest.approx(0.2)
    expected_se = math.sqrt((8.0**2 / 10.0) / 125.0)
    assert slope_se == pytest.approx(expected_se)
    assert slope_se == pytest.approx(0.2263, abs=1e-4)
    assert n_samples == 4
    assert span == 15


def test_trend_zero_variance():
    # Zero standard deviation uses smallest positive variance or 1e-6
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    samples = [
        SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=0.0),
        SampleRecord(2, date(2026, 11, 6), 10, 0, 91.0, False, None, sd_length_mm=0.0),
        SampleRecord(3, date(2026, 11, 11), 10, 0, 92.0, False, None, sd_length_mm=0.0),
    ]
    res = _trend(samples, settings)
    assert res is not None
    slope, slope_se, n_samples, span = res
    assert slope == pytest.approx(0.2)
    assert n_samples == 3
    assert span == 10


def test_trend_dashboard_confident_stall():
    # Four samples falling 0.0 per day flag stall True
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    samples = [
        SampleRecord(1, date(2026, 11, 1), 30, 0, 90.0, False, None, sd_length_mm=8.0),
        SampleRecord(2, date(2026, 11, 6), 30, 0, 90.0, False, None, sd_length_mm=8.0),
        SampleRecord(3, date(2026, 11, 11), 30, 0, 90.0, False, None, sd_length_mm=8.0),
        SampleRecord(4, date(2026, 11, 16), 30, 0, 90.0, False, None, sd_length_mm=8.0),
    ]
    d = build_dashboard(samples, [], settings, FakeTable())
    assert d.stall is True
    assert d.stall_unclear is False
    assert d.trend_samples == 4
    assert d.trend_span_days == 15
    assert d.growth_se_mm_per_day is not None


def test_trend_dashboard_confident_not_stall():
    # Four samples growing 1.0 mm per day flag stall False
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    samples = [
        SampleRecord(1, date(2026, 11, 1), 20, 0, 90.0, False, None, sd_length_mm=4.0),
        SampleRecord(2, date(2026, 11, 6), 20, 0, 95.0, False, None, sd_length_mm=4.0),
        SampleRecord(3, date(2026, 11, 11), 20, 0, 100.0, False, None, sd_length_mm=4.0),
        SampleRecord(4, date(2026, 11, 16), 20, 0, 105.0, False, None, sd_length_mm=4.0),
    ]
    d = build_dashboard(samples, [], settings, FakeTable())
    assert d.stall is False
    assert d.stall_unclear is False
    assert d.trend_samples == 4
    assert d.trend_span_days == 15


def test_trend_dashboard_unclear_stall():
    # Four samples growing 0.2 mm per day flag unclear stall
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    samples = [
        SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=8.0),
        SampleRecord(2, date(2026, 11, 6), 10, 0, 91.0, False, None, sd_length_mm=8.0),
        SampleRecord(3, date(2026, 11, 11), 10, 0, 92.0, False, None, sd_length_mm=8.0),
        SampleRecord(4, date(2026, 11, 16), 10, 0, 93.0, False, None, sd_length_mm=8.0),
    ]
    d = build_dashboard(samples, [], settings, FakeTable())
    assert d.stall is None
    assert d.stall_unclear is True
    assert isinstance(d.days_needed, int) and d.days_needed > 0
    assert isinstance(d.shrimp_needed, int) and d.shrimp_needed > 10
    assert d.trend_samples == 4
    assert d.trend_span_days == 15


def test_trend_fallback_to_two_sample_rule():
    # Insufficient usable samples, distinct days, or span fall back to two-sample rule
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)

    s1 = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=8.0)
    s2 = SampleRecord(2, date(2026, 11, 8), 10, 0, 91.0, False, None, sd_length_mm=8.0)
    d_two = build_dashboard([s1, s2], [], settings, FakeTable())
    assert d_two.trend_samples is None
    assert d_two.trend_span_days is None

    s_a = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=8.0)
    s_b = SampleRecord(2, date(2026, 11, 1), 10, 0, 90.2, False, None, sd_length_mm=8.0)
    s_c = SampleRecord(3, date(2026, 11, 8), 10, 0, 91.0, False, None, sd_length_mm=8.0)
    d_two_days = build_dashboard([s_a, s_b, s_c], [], settings, FakeTable())
    d_expected_two_days = build_dashboard([s_b, s_c], [], settings, FakeTable())
    assert d_two_days.trend_samples is None
    assert d_two_days.trend_span_days is None
    assert d_two_days.stall == d_expected_two_days.stall
    assert d_two_days.stall_unclear == d_expected_two_days.stall_unclear
    assert d_two_days.growth_se_mm_per_day == d_expected_two_days.growth_se_mm_per_day

    s_d1 = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=8.0)
    s_d2 = SampleRecord(2, date(2026, 11, 3), 10, 0, 90.5, False, None, sd_length_mm=8.0)
    s_d3 = SampleRecord(3, date(2026, 11, 6), 10, 0, 91.0, False, None, sd_length_mm=8.0)
    d_short_span = build_dashboard([s_d1, s_d2, s_d3], [], settings, FakeTable())
    d_expected_short = build_dashboard([s_d2, s_d3], [], settings, FakeTable())
    assert d_short_span.trend_samples is None
    assert d_short_span.trend_span_days is None
    assert d_short_span.stall == d_expected_short.stall
    assert d_short_span.stall_unclear == d_expected_short.stall_unclear
    assert d_short_span.growth_se_mm_per_day == d_expected_short.growth_se_mm_per_day


def test_trend_skips_sample_without_spread():
    # Samples in group without spread are skipped
    settings = Settings(stall_mm_per_day=0.33, min_measured=5)
    s1 = SampleRecord(1, date(2026, 11, 1), 10, 0, 90.0, False, None, sd_length_mm=8.0)
    s2_no_sd = SampleRecord(2, date(2026, 11, 6), 10, 0, 91.0, False, None, sd_length_mm=None)
    s3 = SampleRecord(3, date(2026, 11, 11), 10, 0, 92.0, False, None, sd_length_mm=8.0)
    s4 = SampleRecord(4, date(2026, 11, 16), 10, 0, 93.0, False, None, sd_length_mm=8.0)
    d = build_dashboard([s1, s2_no_sd, s3, s4], [], settings, FakeTable())
    assert d.trend_samples == 3
    assert d.trend_span_days == 15
    assert d.stall is None
    assert d.stall_unclear is True

