# AGENTS.md

Guidance for AI agents (and humans) working in this repository.

## Project

`mod_turbotab` is a pure-Python telecom and contact-center capacity library,
exposed primarily through the `turbotab` CLI. It implements Erlang-style
queueing formulas, staffing calculations, queue metrics, and trunk sizing
helpers, with `--json` output designed for scripts and AI agents as much as
humans.

Key facts:

- Repository: `https://github.com/gstvbatista/mod_turbotab`, default branch `main`
- Runtime: Python >= 3.9, zero runtime dependencies (intentional)
- Published on PyPI as `turbotab` (`pip install turbotab`); console script
  `turbotab -> mod_turbotab.cli:main`
- The package root maps to the repo root (`package-dir` in `pyproject.toml`),
  so `import mod_turbotab` resolves from the repo's *parent* directory

## Repository map

| Path | Purpose |
|---|---|
| `cli.py` | `turbotab` CLI entry point: argument parsing, command groups, `--json` output |
| `calculations/erlang.py` | Erlang B, extended Erlang B, Engset B, Erlang C, Erlang A |
| `calculations/traffic.py` | Inversion/search helpers for traffic intensity |
| `agents/capacity.py` | Staffing, ASA, call capacity, fractional staffing |
| `queues/queues.py` | Queued percentage, queue size, wait time, service time, achieved SLA |
| `trunks/trunks.py` | Telephony trunk sizing |
| `utils.py` | Numeric helpers: clamping, ceiling, interval conversion |
| `exceptions.py` | Project-specific exception classes |
| `tests/test_cli.py` | CLI behavior tests |
| `skills/mod-turbotab/SKILL.md` | Agent-facing skill definition for the CLI |
| `README.md` | Primary user-facing API and mathematical model documentation |

Roadmap items (multi-skill Erlang C, occupancy cap, shrinkage/absenteeism,
intraday simulation) are tracked as GitHub issues labeled `roadmap`, not as
files in this repo. When picking one up, read the issue for the full
problem/approach writeup before implementing.

## Workflow

- **Branches**: code changes go through a `feat/*` (or `fix/*`, `docs/*`)
  branch merged into `main` via pull request. Committing directly to `main`
  is acceptable only for trivial docs/config touches.
- **Commits**: use conventional commits — `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`.
- **External PRs**: this repository does not accept external pull requests
  (see `CONTRIBUTING.md`); they are auto-closed by
  `.github/workflows/close-prs.yml`. PRs from the repository owner are exempt.
- **Releases**: bump `version` in `pyproject.toml`, then create a GitHub
  Release (`vX.Y.Z` tag); `.github/workflows/publish.yml` builds and publishes
  to PyPI automatically via trusted publishing. PyPI versions are immutable —
  never reuse a version number.

## Working rules

- Keep changes scoped to the Python library/CLI surface, tests, and README
  unless the task explicitly asks for packaging, CI, or release work.
- Preserve public API and CLI flag names already documented in `README.md`
  unless a breaking-change discussion has happened first.
- Treat units carefully: call volumes are `calls_per_interval`; the default
  `interval` is `600.0` seconds, so default examples are 10-minute buckets.
- Prefer small, isolated changes. Shared formula changes can affect agents,
  queues, and trunks behavior at once — when changing one formula, inspect
  the related queue, capacity, and README documentation paths.
- Do not add third-party runtime dependencies without explicit approval.

## Code style

- Existing source uses type hints, module docstrings in Portuguese, and
  project-specific exceptions for validation/calculation failures.
- Prefer clear mathematical variable names that match the README terminology:
  `traffic_rate`, `birth_rate`, `death_rate`, `utilisation`, `sla`, `aht`,
  `interval`.
- Keep docstrings consistent with nearby code. Portuguese is acceptable and
  currently predominant in source docstrings; README and CLI help text are
  in English.
- Avoid broad refactors when fixing formulas. Make the smallest change that
  can be validated.

## Validation

Run the test suite from the repository root:

```bash
python3 -m unittest discover -s tests
```

For a quick manual check of a specific calculation, put the repository's
parent directory on `PYTHONPATH` (the package root maps to the repo root, so
`import mod_turbotab` resolves from one level up — the same trick
`tests/test_cli.py` uses):

```bash
PYTHONPATH=.. python3 -c "from mod_turbotab.agents.capacity import agents_required; print(agents_required(0.80, 20, 25, 180))"
# expected output: 11 (matches the README quick-start example)
```

For behavioral changes, add or update a focused test in `tests/test_cli.py`
(or a new test module) covering the changed public function or CLI command.

Before finishing, run `git status --short` and confirm only the intended
files are staged.

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
