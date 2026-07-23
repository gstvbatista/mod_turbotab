"""
Shrinkage and absenteeism adjustments for workforce scheduling.

Erlang C calculates the number of agents needed **on the phones**. Shrinkage
bridges the gap between "agents on phones" and "agents to schedule" by
applying the standard workforce-management correction:

    HC_scheduled = HC_required / (1 - shrinkage)

This module implements **Option A** (post-calculation adjustment) from the
``coming_soon/shrinkage_absenteeism.md`` spec: the core Erlang math is
unchanged; shrinkage is layered on top.
"""

import math

from mod_turbotab.agents.capacity import agents_required
from mod_turbotab.exceptions import InputValidationError


def _validate_shrinkage(shrinkage: float) -> None:
    """Reject invalid shrinkage factors.

    Shrinkage must be in ``[0.0, 1.0)``. A value of ``1.0`` would imply the
    workforce is entirely unavailable (division by zero); negative values are
    nonsensical.
    """
    if shrinkage < 0 or shrinkage >= 1.0:
        raise InputValidationError(
            "Shrinkage deve estar no intervalo [0.0, 1.0). "
            f"Recebido: {shrinkage}."
        )


def scheduled_agents(agents_on_phone: int, shrinkage: float) -> int:
    """Inflate ``agents_on_phone`` by the shrinkage factor.

    Args:
        agents_on_phone (int): Number of agents required on the phones
            (e.g. the output of :func:`agents_required`).
        shrinkage (float): Fraction of paid time unavailable for handling
            calls, in ``[0.0, 1.0)``. ``0.0`` returns ``agents_on_phone``
            unchanged.

    Returns:
        int: Headcount to schedule, rounded up.

    Raises:
        InputValidationError: If ``shrinkage`` is outside ``[0.0, 1.0)`` or
            ``agents_on_phone`` is negative.
    """
    if agents_on_phone < 0:
        raise InputValidationError(
            "agents_on_phone deve ser >= 0. "
            f"Recebido: {agents_on_phone}."
        )
    _validate_shrinkage(shrinkage)
    if shrinkage == 0.0:
        return int(agents_on_phone)
    return int(math.ceil(agents_on_phone / (1.0 - shrinkage)))


def shrinkage_factor(
    breaks: float = 0.0,
    training: float = 0.0,
    meetings: float = 0.0,
    absenteeism: float = 0.0,
    system_downtime: float = 0.0,
    other: float = 0.0,
) -> float:
    """Combine individual shrinkage components into a single factor.

    Components are additive — they represent disjoint slices of paid time
    spent off the phones. Each component must be in ``[0.0, 1.0)`` and the
    sum must remain strictly below ``1.0``.

    Args:
        breaks (float): Paid breaks.
        training (float): Training time.
        meetings (float): Team meetings, one-on-ones, etc.
        absenteeism (float): Unplanned absences.
        system_downtime (float): Time lost to system/tooling outages.
        other (float): Any additional component not listed above.

    Returns:
        float: Combined shrinkage in ``[0.0, 1.0)``.

    Raises:
        InputValidationError: If any component is negative or the total
            reaches ``1.0``.
    """
    components = {
        "breaks": breaks,
        "training": training,
        "meetings": meetings,
        "absenteeism": absenteeism,
        "system_downtime": system_downtime,
        "other": other,
    }
    for name, value in components.items():
        if value < 0:
            raise InputValidationError(
                f"Componente de shrinkage '{name}' deve ser >= 0. "
                f"Recebido: {value}."
            )
    total = sum(components.values())
    _validate_shrinkage(total)
    return total


def agents_required_with_shrinkage(
    sla: float,
    service_time: int,
    calls_per_interval: float,
    aht: int,
    shrinkage: float = 0.0,
    interval: float = 600.0,
    patience: float = None,
) -> int:
    """Compute scheduled headcount, applying shrinkage to Erlang C output.

    This is :func:`agents_required` followed by :func:`scheduled_agents`.
    With ``shrinkage=0.0`` (the default) the result is identical to
    ``agents_required(...)``.

    Args:
        sla (float): Target service level (e.g. ``0.80`` for 80%).
        service_time (int): Target answer time in seconds.
        calls_per_interval (float): Arrivals per planning interval.
        aht (int): Average handle time in seconds.
        shrinkage (float, optional): Combined shrinkage in ``[0.0, 1.0)``.
            Defaults to ``0.0`` (no adjustment).
        interval (float, optional): Planning interval in seconds.
            Defaults to ``600`` (10 minutes), matching the rest of the
            library.
        patience (float, optional): Average patience for Erlang A. ``None``
            uses pure Erlang C.

    Returns:
        int: Number of agents to schedule.

    Raises:
        InputValidationError: If ``shrinkage`` is invalid or any of the
            underlying parameters fail validation in :func:`agents_required`.
        CalculationError: If the underlying Erlang calculation fails.
    """
    _validate_shrinkage(shrinkage)
    on_phone = agents_required(
        sla,
        service_time,
        calls_per_interval,
        aht,
        interval=interval,
        patience=patience,
    )
    return scheduled_agents(on_phone, shrinkage)
