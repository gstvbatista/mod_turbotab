"""Testes de regressão da CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_DIR.parent


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKSPACE_DIR)
    return subprocess.run(
        [sys.executable, "-m", "mod_turbotab.cli", *args],
        cwd=WORKSPACE_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class CliTests(unittest.TestCase):
    def test_version_matches_pyproject(self) -> None:
        pyproject = (REPO_DIR / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^version = "([^"]+)"', pyproject)
        assert match is not None
        declared_version = match.group(1)

        result = run_cli("--version")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"turbotab {declared_version}")

    def test_group_without_command_prints_group_help(self) -> None:
        result = run_cli("sla")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: turbotab sla", result.stdout)
        self.assertIn("achieved", result.stdout)
        self.assertIn("target-time", result.stdout)
        self.assertNotIn("staffing  Intent-first staffing", result.stdout)

    def test_subcommand_help(self) -> None:
        result = run_cli("agents", "required", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--contacts-per-interval", result.stdout)
        self.assertIn("--sla", result.stdout)

    def test_staffing_required_headcount_chain_json(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--shrinkage",
            "0.30",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "2.2")
        self.assertEqual(payload["calculation"], "staffing.required")
        self.assertEqual(payload["inputs"]["shrinkage"], 0.30)
        self.assertEqual(payload["result"]["name"], "headcount")
        self.assertEqual(payload["result"]["unit"], "agents")
        self.assertEqual(
            payload["result"]["value"],
            {"productive_agents": 11, "scheduled_agents": 16},
        )

    def test_staffing_required_zero_shrinkage_keeps_erlang_headcount(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--shrinkage",
            "0",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["result"]["value"],
            {"productive_agents": 11, "scheduled_agents": 11},
        )

    def test_staffing_required_without_shrinkage_exits_nonzero(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--shrinkage", result.stderr)

    def test_staffing_required_invalid_shrinkage_exits_nonzero(self) -> None:
        for bad in ("1.0", "nan", "inf"):
            with self.subTest(shrinkage=bad):
                result = run_cli(
                    "staffing",
                    "required",
                    "--sla",
                    "0.80",
                    "--service-time",
                    "20",
                    "--contacts-per-interval",
                    "25",
                    "--aht",
                    "180",
                    "--shrinkage",
                    bad,
                    "--json",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("Shrinkage", result.stderr)

    def test_staffing_required_with_shifts_adds_rostered_agents(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "20.0475",
            "--aht",
            "480",
            "--interval",
            "3600",
            "--shrinkage",
            "0.105263",
            "--shifts",
            "2.0",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "2.2")
        self.assertEqual(payload["inputs"]["shifts"], 2.0)
        # Caso de referência da issue #26: 5 produtivos -> 6 assentos -> 12 operadores.
        self.assertEqual(
            payload["result"]["value"],
            {"productive_agents": 5, "scheduled_agents": 6, "rostered_agents": 12},
        )

    def test_staffing_required_without_shifts_omits_rostered_agents(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--shrinkage",
            "0.30",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertNotIn("shifts", payload["inputs"])
        self.assertNotIn("rostered_agents", payload["result"]["value"])

    def test_staffing_required_invalid_shifts_exits_nonzero(self) -> None:
        for bad in ("0", "0.5", "-1", "nan", "inf"):
            with self.subTest(shifts=bad):
                result = run_cli(
                    "staffing",
                    "required",
                    "--sla",
                    "0.80",
                    "--service-time",
                    "20",
                    "--contacts-per-interval",
                    "25",
                    "--aht",
                    "180",
                    "--shrinkage",
                    "0.30",
                    "--shifts",
                    bad,
                    "--json",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("Shifts", result.stderr)

    def test_staffing_fractional_required_with_shifts_keeps_chain_fractional(self) -> None:
        result = run_cli(
            "staffing",
            "fractional-required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--shrinkage",
            "0.30",
            "--shifts",
            "1.5",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "2.2")
        value = payload["result"]["value"]
        # A cadeia fracionária não arredonda em nenhum passo, inclusive na escala.
        self.assertAlmostEqual(
            value["rostered_agents"], value["scheduled_agents"] * 1.5
        )

    def test_staffing_fractional_required_headcount_chain_json(self) -> None:
        result = run_cli(
            "staffing",
            "fractional-required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--shrinkage",
            "0.30",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "2.2")
        self.assertEqual(payload["calculation"], "staffing.fractional_required")
        self.assertEqual(payload["result"]["name"], "headcount")
        value = payload["result"]["value"]
        # A cadeia fracionária não arredonda em nenhum passo.
        self.assertAlmostEqual(value["productive_agents"], 10.285163130544403)
        self.assertAlmostEqual(
            value["scheduled_agents"], value["productive_agents"] / 0.7
        )

    def test_staffing_required_max_occupancy_json(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "100",
            "--aht",
            "180",
            "--max-occupancy",
            "0.85",
            "--shrinkage",
            "0",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["inputs"]["max_occupancy"], 0.85)
        self.assertEqual(payload["result"]["value"]["productive_agents"], 36)

    def test_staffing_required_invalid_max_occupancy_exits_nonzero(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "100",
            "--aht",
            "180",
            "--max-occupancy",
            "1.5",
            "--shrinkage",
            "0",
            "--json",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("max_occupancy", result.stderr)

    def test_staffing_fractional_required_max_occupancy_json(self) -> None:
        result = run_cli(
            "staffing",
            "fractional-required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "100",
            "--aht",
            "180",
            "--max-occupancy",
            "0.85",
            "--shrinkage",
            "0",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["inputs"]["max_occupancy"], 0.85)
        # O floor A/rho (30 / 0.85) vence o Erlang fracionário (~34.53), sem ceil.
        self.assertAlmostEqual(
            payload["result"]["value"]["productive_agents"], 30 / 0.85
        )

    def test_staffing_fractional_required_invalid_max_occupancy_exits_nonzero(self) -> None:
        result = run_cli(
            "staffing",
            "fractional-required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "100",
            "--aht",
            "180",
            "--max-occupancy",
            "1.5",
            "--shrinkage",
            "0",
            "--json",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("max_occupancy", result.stderr)

    def test_agents_fractional_required_subnormal_max_occupancy_exits_nonzero(self) -> None:
        # Regressão: 5e-324 estourava a divisão para inf e o comando saía com
        # sucesso emitindo "value": Infinity — que não é JSON válido.
        result = run_cli(
            "agents",
            "fractional-required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "100",
            "--aht",
            "180",
            "--max-occupancy",
            "5e-324",
            "--json",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("too small for the offered traffic", result.stderr)
        self.assertNotIn("Infinity", result.stdout)

    def test_agents_fractional_required_max_occupancy_json(self) -> None:
        result = run_cli(
            "agents",
            "fractional-required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "100",
            "--aht",
            "180",
            "--max-occupancy",
            "0.85",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["inputs"]["max_occupancy"], 0.85)
        self.assertAlmostEqual(payload["result"]["value"], 30 / 0.85)

    def test_queue_sla_json(self) -> None:
        result = run_cli(
            "sla",
            "achieved",
            "--agents",
            "11",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["calculation"], "sla.achieved")
        self.assertIn("service_time", payload["inputs"])
        self.assertNotIn("service_time_val", payload["inputs"])
        self.assertGreaterEqual(payload["result"]["value"], 0.80)

    def test_capacity_json_uses_cli_terms(self) -> None:
        result = run_cli(
            "staffing",
            "capacity",
            "--agents",
            "11",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("agents", payload["inputs"])
        self.assertNotIn("no_agents", payload["inputs"])

    def test_intent_first_queue_wait_and_telecom_trunks(self) -> None:
        queue_result = run_cli(
            "queue",
            "wait",
            "--agents",
            "11",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )
        telecom_result = run_cli(
            "telecom",
            "trunks",
            "--agents",
            "11",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(queue_result.returncode, 0, queue_result.stderr)
        self.assertEqual(telecom_result.returncode, 0, telecom_result.stderr)
        self.assertEqual(json.loads(queue_result.stdout)["calculation"], "queue.wait")
        self.assertEqual(json.loads(telecom_result.stdout)["calculation"], "telecom.trunks")

    def test_invalid_input_exits_nonzero(self) -> None:
        result = run_cli(
            "agents",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--contacts-per-interval",
            "-1",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("turbotab: error:", result.stderr)
        self.assertIn("Invalid parameters for agents_required.", result.stderr)

    def test_invalid_queue_input_exits_nonzero(self) -> None:
        result = run_cli(
            "queues",
            "queued",
            "--agents",
            "-1",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid parameters for queued.", result.stderr)

    def test_invalid_trunks_input_exits_nonzero(self) -> None:
        result = run_cli(
            "telecom",
            "trunks",
            "--agents",
            "-1",
            "--contacts-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "Invalid values for 'agents', 'contacts_per_interval', or 'aht'.",
            result.stderr,
        )

    def test_existing_python_api_import_still_works(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(WORKSPACE_DIR)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from mod_turbotab.agents.capacity import agents_required; "
                    "print(agents_required(0.80, 20, 25, 180))"
                ),
            ],
            cwd=WORKSPACE_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "11")


if __name__ == "__main__":
    unittest.main()
