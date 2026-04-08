# mod_turbotab

`mod_turbotab` is a pure-Python telecom and contact-center capacity library built around Erlang-style queueing formulas.

It provides:

- Erlang B, extended Erlang B, Engset B, Erlang C, and Erlang A (abandonment) calculations
- Queueing metrics such as queued percentage, queue size, queue wait time, and achieved SLA
- Staffing metrics such as required agents, ASA, and call capacity
- Trunk sizing utilities for telephony capacity planning
- No third-party runtime dependencies

The repository is intentionally small: it is a library package, not a CLI or web app.

## Contents

- [What This Library Models](#what-this-library-models)
- [Importing The Package](#importing-the-package)
- [Units And Core Assumptions](#units-and-core-assumptions)
- [Mathematical Model](#mathematical-model)
- [Worked Example](#worked-example)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Exceptions](#exceptions)
- [Current Limitations](#current-limitations)

## What This Library Models

The codebase models a classic queueing and telephony planning problem:

1. Convert offered workload into traffic intensity.
2. Use Erlang formulas to estimate blocking or queueing.
3. Derive operational decisions from that model:
   - How many agents are required?
   - What ASA will that staffing level produce?
   - What SLA is achievable for a target answer time?
   - How many trunks are needed to keep blocking below a threshold?

In practice this is useful for:

- contact-center workforce planning
- SLA and queue analysis
- inbound telephony trunk sizing
- "what-if" capacity simulations

## Importing The Package

This repository does not currently include `pyproject.toml`, `setup.py`, or a published package configuration. Use it as a source package by placing the parent directory on `PYTHONPATH`.

Example:

```bash
git clone <repo-url>
cd /path/to/parent/of/mod_turbotab
python3 - <<'PY'
from mod_turbotab.agents.capacity import agents_required

print(agents_required(0.80, 20, 25, 180))
PY
```

Or:

```bash
export PYTHONPATH=/path/to/parent/of/mod_turbotab_parent
python3 your_script.py
```

## Units And Core Assumptions

This section matters more than anything else in the README.

Every function that works with call volumes accepts an `interval` parameter (default `600.0` — 10 minutes). This defines the planning bucket size in seconds.

All functions that accept a volume parameter use `calls_per_interval` — the number of arrivals per interval:

```math
A = \frac{\lambda \cdot \mathrm{AHT}}{\mathrm{interval}}
```

where:

- `A` = offered traffic in erlangs
- `lambda` = arrival volume per interval
- `AHT` = average handle time in seconds
- `interval` = planning bucket in seconds (default `600`)

With the default `interval=600`, pass the number of calls per 10-minute bucket. For hourly semantics, pass `interval=3600`:

```python
# 10-minute buckets (default)
agents_required(0.80, 20, 25, 180)

# Hourly buckets
agents_required(0.80, 20, 150, 180, interval=3600)
```

## Mathematical Model

### Notation

Throughout the README:

- `N` = number of agents, servers, or trunks depending on the function
- `lambda` = arrival volume per configured interval
- `h` = average handle time (`AHT`) in seconds
- `I` = interval in seconds (function parameter, default `600`)
- `mu` = service completions per interval per server
- `A` = offered traffic in erlangs
- `rho` = utilization
- `B(N, A)` = Erlang B blocking probability
- `C(N, A)` = Erlang C queueing probability

The library computes:

```math
\mu = \frac{I}{h}
```

```math
A = \frac{\lambda}{\mu} = \frac{\lambda h}{I}
```

```math
\rho = \frac{A}{N}
```

### Erlang B

The implementation uses the numerically stable recurrence:

```math
B_0 = 1
```

```math
B_n = \frac{A B_{n-1}}{n + A B_{n-1}}
```

After iterating up to `n = N`, the function returns `B_N`.

### Extended Erlang B

The retry-aware variant inflates effective offered traffic by the retry factor `r` at each iteration. In code, the recurrence is implemented as:

```math
b_n^{basic} = \frac{A B_{n-1}}{n + A B_{n-1}}
```

```math
\alpha_n = \frac{1}{1 - r b_n^{basic}}
```

```math
B_n^{ext} = \frac{A B_{n-1} \alpha_n}{n + A B_{n-1} \alpha_n}
```

This is useful when a blocked caller may retry.

### Engset B

The Engset-style blocking calculation is implemented through this recurrence:

```math
x_0 = 1
```

```math
x_n = 1 + x_{n-1} \cdot \frac{n}{(E - n) a}
```

```math
B_{Engset} = \frac{1}{x_N}
```

where:

- `E` = number of sources/events
- `a` = per-source intensity

### Erlang C

The queueing probability is derived from Erlang B:

```math
C(N, A) = \frac{B(N, A)}{\left(\frac{A}{N}\right) B(N, A) + \left(1 - \frac{A}{N}\right)}
```

This is the probability that an arrival has to wait.

### Erlang A (Abandonment)

The Erlang A model (M/M/N+M) extends Erlang C by modeling caller patience. Callers who wait beyond their patience threshold abandon the queue with rate `θ = 1/patience`.

Key metrics:

- **Probability of waiting:** adjusted from Erlang C using abandonment rate
- **ASA:** reduced by abandonment (impatient callers leave, shortening the queue)
- **Abandon rate:** `P(abandon) = P(wait) · (1 - e^(-θ · expected_wait))`
- **SLA:** `SLA(t) = 1 - P(wait) · min(e^((A-N)/h · t), e^(-θ · t))`

All functions that support Erlang A accept an optional `patience` parameter (in seconds). When `patience=None` (default), pure Erlang C is used.

### Queue wait time and SLA

For a given number of agents:

```math
W_q = \frac{1}{N \mu (1 - \rho)}
```

The implementation then converts `W_q` back into seconds by multiplying by `interval`.

The SLA function implemented in the code is:

```math
\mathrm{SLA}(t) = 1 - C(N, A) \exp\left(\frac{A - N}{h} t\right)
```

Equivalent form:

```math
\mathrm{SLA}(t) = 1 - C(N, A) \exp\left(-\frac{N - A}{h} t\right)
```

### ASA

Average Speed of Answer is implemented as:

```math
\mathrm{ASA} = \frac{C(N, A)}{N \mu (1 - \rho)}
```

and is returned in seconds after multiplying by `interval` and rounding.

## Worked Example

With the default `interval=600` (10-minute buckets):

Example inputs:

- arrivals: `25`
- `AHT`: `180` seconds
- target SLA: `0.80`
- target answer time: `20` seconds

Example script:

```python
from mod_turbotab.agents.capacity import (
    agents_required,
    asa,
    call_capacity,
    fractional_agents,
)
from mod_turbotab.queues.queues import queued, queue_time, sla_metric, service_time
from mod_turbotab.trunks.trunks import trunks_required

calls = 25          # per 10-minute bucket (default interval=600)
aht = 180           # seconds
sla = 0.80
target_time = 20    # seconds

agents = agents_required(sla, target_time, calls, aht)

print("agents_required:", agents)
print("asa:", asa(agents, calls, aht))
print("queued:", round(queued(agents, calls, aht), 6))
print("queue_time:", queue_time(agents, calls, aht))
print("sla_metric:", round(sla_metric(agents, target_time, calls, aht), 6))
print("service_time for 90% SLA:", service_time(agents, 0.90, calls, aht))
print("call_capacity:", call_capacity(agents, sla, target_time, aht))
print("fractional_agents:", round(fractional_agents(sla, target_time, calls, aht), 4))
print("trunks_required:", trunks_required(agents, calls, aht))

# Erlang A — with 60s average patience
from mod_turbotab.calculations.erlang import erlang_a

agents_patience = agents_required(sla, target_time, calls, aht, patience=60)
print("\n--- Erlang A (patience=60s) ---")
print("agents_required:", agents_patience)
print("asa:", asa(agents_patience, calls, aht, patience=60))
print("sla_metric:", round(sla_metric(agents_patience, target_time, calls, aht, patience=60), 6))
```

Observed output:

```text
agents_required: 11
asa: 9
queued: 0.175807
queue_time: 51
sla_metric: 0.880836
service_time for 90% SLA: 29
call_capacity: 27.0
fractional_agents: 10.2852
trunks_required: 18

--- Erlang A (patience=60s) ---
agents_required: 11
asa: 5
sla_metric: 0.880836
```

## API Reference

### `calculations.erlang`

#### `erlang_b(servers, intensity) -> float`

Returns the blocking probability for `servers` and offered traffic `intensity`.

Formula:

```math
B_N = \frac{A B_{N-1}}{N + A B_{N-1}}
```

using the recurrence defined above.

#### `erlang_b_ext(servers, intensity, retry) -> float`

Returns retry-adjusted blocking probability.

Use this when a blocked customer may immediately reattempt.

#### `engset_b(servers, events, intensity) -> float`

Returns blocking probability using the Engset model for finite populations.

#### `erlang_c(servers, intensity) -> float`

Returns the probability that an arrival must wait in queue.

Formula:

```math
C(N, A) = \frac{B(N, A)}{\left(\frac{A}{N}\right) B(N, A) + \left(1 - \frac{A}{N}\right)}
```

#### `erlang_a(servers, intensity, patience, aht) -> dict`

Returns a dictionary with Erlang A (M/M/N+M) abandonment metrics:

- `pw` — probability of waiting (adjusted for abandonment)
- `asa` — average speed of answer in seconds
- `abandon_rate` — fraction of calls that abandon
- `sla` — callable `sla(t)` returning the SLA achieved at target time `t`

### `calculations.traffic`

#### `traffic(servers, blocking) -> float`

Numerically inverts Erlang B.

It searches for traffic intensity `A` such that:

```math
B(N, A) \approx \mathrm{blocking}
```

The search is iterative and stops when the increment falls below `MAX_ACCURACY` or loop limits are reached.

#### `looping_traffic(...) -> float`

Internal helper used by `traffic()` to refine the search interval.

### `queues.queues`

#### `queued(agents, calls_per_interval, aht, interval=600.0, patience=None) -> float`

Returns the fraction of arrivals that queue.

Formula:

```math
\mathrm{queued} = C(N, A)
```

#### `queue_size(agents, calls_per_interval, aht, interval=600.0, patience=None) -> int`

Returns the mean queue size, rounded to the nearest integer.

Formula:

```math
Q = \frac{\rho C(N, A)}{1 - \rho}
```

#### `queue_time(agents, calls_per_interval, aht, interval=600.0, patience=None) -> int`

Returns mean waiting time in seconds.

Formula:

```math
W_q = \frac{1}{N \mu (1 - \rho)}
```

Returned value:

```math
\mathrm{queue\_time\_seconds} = \mathrm{round}(W_q \cdot I)
```

#### `service_time(agents, sla, calls_per_interval, aht, interval=600.0, patience=None) -> int`

Returns the answer-time threshold required to meet a desired SLA for a fixed staffing level.

Uses the exact algebraic inverse of `sla_metric()`:

```math
t = \frac{h \cdot \ln\left(\frac{1 - \mathrm{SLA}}{C(N, A)}\right)}{A - N}
```

When `patience` is provided, uses binary search over the Erlang A SLA function instead.

Returns `0` when the SLA is already met without queueing pressure. Raises `CalculationError` when the system is overloaded (`A >= N`).

#### `sla_metric(agents, service_time_val, calls_per_interval, aht, interval=600.0, patience=None) -> float`

Returns achieved service level for a target answer time.

Formula:

```math
\mathrm{SLA}(t) = 1 - C(N, A)\exp\left(\frac{A - N}{h} t\right)
```

### `agents.capacity`

#### `agents_required(sla, service_time, calls_per_interval, aht, interval=600.0, patience=None) -> int`

Returns the smallest integer number of agents such that:

```math
\mathrm{SLA}(t) \ge \mathrm{target\_sla}
```

Uses binary search with a doubling upper bound for O(log N) performance. When `patience` is provided, uses Erlang A instead of Erlang C for the SLA check.

#### `asa(agents, calls_per_interval, aht, interval=600.0, patience=None) -> int`

Returns ASA in seconds.

Formula:

```math
\mathrm{ASA} = \frac{C(N, A)}{N \mu (1 - \rho)}
```

#### `agents_asa(asa_target, calls_per_interval, aht, interval=600.0) -> int`

Returns the smallest integer number of agents such that:

```math
\mathrm{ASA}(N) \le \mathrm{asa\_target}
```

Uses binary search with a doubling upper bound.

#### `nb_agents(calls_per_interval, avg_sa, avg_ht, interval=600.0) -> int`

Returns the smallest integer number of agents such that:

```math
\mathrm{ASA}(N) \le \mathrm{avg\_sa}
```

Uses binary search with a doubling upper bound.

#### `call_capacity(no_agents, sla, service_time, aht, interval=600.0) -> float`

Approximates the largest call volume supported by a fixed integer staffing level while meeting the SLA target.

Algorithm:

1. Start from a saturation-style upper bound:

```math
\lambda_{start} = \left\lceil \frac{I}{h} \right\rceil N
```

2. Recompute `agents_required(...)`.
3. Decrease call volume until the required agent count no longer exceeds `no_agents`.

#### `fractional_agents(sla, service_time, calls_per_interval, aht, interval=600.0, patience=None) -> float`

Returns a fractional staffing estimate by linearly interpolating between the last staffing level below target and the first staffing level above target.

Interpolation used by the code:

```math
N_{frac} = (N - 1) + \frac{\mathrm{SLA}_{target} - \mathrm{SLA}_{prev}}{\mathrm{SLA}_{curr} - \mathrm{SLA}_{prev}}
```

#### `fractional_call_capacity(no_agents, sla, service_time, aht, interval=600.0) -> float`

Like `call_capacity`, but uses `fractional_agents(...)` during the inverse search.

### `trunks.trunks`

#### `number_trunks(servers, intensity) -> int`

Returns the smallest integer number of trunks with blocking below a hard-coded threshold of `0.001`.

Condition:

```math
B(T, A) < 0.001
```

where `T >= ceil(servers)`.

#### `trunks_required(agents, calls_per_interval, aht, interval=600.0) -> int`

Estimates telephony trunks needed for a staffed system.

The implementation:

1. Computes Erlang C queueing probability.
2. Computes ASA.
3. Converts talk time plus waiting time into effective carried traffic:

```math
R \approx \frac{\lambda (h + \mathrm{ASA})}{I}
```

In the current code the ASA component is rounded to integer seconds before being reused.

4. Finds the smallest trunk count satisfying:

```math
B(T, R) < 0.001
```

### `utils`

#### `min_max(val, min_val, max_val) -> float`

Clamps a value into a closed interval.

#### `int_ceiling(val) -> int`

Implements a lightweight ceiling-like conversion.

#### `secs(amount, interval=600.0) -> int`

Converts interval-based time into seconds:

```math
\mathrm{secs}(x) = \mathrm{round}(x \cdot \mathrm{interval})
```

### Internal constants

The following constants are defined locally in `calculations/traffic.py` and control the iterative search convergence:

```python
MAX_ACCURACY = 0.00001
MAX_LOOPS = 100
```

## Project Structure

```text
mod_turbotab/
├── agents/
│   └── capacity.py
├── calculations/
│   ├── erlang.py
│   └── traffic.py
├── coming_soon/
│   ├── intraday_simulation.md
│   ├── multi_skill_erlang_c.md
│   ├── occupancy_cap.md
│   └── shrinkage_absenteeism.md
├── queues/
│   └── queues.py
├── trunks/
│   └── trunks.py
├── exceptions.py
└── utils.py
```

## Exceptions

The package defines two custom exceptions in [`exceptions.py`](exceptions.py):

- `InputValidationError`: raised for invalid argument values
- `CalculationError`: raised when a computation fails or a search cannot converge to a valid result

A practical pattern is:

```python
from mod_turbotab.exceptions import InputValidationError, CalculationError

try:
    ...
except InputValidationError:
    ...
except CalculationError:
    ...
```

## Current Limitations

These are worth knowing before you build on top of the library:

- The package is not yet packaged for installation with `pip`.
- Some zero-value edge cases are not handled cleanly. For example, `agents=0` or `servers=0` may lead to wrapped runtime errors rather than a clean validation failure.
- `number_trunks()` uses a fixed blocking threshold of `0.001`; it is not configurable.
- No multi-skill routing model (see `coming_soon/multi_skill_erlang_c.md`).
- No shrinkage/absenteeism factor (see `coming_soon/shrinkage_absenteeism.md`).

## Summary

`mod_turbotab` is a compact Erlang-based planning library with building blocks for queueing, staffing, SLA, ASA, traffic intensity, trunk sizing, and abandonment modeling (Erlang A). The codebase is small enough to understand quickly, and the formulas above map directly to what the repository actually computes today.
