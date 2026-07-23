# AGENTS.md

<mission>
You are working in the `mod_turbotab` repository.

`mod_turbotab` is a pure-Python telecom and contact-center capacity library,
exposed primarily through the `turbotab` CLI. It implements Erlang-style
queueing formulas, staffing calculations, queue metrics, and trunk sizing
helpers, with `--json` output designed for scripts and AI agents as much as
humans.
</mission>

<workspace>
- Repository: `https://github.com/gstvbatista/mod_turbotab`
- Default branch: `main`
- Runtime: Python >= 3.9
- Runtime dependencies: none
- Packaging: `pyproject.toml`, published on PyPI as `turbotab`
  (`pip install turbotab`), console script `turbotab -> mod_turbotab.cli:main`
</workspace>

<repository-map>
- `cli.py`: the `turbotab` CLI entry point (argument parsing, command groups,
  `--json` output).
- `calculations/erlang.py`: Erlang B, extended Erlang B, Engset B, Erlang C,
  and Erlang A helpers.
- `calculations/traffic.py`: inversion/search helpers for traffic intensity.
- `agents/capacity.py`: staffing, ASA, call capacity, and fractional staffing
  calculations.
- `queues/queues.py`: queued percentage, queue size, wait time, service time,
  and achieved SLA metrics.
- `trunks/trunks.py`: telephony trunk sizing calculations.
- `utils.py`: small numeric helpers such as clamping, ceiling, and interval
  conversion.
- `exceptions.py`: project-specific exception classes.
- `tests/test_cli.py`: CLI behavior tests (`python3 -m unittest discover -s tests`).
- `skills/mod-turbotab/SKILL.md`: agent-facing skill definition for the
  `turbotab` CLI.
- `README.md`: primary user-facing API and mathematical model documentation.
- Roadmap items (multi-skill Erlang C, occupancy cap, shrinkage/absenteeism,
  intraday simulation) are tracked as GitHub issues labeled `roadmap`, not as
  files in this repo.
</repository-map>

<working-rules>
- Keep changes scoped to the Python library/CLI surface, tests, and README
  unless the task explicitly asks for packaging, CI, or release work.
- Preserve public API and CLI flag names already documented in `README.md`
  unless a breaking-change discussion has happened first.
- Treat units carefully: call volumes are `calls_per_interval`; the default
  `interval` is `600.0` seconds, so default examples are 10-minute buckets.
- Prefer small, isolated changes. Shared formula changes can affect agents,
  queues, and trunks behavior at once.
- Do not add third-party runtime dependencies without explicit approval.
- This repository does not accept external pull requests (see
  `CONTRIBUTING.md`); external PRs are auto-closed by
  `.github/workflows/close-prs.yml`.
</working-rules>

<code-style>
- Existing source uses type hints, module docstrings in Portuguese, and
  project-specific exceptions for validation/calculation failures.
- Prefer clear mathematical variable names that match the README terminology:
  `traffic_rate`, `birth_rate`, `death_rate`, `utilisation`, `sla`, `aht`, and
  `interval`.
- Keep docstrings consistent with nearby code. Portuguese is acceptable and
  currently predominant in source docstrings; README and CLI help text are in
  English.
- Avoid broad refactors when fixing formulas. Make the smallest change that
  can be validated.
</code-style>

<validation>
Run the test suite from the repository root:

```bash
python3 -m unittest discover -s tests
```

For a quick manual check of a specific calculation:

```bash
python3 -c "from mod_turbotab.agents.capacity import agents_required; print(agents_required(0.80, 20, 25, 180))"
```

For behavioral changes, add or update a focused test in `tests/test_cli.py`
(or a new test module) covering the changed public function or CLI command.

Before finishing, run `git status --short` and confirm only the intended
files are staged.
</validation>

## Code Review Rules

- Flag any change to a formula in `calculations/`, `agents/capacity.py`,
  `queues/queues.py`, or `trunks/trunks.py` that isn't accompanied by a test
  exercising the new behavior.
- Check edge cases explicitly: zero/negative inputs, overloaded systems
  (utilisation >= 1), and Erlang A patience/abandonment behavior — these are
  the historical failure points in this kind of library.
- Verify unit consistency across a change (seconds vs. intervals, `aht` vs.
  `service_time`) since several modules share the same traffic assumptions.
- If a CLI flag or output field is renamed or removed, confirm the README
  examples were updated to match.
- Do not flag missing third-party dependency pinning — this project
  intentionally has zero runtime dependencies.

<future-work-notes>
- Roadmap items live as GitHub issues labeled `roadmap`, not markdown files
  in the repo. When picking up one of these, read the linked issue for the
  full problem/approach writeup before implementing.
- Several modules share traffic/unit assumptions. When changing one formula,
  inspect the related queue, capacity, and README documentation paths.
</future-work-notes>
