# Occupancy Cap (Maximum Utilization)

## Problem

Erlang C assumes agents can sustain up to ~99% occupancy. In practice, sustained occupancy above 85% leads to agent burnout, quality degradation, increased turnover, and higher absenteeism. Operations teams manually pad headcount to keep occupancy in a healthy range, but this adjustment is done outside the model.

## What It Solves

- Prevents dimensioning that would overload agents
- Makes the library output realistic for scheduling decisions
- Eliminates manual HC adjustments for occupancy control
- Aligns mathematical output with operational health constraints

## How It Works

### Current behavior (no cap)

```python
agents_required(0.80, 20, 25, 180)  # -> 11
# Occupancy: A/N = 7.5/11 = 68%
```

### With occupancy cap

```python
agents_required(0.80, 20, 25, 180, max_occupancy=0.85)  # -> 11 (already under 85%)
agents_required(0.80, 20, 100, 180, max_occupancy=0.85)  # -> 36 (instead of 33, to stay under 85%)
```

The logic:

1. Calculate agents via normal Erlang C
2. Calculate `min_agents_for_occupancy = ceil(A / max_occupancy)`
3. Return `max(erlang_result, occupancy_floor)`

## API Surface (Draft)

```python
# Added optional parameter to existing function
agents_required(
    sla: float,
    service_time: int,
    calls_per_hour: float,
    aht: int,
    max_occupancy: float = None  # None = no cap (current behavior)
) -> int

# Standalone utility
occupancy(agents: int, calls_per_hour: float, aht: int) -> float
# Returns current occupancy ratio (A/N)

# Check function
is_within_occupancy(
    agents: int,
    calls_per_hour: float,
    aht: int,
    max_occupancy: float
) -> bool
```

## Agnostic Behavior

- `max_occupancy=None` or omitted: identical to current behavior (no cap)
- `max_occupancy=0.85`: agents will be at most 85% occupied
- Follows the same pattern as Erlang A patience: user opts in, otherwise library behaves as before

## Industry Benchmarks

| Occupancy Range | Typical Use |
|----------------|-------------|
| 70-75% | Premium/high-touch operations |
| 75-80% | Standard voice operations |
| 80-85% | Efficient operations, experienced teams |
| 85-90% | High-volume, short AHT operations |
| 90%+ | Generally unsustainable, high attrition risk |

## Complexity

Low. This is a floor check on top of existing Erlang C output. No changes to core math.

## Dependencies

None. Can be implemented independently.
