"""Testes de regressão do multiplicador de turnos (assentos -> operadores)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# O pacote mod_turbotab resolve a partir do diretório pai do repo
# (package-dir mapeia o pacote para a raiz do repo).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mod_turbotab.agents.roster import (
    rostered_agents,
    rostered_fractional_agents,
)
from mod_turbotab.exceptions import InputValidationError


class RosteredAgentsTests(unittest.TestCase):
    def test_reference_model_case(self) -> None:
        # Caso da issue #26: 6 assentos escalados x 2 turnos = 12 operadores.
        self.assertEqual(rostered_agents(6, 2.0), 12)

    def test_unit_shifts_is_identity(self) -> None:
        self.assertEqual(rostered_agents(11, 1.0), 11)

    def test_zero_scheduled_agents(self) -> None:
        self.assertEqual(rostered_agents(0, 2.0), 0)

    def test_fractional_shifts_round_up(self) -> None:
        # 5 assentos x 1.5 = 7.5 -> 8 operadores; nunca subdimensiona.
        self.assertEqual(rostered_agents(5, 1.5), 8)
        self.assertEqual(rostered_agents(7, 1.4), 10)

    def test_exact_float_product_does_not_overshoot(self) -> None:
        # 10 * 1.1 = 11.000000000000002 em float; o teto não pode virar 12.
        self.assertEqual(rostered_agents(10, 1.1), 11)

    def test_invalid_shifts_rejected(self) -> None:
        for bad in (0.0, 0.5, 0.999, -1.0, float("nan"), float("inf")):
            with self.subTest(shifts=bad):
                with self.assertRaises(InputValidationError):
                    rostered_agents(6, bad)

    def test_negative_scheduled_agents_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            rostered_agents(-1, 2.0)

    def test_non_finite_scheduled_agents_rejected(self) -> None:
        for bad in (float("nan"), float("inf")):
            with self.subTest(scheduled_agents=bad):
                with self.assertRaises(InputValidationError):
                    rostered_agents(bad, 2.0)


class RosteredFractionalAgentsTests(unittest.TestCase):
    def test_does_not_round(self) -> None:
        self.assertAlmostEqual(
            rostered_fractional_agents(5.588, 2.0), 11.176, places=12
        )

    def test_unit_shifts_is_identity(self) -> None:
        self.assertEqual(rostered_fractional_agents(10.5, 1.0), 10.5)

    def test_zero_scheduled_agents(self) -> None:
        self.assertEqual(rostered_fractional_agents(0.0, 2.0), 0.0)

    def test_invalid_shifts_rejected(self) -> None:
        for bad in (0.0, 0.5, -1.0, float("nan"), float("inf")):
            with self.subTest(shifts=bad):
                with self.assertRaises(InputValidationError):
                    rostered_fractional_agents(10.5, bad)

    def test_negative_scheduled_agents_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            rostered_fractional_agents(-0.5, 2.0)

    def test_non_finite_scheduled_agents_rejected(self) -> None:
        for bad in (float("nan"), float("inf")):
            with self.subTest(scheduled_agents=bad):
                with self.assertRaises(InputValidationError):
                    rostered_fractional_agents(bad, 2.0)


if __name__ == "__main__":
    unittest.main()
