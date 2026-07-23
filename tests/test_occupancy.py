"""Testes de regressão do teto de ocupação (max_occupancy) e helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# O pacote mod_turbotab resolve a partir do diretório pai do repo
# (package-dir mapeia o pacote para a raiz do repo).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mod_turbotab.agents.capacity import (
    agents_required,
    is_within_occupancy,
    occupancy,
)
from mod_turbotab.exceptions import InputValidationError


class AgentsRequiredMaxOccupancyTests(unittest.TestCase):
    def test_default_preserves_baseline(self) -> None:
        self.assertEqual(agents_required(0.80, 20, 25, 180), 11)
        self.assertEqual(agents_required(0.80, 20, 25, 180, max_occupancy=None), 11)

    def test_cap_not_binding_keeps_erlang_result(self) -> None:
        # A/N = 7.5/11 ~= 0.68, já abaixo de 0.85: o cap não altera o resultado.
        self.assertEqual(agents_required(0.80, 20, 25, 180, max_occupancy=0.85), 11)

    def test_cap_binding_lifts_headcount(self) -> None:
        # 100 chamadas: Erlang C pede 35, mas ceil(30 / 0.85) = 36.
        self.assertEqual(agents_required(0.80, 20, 100, 180), 35)
        self.assertEqual(agents_required(0.80, 20, 100, 180, max_occupancy=0.85), 36)

    def test_cap_of_one_never_lowers_result(self) -> None:
        # ceil(A / 1.0) = 30 < 35: o resultado é max(erlang, floor), nunca o menor.
        self.assertEqual(agents_required(0.80, 20, 100, 180, max_occupancy=1.0), 35)

    def test_cap_composes_with_erlang_a_patience(self) -> None:
        self.assertEqual(
            agents_required(0.80, 20, 100, 180, patience=60, max_occupancy=0.85), 36
        )

    def test_exact_boundary_does_not_over_ceil(self) -> None:
        # A = 35.7 e 35.7/0.85 = 42 exato em decimal, mas o float dá
        # 42.00000000000001: sem tolerância o ceil contrataria 43.
        self.assertEqual(agents_required(0.80, 20, 36, 595), 42)
        self.assertEqual(agents_required(0.80, 20, 36, 595, max_occupancy=0.85), 42)

    def test_zero_volume_with_cap(self) -> None:
        self.assertEqual(agents_required(0.80, 20, 0, 180, max_occupancy=0.85), 1)

    def test_invalid_cap_raises(self) -> None:
        for bad in (0, -0.1, 1.01, 2):
            with self.assertRaises(InputValidationError):
                agents_required(0.80, 20, 25, 180, max_occupancy=bad)


class OccupancyTests(unittest.TestCase):
    def test_ratio_matches_readme_example(self) -> None:
        self.assertAlmostEqual(occupancy(11, 25, 180), 0.681818, places=6)

    def test_respects_interval(self) -> None:
        # 150 chamadas/hora com interval=3600 equivale a 25/10min.
        self.assertAlmostEqual(
            occupancy(11, 150, 180, interval=3600), occupancy(11, 25, 180), places=9
        )

    def test_invalid_inputs_raise(self) -> None:
        with self.assertRaises(InputValidationError):
            occupancy(0, 25, 180)
        with self.assertRaises(InputValidationError):
            occupancy(11, -1, 180)
        with self.assertRaises(InputValidationError):
            occupancy(11, 25, 0)
        with self.assertRaises(InputValidationError):
            occupancy(11, 25, 180, interval=0)
        with self.assertRaises(InputValidationError):
            occupancy(11, 25, 180, interval=-600)

    def test_invalid_interval_raises_through_is_within(self) -> None:
        with self.assertRaises(InputValidationError):
            is_within_occupancy(11, 25, 180, 0.85, interval=-600)


class IsWithinOccupancyTests(unittest.TestCase):
    def test_over_and_under_the_cap(self) -> None:
        # A = 30 erlangs: 30/33 ~= 0.91 estoura o cap; 30/36 ~= 0.83 respeita.
        self.assertFalse(is_within_occupancy(33, 100, 180, 0.85))
        self.assertTrue(is_within_occupancy(36, 100, 180, 0.85))

    def test_boundary_is_inclusive(self) -> None:
        # A/N exatamente igual ao cap conta como dentro (<=).
        self.assertTrue(is_within_occupancy(10, 25, 180, 0.75))

    def test_exact_boundary_survives_float_error(self) -> None:
        # 35.7/42 vira 0.8500000000000001 em float; a tolerância evita
        # negar um cap atingido exatamente.
        self.assertTrue(is_within_occupancy(42, 36, 595, 0.85))

    def test_invalid_cap_raises(self) -> None:
        for bad in (0, -0.5, 1.5):
            with self.assertRaises(InputValidationError):
                is_within_occupancy(11, 25, 180, bad)


if __name__ == "__main__":
    unittest.main()
