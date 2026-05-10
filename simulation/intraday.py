"""
Intraday simulation: per-interval staffing plan for a full day.

This module turns a daily volume plus an arrival curve into an
interval-by-interval staffing plan, the same workflow used by the
"MODELO MENSAL" Excel spreadsheet. The per-interval math is delegated to the
existing ``agents.capacity`` and ``queues.queues`` helpers — this module
orchestrates them, validates the curve, and detects the peak.

Spec: ``coming_soon/intraday_simulation.md``.
"""

import math

from mod_turbotab.agents.capacity import agents_required, asa, occupancy
from mod_turbotab.agents.shrinkage import scheduled_agents, _validate_shrinkage
from mod_turbotab.queues.queues import sla_metric
from mod_turbotab.exceptions import InputValidationError


_CURVE_SUM_TOLERANCE = 1e-6


def _normalize(weights):
    """Rescale a non-negative weight vector so it sums to ``1.0`` exactly.

    Any residual floating-point drift after division is absorbed by the last
    element, guaranteeing ``sum(result) == 1.0`` within ``2**-52``.
    """
    total = sum(weights)
    if total <= 0:
        raise InputValidationError("Curve weights must sum to a positive value.")
    curve = [w / total for w in weights]
    curve[-1] += 1.0 - sum(curve)
    return curve


# Raw weights below are the *shape* of each curve. They are normalized at module
# load time so each constant sums to exactly 1.0. 48 entries = 30-minute buckets
# across a 24-hour day, starting at 00:00. Users can supply their own curves of
# any length; these are merely sensible defaults inspired by the "CURVA" tab of
# the Excel model.

_WEEKDAY_VOZ_WEIGHTS = [
    # 00:00-03:00 — overnight, minimal traffic
    0.2, 0.2, 0.2, 0.2, 0.2, 0.2,
    # 03:00-06:00 — ramping up before opening
    0.2, 0.3, 0.5, 0.7, 1.0, 1.5,
    # 06:00-09:00 — early-morning rise
    2.0, 3.0, 4.0, 5.0, 6.0, 7.0,
    # 09:00-12:00 — morning peak around 10:00
    8.0, 9.0, 9.5, 9.0, 7.5, 6.5,
    # 12:00-15:00 — lunch dip + afternoon peak around 14:00
    5.5, 5.0, 6.0, 7.5, 8.5, 8.0,
    # 15:00-18:00 — afternoon taper
    7.0, 6.0, 4.5, 3.5, 2.5, 1.5,
    # 18:00-21:00 — evening tail
    1.0, 0.8, 0.5, 0.5, 0.3, 0.3,
    # 21:00-24:00 — late-night minimum
    0.3, 0.3, 0.2, 0.2, 0.2, 0.2,
]

_SATURDAY_WEIGHTS = [
    0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
    0.1, 0.1, 0.2, 0.3, 0.5, 0.8,
    1.2, 1.8, 2.5, 3.5, 4.5, 5.5,
    6.5, 7.5, 8.5, 9.0, 8.5, 7.5,
    6.5, 5.5, 4.5, 3.5, 3.0, 2.5,
    2.0, 1.5, 1.0, 0.8, 0.5, 0.5,
    0.4, 0.4, 0.3, 0.3, 0.2, 0.2,
    0.2, 0.2, 0.1, 0.1, 0.1, 0.1,
]

_SUNDAY_WEIGHTS = [
    0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
    0.1, 0.1, 0.1, 0.1, 0.2, 0.3,
    0.5, 0.7, 1.0, 1.3, 1.7, 2.0,
    2.3, 2.5, 2.7, 2.9, 3.0, 3.0,
    3.0, 2.9, 2.7, 2.5, 2.3, 2.0,
    1.7, 1.3, 1.0, 0.7, 0.5, 0.4,
    0.3, 0.3, 0.2, 0.2, 0.2, 0.2,
    0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
]


CURVE_WEEKDAY_VOZ = _normalize(_WEEKDAY_VOZ_WEIGHTS)
"""Typical voice weekday curve: 48 × 30min, peaks at 10:00 and 14:00."""

CURVE_SATURDAY = _normalize(_SATURDAY_WEIGHTS)
"""Saturday curve: 48 × 30min, single peak around 11:00, reduced volume."""

CURVE_SUNDAY = _normalize(_SUNDAY_WEIGHTS)
"""Sunday curve: 48 × 30min, broad midday plateau, minimal volume."""

CURVE_FLAT = _normalize([1.0] * 48)
"""Baseline flat curve: 48 × 30min, uniform distribution (1/48 per interval)."""


def _validate_curve(arrival_curve):
    """Reject curves that are empty, contain negatives, or do not sum to 1.0."""
    if not arrival_curve:
        raise InputValidationError("arrival_curve must contain at least one entry.")
    for i, value in enumerate(arrival_curve):
        if value < 0:
            raise InputValidationError(
                f"arrival_curve[{i}] must be >= 0 (got {value})."
            )
    total = sum(arrival_curve)
    if not math.isclose(total, 1.0, abs_tol=_CURVE_SUM_TOLERANCE):
        raise InputValidationError(
            f"arrival_curve must sum to 1.0 (got {total}). "
            f"Tolerance is {_CURVE_SUM_TOLERANCE}."
        )


def _format_time(total_minutes):
    """Render a minute offset as ``HH:MM`` (24:00 is allowed for end-of-day)."""
    hours, minutes = divmod(int(total_minutes), 60)
    return f"{hours:02d}:{minutes:02d}"


def simulate_day(
    daily_volume: int,
    arrival_curve: list,
    aht: int,
    sla: float,
    service_time: int,
    interval_minutes: int = 30,
    patience: float = None,
    max_occupancy: float = None,
    shrinkage: float = 0.0,
) -> dict:
    """Produce a full-day staffing plan, one row per interval.

    For each interval the daily volume is distributed according to
    ``arrival_curve[i]``, then :func:`agents_required` sizes the on-phone
    headcount and :func:`sla_metric` / :func:`asa` / :func:`occupancy` compute
    the expected service metrics. The output dict matches the shape documented
    in ``coming_soon/intraday_simulation.md``.

    Args:
        daily_volume (int): Total calls for the day.
        arrival_curve (list[float]): Fraction of ``daily_volume`` per interval.
            Must be non-negative and sum to ``1.0`` (within
            ``1e-6``). Length determines the number of intervals.
        aht (int): Average handle time in seconds.
        sla (float): Target service level (e.g. ``0.80``).
        service_time (int): Target answer time in seconds.
        interval_minutes (int, optional): Length of each interval in minutes.
            Defaults to ``30``.
        patience (float, optional): Average patience in seconds (Erlang A).
            ``None`` uses Erlang C.
        max_occupancy (float, optional): Occupancy cap in ``(0, 1]`` forwarded
            to :func:`agents_required`. ``None`` disables the cap (default
            behavior is unchanged).
        shrinkage (float, optional): Shrinkage fraction in ``[0.0, 1.0)``.
            When ``> 0`` each interval gets a ``scheduled_agents`` field and
            the report includes ``peak_scheduled_agents`` and
            ``total_scheduled_hours``. Defaults to ``0.0`` (no adjustment).

    Returns:
        dict: ``{"intervals": [...], "peak_interval": "HH:MM",
        "peak_agents": int, "total_agent_hours": float}`` plus the scheduled-HC
        fields when ``shrinkage > 0``.

    Raises:
        InputValidationError: On invalid curve, negative volume, non-positive
            ``aht``/``interval_minutes``, or invalid ``shrinkage``.
    """
    if daily_volume < 0:
        raise InputValidationError("daily_volume must be >= 0.")
    if aht <= 0:
        raise InputValidationError("aht must be > 0.")
    if interval_minutes <= 0:
        raise InputValidationError("interval_minutes must be > 0.")
    _validate_curve(arrival_curve)
    _validate_shrinkage(shrinkage)

    interval_seconds = float(interval_minutes * 60)
    intervals = []
    peak_idx = 0
    peak_agents = -1
    peak_scheduled = -1
    total_agents = 0
    total_scheduled = 0

    for i, fraction in enumerate(arrival_curve):
        # Round to the nearest integer call; with millions of calls and a fine
        # curve the rounding error is bounded by ``len(curve)/2`` calls total.
        volume = int(round(daily_volume * fraction))
        start_minutes = i * interval_minutes
        end_minutes = (i + 1) * interval_minutes

        if volume == 0:
            agents = 0
            interval_sla = 1.0
            interval_asa = 0
            interval_occ = 0.0
        else:
            agents = agents_required(
                sla,
                service_time,
                volume,
                aht,
                interval=interval_seconds,
                patience=patience,
                max_occupancy=max_occupancy,
            )
            interval_sla = sla_metric(
                agents,
                service_time,
                volume,
                aht,
                interval=interval_seconds,
                patience=patience,
            )
            interval_asa = asa(
                agents,
                volume,
                aht,
                interval=interval_seconds,
                patience=patience,
            )
            interval_occ = occupancy(agents, volume, aht, interval=interval_seconds)

        row = {
            "start": _format_time(start_minutes),
            "end": _format_time(end_minutes),
            "volume": volume,
            "agents_required": agents,
            "expected_sla": interval_sla,
            "expected_asa": interval_asa,
            "occupancy": interval_occ,
        }
        if shrinkage > 0.0:
            scheduled = scheduled_agents(agents, shrinkage)
            row["scheduled_agents"] = scheduled
            total_scheduled += scheduled
            if scheduled > peak_scheduled:
                peak_scheduled = scheduled

        intervals.append(row)
        total_agents += agents
        if agents > peak_agents:
            peak_agents = agents
            peak_idx = i

    hours_per_interval = interval_minutes / 60.0
    report = {
        "intervals": intervals,
        "peak_interval": _format_time(peak_idx * interval_minutes),
        "peak_agents": peak_agents,
        "total_agent_hours": total_agents * hours_per_interval,
    }
    if shrinkage > 0.0:
        report["peak_scheduled_agents"] = peak_scheduled
        report["total_scheduled_hours"] = total_scheduled * hours_per_interval
    return report
