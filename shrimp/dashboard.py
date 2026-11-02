import math
from typing import Any, Iterable, List, Optional

from shrimp.models import (
    ChartPoint,
    Dashboard,
    FeedEntry,
    SampleRecord,
    SampleRow,
    Settings,
)

Z_CONFIDENT: float = 1.645


def _calc_stall(
    prev: SampleRecord, cur: SampleRecord, settings: Settings
) -> Optional[bool]:
    # Calculate stall status between two consecutive samples
    days = (cur.day - prev.day).days
    if days <= 0:
        return None
    if (
        cur.n_measured < settings.min_measured
        or prev.n_measured < settings.min_measured
    ):
        return None
    if cur.mean_length_mm is None or prev.mean_length_mm is None:
        return None
    growth_per_day = (cur.mean_length_mm - prev.mean_length_mm) / days
    if (
        cur.sd_length_mm is not None
        and prev.sd_length_mm is not None
        and cur.n_measured >= max(2, settings.min_measured)
        and prev.n_measured >= max(2, settings.min_measured)
    ):
        sigma_diff = math.sqrt(
            (cur.sd_length_mm ** 2) / cur.n_measured
            + (prev.sd_length_mm ** 2) / prev.n_measured
        )
        se = sigma_diff / days
        thr = settings.stall_mm_per_day
        if growth_per_day + Z_CONFIDENT * se < thr - 1e-9:
            return True
        if growth_per_day - Z_CONFIDENT * se >= thr - 1e-9:
            return False
        return None
    # Float guard avoids rounding up actual stalls while tolerating float imprecision
    return growth_per_day < settings.stall_mm_per_day - 1e-9


def build_dashboard(
    samples: Iterable[SampleRecord],
    feeds: Iterable[FeedEntry],
    settings: Settings,
    table: Any,
) -> Dashboard:
    # Build dashboard model from samples, feeds, settings, and size table
    sorted_samples = sorted(samples, key=lambda s: (s.day, s.id))
    if not sorted_samples:
        return Dashboard(
            empty=True,
            latest_length_mm=None,
            latest_size_per_kg=None,
            n_latest=None,
            change_length_mm=None,
            change_size_per_kg=None,
            n_previous=None,
            days_between=None,
            stall=None,
            at_harvest=False,
            stall_day_cost_vnd=None,
            chart=[],
            rows=[],
            notices=[],
            growth_mm_per_day=None,
            stall_threshold_mm_per_day=settings.stall_mm_per_day,
            harvest_threshold_per_kg=settings.harvest_per_kg,
            min_measured=settings.min_measured,
            growth_se_mm_per_day=None,
            stall_unclear=False,
            days_needed=None,
            shrimp_needed=None,
        )

    rows: List[SampleRow] = []
    for i, s in enumerate(sorted_samples):
        size = table.per_kg(s.mean_length_mm) if s.mean_length_mm is not None else None
        growth: Optional[float] = None
        if i > 0:
            prev = sorted_samples[i - 1]
            days = (s.day - prev.day).days
            if (
                days > 0
                and s.mean_length_mm is not None
                and prev.mean_length_mm is not None
            ):
                growth = (s.mean_length_mm - prev.mean_length_mm) / days
        rows.append(
            SampleRow(
                day=s.day,
                n_measured=s.n_measured,
                mean_length_mm=s.mean_length_mm,
                size_per_kg=size,
                demo=s.demo,
                growth_mm_per_day=growth,
            )
        )

    latest = sorted_samples[-1]
    latest_length_mm = latest.mean_length_mm
    latest_size_per_kg = (
        table.per_kg(latest.mean_length_mm)
        if latest.mean_length_mm is not None
        else None
    )
    n_latest = latest.n_measured

    previous = sorted_samples[-2] if len(sorted_samples) > 1 else None
    n_previous: Optional[int] = None
    days_between: Optional[int] = None
    change_length_mm: Optional[float] = None
    change_size_per_kg: Optional[float] = None
    stall_notice: Optional[str] = None
    stall: Optional[bool] = None
    growth_mm_per_day: Optional[float] = None
    growth_se_mm_per_day: Optional[float] = None
    stall_unclear: bool = False
    days_needed: Optional[int] = None
    shrimp_needed: Optional[int] = None

    if previous is not None:
        n_previous = previous.n_measured
        days_between = (latest.day - previous.day).days
        if latest.mean_length_mm is not None and previous.mean_length_mm is not None:
            change_length_mm = latest.mean_length_mm - previous.mean_length_mm
            if days_between > 0:
                growth_mm_per_day = change_length_mm / days_between
        prev_size = (
            table.per_kg(previous.mean_length_mm)
            if previous.mean_length_mm is not None
            else None
        )
        if latest_size_per_kg is not None and prev_size is not None:
            change_size_per_kg = latest_size_per_kg - prev_size

        if days_between == 0:
            stall_notice = "same_day"
        elif (
            latest.n_measured < settings.min_measured
            or previous.n_measured < settings.min_measured
        ):
            stall_notice = "not_enough_shrimp"

        if (
            latest.sd_length_mm is not None
            and previous.sd_length_mm is not None
            and latest.n_measured >= max(2, settings.min_measured)
            and previous.n_measured >= max(2, settings.min_measured)
            and days_between > 0
            and growth_mm_per_day is not None
        ):
            thr = settings.stall_mm_per_day
            sigma_diff = math.sqrt(
                (latest.sd_length_mm ** 2) / latest.n_measured
                + (previous.sd_length_mm ** 2) / previous.n_measured
            )
            growth_se_mm_per_day = sigma_diff / days_between
            z_se = Z_CONFIDENT * growth_se_mm_per_day
            if growth_mm_per_day + z_se < thr - 1e-9:
                stall = True
                stall_unclear = False
            elif growth_mm_per_day - z_se >= thr - 1e-9:
                stall = False
                stall_unclear = False
            else:
                stall = None
                stall_unclear = True
                days_needed = math.ceil(Z_CONFIDENT * sigma_diff / thr)
                shrimp_needed = math.ceil(
                    latest.n_measured
                    * (Z_CONFIDENT * sigma_diff / (days_between * thr)) ** 2
                )
        else:
            stall = _calc_stall(previous, latest, settings)

    chart: List[ChartPoint] = []
    for i, s in enumerate(sorted_samples):
        if s.mean_length_mm is None:
            continue
        pt_stall = False
        if i > 0:
            pt_stall = _calc_stall(sorted_samples[i - 1], s, settings) is True
        chart.append(
            ChartPoint(
                day=s.day,
                mean_length_mm=s.mean_length_mm,
                stall=pt_stall,
            )
        )

    at_harvest = (
        latest_size_per_kg is not None
        and latest_size_per_kg <= settings.harvest_per_kg
    )

    qualifying_feeds = [f for f in feeds if f.day <= latest.day]
    feed_notice: Optional[str] = None
    stall_day_cost_vnd: Optional[int] = None
    if qualifying_feeds:
        latest_feed = max(
            enumerate(qualifying_feeds), key=lambda item: (item[1].day, item[0])
        )[1]
        stall_day_cost_vnd = int(round(latest_feed.kg_per_day * latest_feed.price_vnd))
    else:
        feed_notice = "no_feed"

    notices: List[str] = []
    if stall_notice is not None:
        notices.append(stall_notice)
    if feed_notice is not None:
        notices.append(feed_notice)
    if table.temporary and latest_size_per_kg is not None:
        notices.append("temporary_table")
        notices.append("rough_estimate")
    if latest.mean_length_mm is not None and latest_size_per_kg is None:
        notices.append("outside_table_range")

    return Dashboard(
        empty=False,
        latest_length_mm=latest_length_mm,
        latest_size_per_kg=latest_size_per_kg,
        n_latest=n_latest,
        change_length_mm=change_length_mm,
        change_size_per_kg=change_size_per_kg,
        n_previous=n_previous,
        days_between=days_between,
        stall=stall,
        at_harvest=at_harvest,
        stall_day_cost_vnd=stall_day_cost_vnd,
        chart=chart,
        rows=rows,
        notices=notices,
        growth_mm_per_day=growth_mm_per_day,
        stall_threshold_mm_per_day=settings.stall_mm_per_day,
        harvest_threshold_per_kg=settings.harvest_per_kg,
        min_measured=settings.min_measured,
        growth_se_mm_per_day=growth_se_mm_per_day,
        stall_unclear=stall_unclear,
        days_needed=days_needed,
        shrimp_needed=shrimp_needed,
    )
