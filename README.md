# mod_turbotab

CLI-first TurboTable-style calculations for contact-center planning.

`mod_turbotab` keeps the historical name known by call-center planning and traffic analysts, while exposing `turbotab` as the primary interface for humans, scripts, and AI agents.

```bash
turbotab staffing required --sla 0.80 --service-time 20 --calls-per-interval 25 --aht 180 --json
```

```json
{"calculation": "staffing.required", "inputs": {"aht": 180, "calls_per_interval": 25.0, "interval": 600.0, "service_time": 20, "sla": 0.8}, "result": {"name": "agents", "unit": "agents", "value": 11}, "schema_version": "1.0"}
```

## Why

`mod_turbotab` answers operational questions that show up constantly in contact-center planning:

| Question | Command |
|---|---|
| How many agents do I need? | `turbotab staffing required ...` |
| What SLA will this staffing achieve? | `turbotab sla achieved ...` |
| How long will the queue wait be? | `turbotab queue wait ...` |
| How many trunks are required? | `turbotab telecom trunks ...` |
| What is the Erlang B/C/A result? | `turbotab erlang ...` |

It provides Erlang B, extended Erlang B, Engset B, Erlang C, Erlang A, queue metrics, staffing metrics, call capacity, and telephony trunk sizing with no third-party runtime dependencies.

## Install

Recommended local install with `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
turbotab --version
```

Fallback with standard Python tooling:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Names:

| Surface | Name |
|---|---|
| Python distribution | `mod-turbotab` |
| Python import | `mod_turbotab` |
| CLI command | `turbotab` |
| Agent skill | `skills/mod-turbotab/SKILL.md` |

## Quick Start

Required staffing for 80% SLA in 20 seconds:

```bash
turbotab staffing required \
  --sla 0.80 \
  --service-time 20 \
  --calls-per-interval 25 \
  --aht 180 \
  --json
```

Achieved SLA for a fixed staffing level:

```bash
turbotab sla achieved \
  --agents 11 \
  --service-time 20 \
  --calls-per-interval 25 \
  --aht 180 \
  --json
```

Average queue wait:

```bash
turbotab queue wait \
  --agents 11 \
  --calls-per-interval 25 \
  --aht 180 \
  --json
```

Required trunks:

```bash
turbotab telecom trunks \
  --agents 11 \
  --calls-per-interval 25 \
  --aht 180 \
  --json
```

Every command group falls back to contextual help:

```bash
turbotab
turbotab sla
turbotab staffing required --help
```

## CLI

Agent-facing commands are intent-first:

```text
turbotab
├── staffing
│   ├── required
│   ├── asa
│   ├── capacity
│   ├── fractional-required
│   └── fractional-capacity
├── sla
│   ├── achieved
│   └── target-time
├── queue
│   ├── wait
│   ├── size
│   └── probability
└── telecom
    └── trunks
```

Detailed formula/module commands are also available:

```text
turbotab agents ...
turbotab queues ...
turbotab erlang ...
turbotab traffic ...
turbotab trunks ...
```

Use `--json` when calling from agents or automation. Invalid inputs exit non-zero and print a concise error to stderr.

<details>
<summary>Agent usage</summary>

Agents should prefer the CLI with `--json` instead of parsing text output or importing Python internals.

```bash
turbotab staffing required --sla 0.80 --service-time 20 --calls-per-interval 25 --aht 180 --json
```

JSON output is the stable agent contract:

```json
{
  "schema_version": "1.0",
  "calculation": "staffing.required",
  "inputs": {
    "aht": 180,
    "calls_per_interval": 25.0,
    "interval": 600.0,
    "service_time": 20,
    "sla": 0.8
  },
  "result": {
    "name": "agents",
    "unit": "agents",
    "value": 11
  }
}
```

The bundled skill lives at [`skills/mod-turbotab/SKILL.md`](skills/mod-turbotab/SKILL.md). It includes command recipes, unit rules, and agent guardrails.

</details>

<details>
<summary>Units and assumptions</summary>

This project uses interval-based planning buckets.

Every function or CLI command that accepts call volume uses `calls_per_interval`, not calls per hour by default.

| Parameter | Meaning |
|---|---|
| `calls_per_interval` / `--calls-per-interval` | Arrivals in the planning bucket |
| `interval` / `--interval` | Planning bucket in seconds |
| Default `interval` | `600` seconds, or 10 minutes |
| `aht` / `--aht` | Average handle time in seconds |
| `service_time` / `--service-time` | Target answer time in seconds |
| `sla` / `--sla` | Ratio, for example `0.80` for 80% |

For hourly semantics, pass `--interval 3600`:

```bash
turbotab staffing required --sla 0.80 --service-time 20 --calls-per-interval 150 --aht 180 --interval 3600 --json
```

Traffic intensity is computed as:

```math
A = \frac{\lambda \cdot h}{I}
```

where `A` is offered traffic in erlangs, `lambda` is arrivals per interval, `h` is AHT in seconds, and `I` is interval length in seconds.

</details>

<details>
<summary>Worked example</summary>

With the default 10-minute bucket:

| Input | Value |
|---|---|
| Calls | `25` per 10 minutes |
| AHT | `180` seconds |
| Target SLA | `0.80` |
| Target answer time | `20` seconds |

CLI:

```bash
turbotab staffing required --sla 0.80 --service-time 20 --calls-per-interval 25 --aht 180 --json
turbotab sla achieved --agents 11 --service-time 20 --calls-per-interval 25 --aht 180 --json
turbotab queue wait --agents 11 --calls-per-interval 25 --aht 180 --json
turbotab telecom trunks --agents 11 --calls-per-interval 25 --aht 180 --json
```

Expected headline results:

| Metric | Result |
|---|---:|
| Required agents | `11` |
| Achieved SLA | `0.880836` |
| Average queue wait | `51` seconds |
| Required trunks | `18` |

Python API equivalent:

```python
from mod_turbotab.agents.capacity import agents_required

print(agents_required(0.80, 20, 25, 180))
```

</details>

<details>
<summary>Mathematical model</summary>

Notation:

| Symbol | Meaning |
|---|---|
| `N` | Agents, servers, or trunks depending on context |
| `lambda` | Arrival volume per configured interval |
| `h` | Average handle time in seconds |
| `I` | Planning interval in seconds |
| `mu` | Service completions per interval per server |
| `A` | Offered traffic in erlangs |
| `rho` | Utilization |
| `B(N, A)` | Erlang B blocking probability |
| `C(N, A)` | Erlang C queueing probability |

Core conversions:

```math
\mu = \frac{I}{h}
```

```math
A = \frac{\lambda}{\mu} = \frac{\lambda h}{I}
```

```math
\rho = \frac{A}{N}
```

Erlang B recurrence:

```math
B_0 = 1
```

```math
B_n = \frac{A B_{n-1}}{n + A B_{n-1}}
```

Erlang C:

```math
C(N, A) = \frac{B(N, A)}{\left(\frac{A}{N}\right) B(N, A) + \left(1 - \frac{A}{N}\right)}
```

Queue wait:

```math
W_q = \frac{1}{N \mu (1 - \rho)}
```

SLA:

```math
\mathrm{SLA}(t) = 1 - C(N, A)\exp\left(-\frac{N - A}{h}t\right)
```

ASA:

```math
\mathrm{ASA} = \frac{C(N, A)}{N \mu (1 - \rho)}
```

Erlang A extends Erlang C with abandonment through average patience. When `patience=None`, pure Erlang C is used.

</details>

<details>
<summary>API reference</summary>

The CLI is the primary interface, but the Python API remains available.

| Module | Public functions |
|---|---|
| `calculations.erlang` | `erlang_b`, `erlang_b_ext`, `engset_b`, `erlang_c`, `erlang_a` |
| `calculations.traffic` | `traffic`, `looping_traffic` |
| `agents.capacity` | `agents_required`, `asa`, `agents_asa`, `nb_agents`, `call_capacity`, `fractional_agents`, `fractional_call_capacity` |
| `queues.queues` | `queued`, `queue_size`, `queue_time`, `service_time`, `sla_metric` |
| `trunks.trunks` | `number_trunks`, `trunks_required` |
| `utils` | `min_max`, `int_ceiling`, `secs` |

Import example:

```python
from mod_turbotab.agents.capacity import agents_required

agents = agents_required(
    sla=0.80,
    service_time=20,
    calls_per_interval=25,
    aht=180,
)
```

</details>

<details>
<summary>Exceptions</summary>

Project-specific exceptions live in [`exceptions.py`](exceptions.py):

| Exception | Meaning |
|---|---|
| `InputValidationError` | Invalid argument values |
| `CalculationError` | Calculation failed or search could not converge |

Example:

```python
from mod_turbotab.exceptions import CalculationError, InputValidationError

try:
    ...
except InputValidationError:
    ...
except CalculationError:
    ...
```

</details>

## Project Layout

```text
mod_turbotab/
├── cli.py
├── pyproject.toml
├── agents/
├── calculations/
├── queues/
├── trunks/
├── skills/
├── tests/
├── exceptions.py
└── utils.py
```

## Limitations

- `number_trunks()` uses a fixed blocking threshold of `0.001`.
- Some zero-value edge cases still return wrapped calculation errors instead of purpose-built validation messages.
- Shrinkage, absenteeism, occupancy caps, and intraday simulation are tracked as future work in [`coming_soon/`](coming_soon/).

## Development

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
.venv/bin/python -m unittest discover -s tests
```

## License

MIT. See [`LICENSE`](LICENSE).
