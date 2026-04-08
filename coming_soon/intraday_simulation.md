# Intraday Simulation

## Problem

The current library calculates metrics for a single interval at a time. Real WFM planning requires running the calculation across every interval of the day (typically 15 or 30-minute buckets), applying arrival curves, and producing a full-day staffing plan — exactly what the "MODELO MENSAL" Excel spreadsheet does with its day-by-day tabs.

## What It Solves

- Full-day dimensioning with interval-by-interval granularity
- Arrival curve application (volume distribution across the day)
- Peak detection and staffing optimization
- Direct replacement for the manual Excel workflow

## How It Works

### Input: Arrival Curve + Daily Volume

```python
# Arrival curve: percentage of daily volume per interval
# Example: 48 intervals of 30 minutes
curve = [0.01, 0.01, 0.02, 0.03, 0.04, 0.05, ...]  # sums to 1.0

# Daily totals
daily_volume = 1200  # total calls
aht = 180            # seconds
sla_target = 0.80
answer_time = 20     # seconds
```

### Output: Staffing Plan

```python
{
    "intervals": [
        {
            "start": "06:00",
            "end": "06:30",
            "volume": 12,
            "agents_required": 4,
            "expected_sla": 0.92,
            "expected_asa": 8,
            "occupancy": 0.45
        },
        ...
    ],
    "peak_interval": "10:30",
    "peak_agents": 28,
    "total_agent_hours": 156.5
}
```

## API Surface (Draft)

```python
# Core function
simulate_day(
    daily_volume: int,
    arrival_curve: list[float],
    aht: int,
    sla: float,
    service_time: int,
    interval_minutes: int = 30
) -> dict

# With shift constraints
simulate_day_with_shifts(
    daily_volume: int,
    arrival_curve: list[float],
    aht: int,
    sla: float,
    service_time: int,
    shifts: list[dict],  # start, end, headcount per shift
    interval_minutes: int = 30
) -> dict

# Batch: multiple days
simulate_month(
    daily_volumes: dict[str, int],  # date -> volume
    arrival_curves: dict[str, list[float]],  # weekday type -> curve
    aht: int,
    sla: float,
    service_time: int
) -> dict
```

## Standard Arrival Curves

Could ship with default curves based on industry patterns:

- `CURVE_WEEKDAY_VOZ` — typical voice weekday (peaks at 10h and 14h)
- `CURVE_SATURDAY` — reduced volume, single peak
- `CURVE_SUNDAY` — minimal volume
- `CURVE_FLAT` — uniform distribution (baseline)

Users can provide their own curves (like the "CURVA" tab in the Excel model).

## Complexity

Medium. The math per interval is what the library already does — the new part is orchestration, curve handling, and output formatting.

## Dependencies on Other Features

- Benefits from Erlang A (abandonment) for more realistic modeling
- Benefits from shrinkage factor for scheduled vs on-phone HC
- Benefits from occupancy cap for realistic staffing

## Output Formats

- Python dict (default)
- CSV export
- Excel export (to replace the spreadsheet workflow)
- JSON (for API consumers)
