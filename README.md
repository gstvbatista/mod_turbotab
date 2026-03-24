# mod_turbotab

`mod_turbotab` is a pure-Python telecom and contact-center capacity library built around Erlang-style queueing formulas.

It provides:

- Erlang B, extended Erlang B, Engset B, and Erlang C calculations
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

The library uses a global planning interval defined in [`config.py`](config.py):

```python
INTERVAL = 600.0
```

That means the default model works in **600-second buckets** (10 minutes).

Several function arguments are named `calls_per_hour`, but the implementation actually uses:

```math
A = \frac{\lambda \cdot \mathrm{AHT}}{\mathrm{INTERVAL}}
```

where:

- `A` = offered traffic in erlangs
- `lambda` = arrival volume per configured interval
- `AHT` = average handle time in seconds
- `INTERVAL` = default `600` seconds

So, with the code exactly as it exists today:

- if `INTERVAL = 600`, interpret `calls_per_hour` as "calls per 10-minute interval"
- if you want true hourly semantics, either:
  - convert hourly arrivals into the configured interval before calling the functions, or
  - change `INTERVAL` in `config.py` before using the package

## Mathematical Model

### Notation

Throughout the README:

- `N` = number of agents, servers, or trunks depending on the function
- `lambda` = arrival volume per configured interval
- `h` = average handle time (`AHT`) in seconds
- `I` = configured interval in seconds (`INTERVAL`)
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

### Queue wait time and SLA

For a given number of agents:

```math
W_q = \frac{1}{N \mu (1 - \rho)}
```

The implementation then converts `W_q` back into seconds by multiplying by `INTERVAL`.

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

and is returned in seconds after multiplying by `INTERVAL` and rounding.

## Worked Example

With the repository in its current default configuration:

- `INTERVAL = 600`
- calls are interpreted per 10-minute bucket

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

calls = 25          # per INTERVAL, not per clock hour when INTERVAL=600
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
```

Observed output with the current code:

```text
agents_required: 11
asa: 9
queued: 0.175807
queue_time: 51
sla_metric: 0.880836
service_time for 90% SLA: 22
call_capacity: 27.0
fractional_agents: 10.2852
trunks_required: 18
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

#### `queued(agents, calls_per_hour, aht) -> float`

Returns the fraction of arrivals that queue.

Formula:

```math
\mathrm{queued} = C(N, A)
```

#### `queue_size(agents, calls_per_hour, aht) -> int`

Returns the mean queue size, rounded to the nearest integer.

Formula:

```math
Q = \frac{\rho C(N, A)}{1 - \rho}
```

#### `queue_time(agents, calls_per_hour, aht) -> int`

Returns mean waiting time in seconds.

Formula:

```math
W_q = \frac{1}{N \mu (1 - \rho)}
```

Returned value:

```math
\mathrm{queue\_time\_seconds} = \mathrm{round}(W_q \cdot I)
```

#### `service_time(agents, sla, calls_per_hour, aht) -> int`

Returns the answer-time threshold required to meet a desired SLA for a fixed staffing level.

Important: the current implementation uses the following approximation rather than solving the `sla_metric()` equation exactly:

```math
qtime = \frac{I}{N \mu (1 - \rho)}
```

```math
t \approx qtime \left(1 - \frac{1 - \mathrm{SLA}}{C(N, A)}\right)
```

This function raises `CalculationError` when the requested SLA is already satisfied without queueing pressure.

#### `sla_metric(agents, service_time_val, calls_per_hour, aht) -> float`

Returns achieved service level for a target answer time.

Formula:

```math
\mathrm{SLA}(t) = 1 - C(N, A)\exp\left(\frac{A - N}{h} t\right)
```

### `agents.capacity`

#### `agents_required(sla, service_time, calls_per_hour, aht) -> int`

Returns the smallest integer number of agents such that:

```math
\mathrm{SLA}(t) \ge \mathrm{target\_sla}
```

The function begins near the offered load:

```math
N_0 \approx \max(1, \mathrm{round}(A))
```

and then increases `N` until the SLA condition is met.

#### `asa(agents, calls_per_hour, aht) -> int`

Returns ASA in seconds.

Formula:

```math
\mathrm{ASA} = \frac{C(N, A)}{N \mu (1 - \rho)}
```

#### `agents_asa(asa_target, calls_per_hour, aht) -> int`

Returns the smallest integer number of agents such that:

```math
\mathrm{ASA}(N) \le \mathrm{asa\_target}
```

#### `nb_agents(calls_ph, avg_sa, avg_ht) -> int`

Brute-force search over agent counts until:

```math
\mathrm{ASA}(N) \le \mathrm{avg\_sa}
```

#### `call_capacity(no_agents, sla, service_time, aht) -> float`

Approximates the largest call volume supported by a fixed integer staffing level while meeting the SLA target.

Algorithm:

1. Start from a saturation-style upper bound:

```math
\lambda_{start} = \left\lceil \frac{I}{h} \right\rceil N
```

2. Recompute `agents_required(...)`.
3. Decrease call volume until the required agent count no longer exceeds `no_agents`.

#### `fractional_agents(sla, service_time, calls_per_hour, aht) -> float`

Returns a fractional staffing estimate by linearly interpolating between the last staffing level below target and the first staffing level above target.

Interpolation used by the code:

```math
N_{frac} = (N - 1) + \frac{\mathrm{SLA}_{target} - \mathrm{SLA}_{prev}}{\mathrm{SLA}_{curr} - \mathrm{SLA}_{prev}}
```

#### `fractional_call_capacity(no_agents, sla, service_time, aht) -> float`

Like `call_capacity`, but uses `fractional_agents(...)` during the inverse search.

### `trunks.trunks`

#### `number_trunks(servers, intensity) -> int`

Returns the smallest integer number of trunks with blocking below a hard-coded threshold of `0.001`.

Condition:

```math
B(T, A) < 0.001
```

where `T >= ceil(servers)`.

#### `trunks_required(agents, calls_per_hour, aht) -> int`

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

### `config`

Current global constants:

```python
INTERVAL = 600.0
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
├── queues/
│   └── queues.py
├── trunks/
│   └── trunks.py
├── config.py
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
- Function names such as `calls_per_hour` are misleading unless `INTERVAL` is changed to `3600`.
- Some zero-value edge cases are not handled cleanly. For example, `agents=0` or `servers=0` may lead to wrapped runtime errors rather than a clean validation failure.
- `number_trunks()` uses a fixed blocking threshold of `0.001`; it is not configurable.
- `service_time()` uses an approximation, not the exact inverse of `sla_metric()`.
- `agents_asa()` increments staffing during its search but does not recompute utilization inside the loop, so treat it cautiously until corrected.

## Summary

`mod_turbotab` is a compact Erlang-based planning library with solid building blocks for queueing, staffing, SLA, ASA, traffic intensity, and trunk sizing. The codebase is small enough to understand quickly, and the formulas above map directly to what the repository actually computes today.
