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
from shrimp.pricing import breakeven_growth_mm_per_day, days_to_next_class

Z_CONFIDENT: float = 1.645


def _verdict(prev: SampleRecord, cur: SampleRecord, settings: Settings):
    # Slow-growth verdict between two consecutive samples:
    # (stall, growth_se_mm_per_day, unclear, days_needed, shrimp_needed)
    days = (cur.day - prev.day).days
    if days <= 0:
        return None, None, False, None, None
    if (
        cur.n_measured < settings.min_measured
        or prev.n_measured < settings.min_measured
    ):
        return None, None, False, None, None
    if cur.mean_length_mm is None or prev.mean_length_mm is None:
        return None, None, False, None, None
    growth_per_day = (cur.mean_length_mm - prev.mean_length_mm) / days
    thr = settings.stall_mm_per_day
    if (
        cur.sd_length_mm is not None
        and prev.sd_length_mm is not None
        and cur.n_measured >= 2
        and prev.n_measured >= 2
    ):
        # both samples carry a spread: say slow or not slow only when growth is clear of the noise
        sigma_diff = math.sqrt(
            (cur.sd_length_mm ** 2) / cur.n_measured
            + (prev.sd_length_mm ** 2) / prev.n_measured
        )
        se = sigma_diff / days
        if growth_per_day + Z_CONFIDENT * se < thr - 1e-9:
            return True, se, False, None, None
        if growth_per_day - Z_CONFIDENT * se >= thr - 1e-9:
            return False, se, False, None, None
        days_needed = math.ceil(Z_CONFIDENT * sigma_diff / thr)
        shrimp_needed = math.ceil(
            cur.n_measured * (Z_CONFIDENT * sigma_diff / (days * thr)) ** 2
        )
        return None, se, True, days_needed, shrimp_needed
    # Float guard avoids rounding up actual stalls while tolerating float imprecision
    return growth_per_day < thr - 1e-9, None, False, None, None


def _calc_stall(
    prev: SampleRecord, cur: SampleRecord, settings: Settings
) -> Optional[bool]:
    # Stall status between two consecutive samples (used for each chart point)
    return _verdict(prev, cur, settings)[0]


def build_dashboard(
    samples: Iterable[SampleRecord],
    feeds: Iterable[FeedEntry],
    settings: Settings,
    table: Any,
    prices: Optional[Any] = None,
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
            value_per_kg_vnd=None,
            next_class_per_kg=None,
            next_class_price_vnd=None,
            next_class_gain_pct=None,
            days_to_next_class=None,
            breakeven_mm_per_day=None,
            price_source=None,
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

        (
            stall,
            growth_se_mm_per_day,
            stall_unclear,
            days_needed,
            shrimp_needed,
        ) = _verdict(previous, latest, settings)

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

    (
        val_vnd,
        nc_size,
        nc_price,
        nc_gain,
        days_next,
        breakeven,
        price_source,
    ) = _calc_pricing(
        latest_length_mm,
        latest_size_per_kg,
        growth_mm_per_day,
        stall,
        settings,
        table,
        prices,
    )

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
        value_per_kg_vnd=val_vnd,
        next_class_per_kg=nc_size,
        next_class_price_vnd=nc_price,
        next_class_gain_pct=nc_gain,
        days_to_next_class=days_next,
        breakeven_mm_per_day=breakeven,
        price_source=price_source,
    )


def _calc_pricing(
    latest_length_mm: Optional[float],
    latest_size_per_kg: Optional[float],
    growth_mm_per_day: Optional[float],
    stall: Optional[bool],
    settings: Settings,
    table: Any,
    prices: Optional[Any],
) -> Tuple[
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[float],
    Optional[int],
    Optional[float],
    Optional[str],
]:
    # Calculate valuation, next class and break-even growth from price table
    if prices is None or latest_size_per_kg is None:
        return None, None, None, None, None, None, None

    price = prices.price_per_kg(latest_size_per_kg)
    val_vnd = int(round(price)) if price is not None else None

    nc = prices.next_class(latest_size_per_kg)
    nc_size: Optional[int] = None
    nc_price: Optional[int] = None
    nc_gain: Optional[float] = None
    if nc is not None:
        nc_size = int(round(nc[0]))
        nc_price = int(round(nc[1]))
        if price is not None and price > 0:
            nc_gain = round(((nc[1] - price) / price) * 100.0, 1)

    days_next: Optional[int] = None
    if (
        growth_mm_per_day is not None
        and growth_mm_per_day > 0
        and stall is not True
        and latest_length_mm is not None
    ):
        days_next = days_to_next_class(
            latest_length_mm,
            latest_size_per_kg,
            growth_mm_per_day,
            table,
            prices=prices,
        )

    breakeven: Optional[float] = None
    if latest_length_mm is not None and val_vnd is not None:
        breakeven = breakeven_growth_mm_per_day(
            latest_length_mm,
            latest_size_per_kg,
            settings.feed_price_vnd,
            val_vnd,
            settings.ration_pct,
            table,
        )

    source = getattr(prices, "source", None)

    return val_vnd, nc_size, nc_price, nc_gain, days_next, breakeven, source
