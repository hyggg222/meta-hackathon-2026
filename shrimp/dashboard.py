import math
from typing import Any, Iterable, List, Optional, Tuple

from shrimp.models import (
    ChartPoint,
    Dashboard,
    FeedEntry,
    SampleRecord,
    SampleRow,
    Settings,
)

Z_CONFIDENT: float = 1.645
TREND_SAMPLES: int = 4
TREND_MIN_SPAN_DAYS: int = 6


def _trend(
    samples: Iterable[SampleRecord], settings: Settings
) -> Optional[Tuple[float, float, int, int]]:
    # Weighted least squares line over the latest usable samples:
    # returns (slope, slope_se, n_samples, span_days) or None
    usable = [
        s
        for s in samples
        if s.mean_length_mm is not None
        and s.sd_length_mm is not None
        and s.n_measured >= max(2, settings.min_measured)
    ]
    usable.sort(key=lambda s: (s.day, s.id))
    selected = usable[-TREND_SAMPLES:]
    if len(selected) < 3:
        return None
    span = (selected[-1].day - selected[0].day).days
    if span < TREND_MIN_SPAN_DAYS:
        return None
    if len({s.day for s in selected}) < 3:
        return None

    base_day = selected[0].day
    t_list = [(s.day - base_day).days for s in selected]
    y_list = [s.mean_length_mm for s in selected]

    raw_vars = [(s.sd_length_mm ** 2) / s.n_measured for s in selected]
    pos_vars = [v for v in raw_vars if v > 0]
    fallback_var = min(pos_vars) if pos_vars else 1e-6

    weights = [1.0 / (v if v > 0 else fallback_var) for v in raw_vars]
    sum_w = sum(weights)
    t_w = sum(w * t for w, t in zip(weights, t_list)) / sum_w
    y_w = sum(w * y for w, y in zip(weights, y_list)) / sum_w

    denom = sum(w * ((t - t_w) ** 2) for w, t in zip(weights, t_list))
    if denom <= 0:
        return None
    numer = sum(
        w * (t - t_w) * (y - y_w) for w, t, y in zip(weights, t_list, y_list)
    )
    slope = numer / denom
    slope_se = 1.0 / math.sqrt(denom)
    return slope, slope_se, len(selected), span


def _verdict(
    samples_or_prev,
    cur_or_settings=None,
    settings: Optional[Settings] = None,
):
    # Slow-growth verdict using trend or two consecutive samples:
    # (stall, growth_se_mm_per_day, unclear, days_needed, shrimp_needed, trend_samples, trend_span_days)
    if settings is not None:
        samples = [samples_or_prev, cur_or_settings]
        cfg = settings
    elif isinstance(samples_or_prev, (list, tuple)):
        samples = list(samples_or_prev)
        cfg = cur_or_settings
    else:
        samples = [samples_or_prev]
        cfg = cur_or_settings

    sorted_samples = sorted(samples, key=lambda s: (s.day, s.id))
    if len(sorted_samples) < 2:
        return None, None, False, None, None, None, None

    cur = sorted_samples[-1]
    prev = sorted_samples[-2]

    cur_usable = (
        cur.mean_length_mm is not None
        and cur.sd_length_mm is not None
        and cur.n_measured >= max(2, cfg.min_measured)
    )
    if cur_usable:
        trend_res = _trend(sorted_samples, cfg)
        if trend_res is not None:
            slope, slope_se, n_trend, span = trend_res
            growth = slope
            se = slope_se
            thr = cfg.stall_mm_per_day
            if growth + Z_CONFIDENT * se < thr - 1e-9:
                return True, se, False, None, None, n_trend, span
            if growth - Z_CONFIDENT * se >= thr - 1e-9:
                return False, se, False, None, None, n_trend, span
            # slope_se scales roughly as 1 / span**1.5; extra days needed to reach thr / Z_CONFIDENT
            days_needed = max(
                1,
                math.ceil(
                    span * ((slope_se * Z_CONFIDENT / thr) ** (2.0 / 3.0))
                    - span
                ),
            )
            usable_samples = [
                s
                for s in sorted_samples
                if s.mean_length_mm is not None
                and s.sd_length_mm is not None
                and s.n_measured >= max(2, cfg.min_measured)
            ]
            usable_samples.sort(key=lambda s: (s.day, s.id))
            selected = usable_samples[-TREND_SAMPLES:]
            mean_n = sum(s.n_measured for s in selected) / len(selected)
            shrimp_needed = math.ceil(
                mean_n * (Z_CONFIDENT * slope_se / thr) ** 2
            )
            return None, se, True, days_needed, shrimp_needed, n_trend, span

    days = (cur.day - prev.day).days
    if days <= 0:
        return None, None, False, None, None, None, None
    if (
        cur.n_measured < cfg.min_measured
        or prev.n_measured < cfg.min_measured
    ):
        return None, None, False, None, None, None, None
    if cur.mean_length_mm is None or prev.mean_length_mm is None:
        return None, None, False, None, None, None, None
    growth_per_day = (cur.mean_length_mm - prev.mean_length_mm) / days
    thr = cfg.stall_mm_per_day
    if (
        cur.sd_length_mm is not None
        and prev.sd_length_mm is not None
        and cur.n_measured >= 2
        and prev.n_measured >= 2
    ):
        sigma_diff = math.sqrt(
            (cur.sd_length_mm ** 2) / cur.n_measured
            + (prev.sd_length_mm ** 2) / prev.n_measured
        )
        se = sigma_diff / days
        if growth_per_day + Z_CONFIDENT * se < thr - 1e-9:
            return True, se, False, None, None, None, None
        if growth_per_day - Z_CONFIDENT * se >= thr - 1e-9:
            return False, se, False, None, None, None, None
        days_needed = math.ceil(Z_CONFIDENT * sigma_diff / thr)
        shrimp_needed = math.ceil(
            cur.n_measured * (Z_CONFIDENT * sigma_diff / (days * thr)) ** 2
        )
        return None, se, True, days_needed, shrimp_needed, None, None
    return growth_per_day < thr - 1e-9, None, False, None, None, None, None


def _calc_stall(
    samples_or_prev,
    cur_or_settings=None,
    settings: Optional[Settings] = None,
) -> Optional[bool]:
    # Stall status using the trend or two-sample verdict for chart points
    return _verdict(samples_or_prev, cur_or_settings, settings)[0]


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
            trend_samples=None,
            trend_span_days=None,
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
    trend_samples: Optional[int] = None
    trend_span_days: Optional[int] = None

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

        (
            stall,
            growth_se_mm_per_day,
            stall_unclear,
            days_needed,
            shrimp_needed,
            trend_samples,
            trend_span_days,
        ) = _verdict(sorted_samples, settings)

    chart: List[ChartPoint] = []
    for i, s in enumerate(sorted_samples):
        if s.mean_length_mm is None:
            continue
        pt_stall = False
        if i > 0:
            pt_stall = _calc_stall(sorted_samples[: i + 1], settings) is True
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
        trend_samples=trend_samples,
        trend_span_days=trend_span_days,
    )
