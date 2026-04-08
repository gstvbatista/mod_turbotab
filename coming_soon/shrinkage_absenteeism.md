# Shrinkage & Absenteeism Factor

## Problem

Erlang C calculates the number of agents needed **on the phones**. But not every scheduled agent is actually available — breaks, training, meetings, absenteeism, system downtime all reduce effective headcount. Operations teams always apply a shrinkage factor manually (typically 25-35%).

## What It Solves

- Bridges the gap between "agents needed on phones" and "agents to schedule"
- Makes the library output directly usable for workforce scheduling
- Eliminates manual spreadsheet adjustments

## How It Works

```
HC_scheduled = HC_required / (1 - shrinkage)
```

Where shrinkage is a percentage (0.0 to 1.0) representing unavailable time.

### Shrinkage Components (typical)

| Component | Typical % |
|-----------|-----------|
| Breaks (paid) | 5-8% |
| Training | 3-5% |
| Meetings | 2-3% |
| Absenteeism | 5-10% |
| System downtime | 1-2% |
| After-call work (if not in AHT) | 5-15% |
| **Total** | **20-40%** |

## API Surface (Draft)

```python
# Simple: single shrinkage factor
agents_required_with_shrinkage(
    sla: float,
    service_time: int,
    calls_per_hour: float,
    aht: int,
    shrinkage: float = 0.0  # 0.0 = no shrinkage (current behavior)
) -> int

# Advanced: component-based shrinkage
shrinkage_factor(
    breaks: float = 0.0,
    training: float = 0.0,
    meetings: float = 0.0,
    absenteeism: float = 0.0,
    system_downtime: float = 0.0,
    other: float = 0.0
) -> float  # combined shrinkage

# Wrapper
scheduled_agents(
    agents_on_phone: int,
    shrinkage: float
) -> int
```

## Design Decision: Where to Apply

Two approaches:

### Option A: Post-calculation adjustment (recommended)
- Calculate Erlang C normally, then divide by (1 - shrinkage)
- Simple, composable, doesn't change core math
- User controls when to apply it

### Option B: Baked into Erlang calculation
- Modify offered load to account for shrinkage
- Mathematically different result
- More accurate but less transparent

Recommend Option A for simplicity and transparency.

## Complexity

Low. This is essentially a multiplier on top of existing calculations. The value is in providing a standard interface so users don't reinvent it.

## Agnostic Behavior

- `shrinkage=0.0` or omitted: identical to current behavior
- `shrinkage > 0`: applies the factor
- Consistent with the library's pattern of optional enhancements
