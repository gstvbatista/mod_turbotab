"""CLI regression tests."""

from __future__ import annotations

import json
import os
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
        self.assertIn("--calls-per-interval", result.stdout)
        self.assertIn("--sla", result.stdout)

    def test_agents_required_json(self) -> None:
        result = run_cli(
            "staffing",
            "required",
            "--sla",
            "0.80",
            "--service-time",
            "20",
            "--calls-per-interval",
            "25",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["calculation"], "staffing.required")
        self.assertEqual(payload["result"]["name"], "agents")
        self.assertEqual(payload["result"]["unit"], "agents")
        self.assertEqual(payload["result"]["value"], 11)

    def test_queue_sla_json(self) -> None:
        result = run_cli(
            "sla",
            "achieved",
            "--agents",
            "11",
            "--service-time",
            "20",
            "--calls-per-interval",
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
            "--calls-per-interval",
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
            "--calls-per-interval",
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
            "--calls-per-interval",
            "-1",
            "--aht",
            "180",
            "--json",
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("turbotab: error:", result.stderr)

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
