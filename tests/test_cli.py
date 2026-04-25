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
    def test_subcommand_help(self) -> None:
        result = run_cli("agents", "required", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--calls-per-interval", result.stdout)
        self.assertIn("--sla", result.stdout)

    def test_agents_required_json(self) -> None:
        result = run_cli(
            "agents",
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
        self.assertEqual(payload["calculation"], "agents.required")
        self.assertEqual(payload["result"]["name"], "agents")
        self.assertEqual(payload["result"]["unit"], "agents")
        self.assertEqual(payload["result"]["value"], 11)

    def test_queue_sla_json(self) -> None:
        result = run_cli(
            "queues",
            "sla",
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
        self.assertEqual(payload["calculation"], "queues.sla")
        self.assertGreaterEqual(payload["result"]["value"], 0.80)

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
