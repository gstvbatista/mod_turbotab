---
name: mod-turbotab
description: "Use the mod_turbotab TurboTable-style CLI for contact-center Erlang, staffing, queue, SLA, and trunk calculations."
---

# mod_turbotab Skill

Use this skill when a user asks for contact-center planning, traffic analyst, Erlang, staffing, SLA, ASA, queue, or trunk capacity calculations.

## Tool

Use the `turbotab` CLI with `--json` as the primary interface.

```bash
turbotab --help
turbotab staffing required --sla 0.80 --service-time 20 --calls-per-interval 25 --aht 180 --json
```

If the package is not installed, install it from the repo checkout with `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Fallback when `uv` is unavailable:

```bash
python3 -m pip install -e .
```

## Unit Rules

- `calls_per_interval` means arrivals in the configured planning bucket.
- The default interval is `600` seconds, so default commands use 10-minute buckets.
- For hourly volumes, pass `--interval 3600`.
- `aht`, `service-time`, `patience`, and `interval` are seconds.
- SLA values are ratios, for example `0.80` for 80%.

When the user gives an arrival volume without a time bucket, ask whether it is per 10 minutes, per hour, or another interval before calculating.

## Recipes

Required agents:

```bash
turbotab staffing required --sla 0.80 --service-time 20 --calls-per-interval 25 --aht 180 --json
```

Achieved SLA:

```bash
turbotab sla achieved --agents 11 --service-time 20 --calls-per-interval 25 --aht 180 --json
```

Average queue wait:

```bash
turbotab queue wait --agents 11 --calls-per-interval 25 --aht 180 --json
```

Call capacity for a fixed staffing level:

```bash
turbotab staffing capacity --agents 11 --sla 0.80 --service-time 20 --aht 180 --json
```

Trunks required:

```bash
turbotab telecom trunks --agents 11 --calls-per-interval 25 --aht 180 --json
```

Erlang B:

```bash
turbotab erlang b --servers 10 --intensity 8 --json
```

Erlang A with abandonment:

```bash
turbotab erlang a --servers 10 --intensity 8 --patience 60 --aht 180 --target-time 20 --json
```

## Output Handling

Parse the JSON object and report:

- `schema_version`: output contract version.
- `calculation`: command family and metric.
- `inputs`: normalized input values used by the calculation.
- `result.name`: metric name.
- `result.value`: numeric result.
- `result.unit`: result unit or ratio.

Do not scrape human text output when `--json` is available.
Do not import Python internals when the CLI can answer the user request.

## Guardrails

- Explain assumptions when converting between hourly and interval volumes.
- Do not present results as exact operational guarantees; these are queueing model estimates.
- Mention Erlang A only when caller abandonment/patience is relevant or requested.
- Do not change formulas or hard-coded thresholds from the CLI. If a threshold is not exposed, say it is not currently configurable.
