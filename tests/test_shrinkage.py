"""Testes de regressão dos ajustes de shrinkage e absenteísmo (Opção A)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# O pacote mod_turbotab resolve a partir do diretório pai do repo
# (package-dir mapeia o pacote para a raiz do repo).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mod_turbotab.agents.capacity import agents_required
from mod_turbotab.agents.shrinkage import (
    agents_required_with_shrinkage,
    scheduled_agents,
    shrinkage_factor,
)
from mod_turbotab.exceptions import InputValidationError


class ScheduledAgentsTests(unittest.TestCase):
    def test_inflates_and_rounds_up(self) -> None:
        # 11 / (1 - 0.3) = 15.71... -> 16
        self.assertEqual(scheduled_agents(11, 0.3), 16)

    def test_zero_shrinkage_is_identity(self) -> None:
        self.assertEqual(scheduled_agents(11, 0.0), 11)

    def test_zero_agents_stay_zero(self) -> None:
        self.assertEqual(scheduled_agents(0, 0.3), 0)

    def test_exact_division_does_not_over_ceil(self) -> None:
        # 1 / (1 - 0.8) = 5.000000000000001 em float; sem a tolerância o
        # ceil estouraria para 6.
        self.assertEqual(scheduled_agents(1, 0.8), 5)
        self.assertEqual(scheduled_agents(2, 0.9), 20)
        self.assertEqual(scheduled_agents(3, 0.8), 15)

    def test_negative_agents_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            scheduled_agents(-1, 0.3)

    def test_invalid_shrinkage_rejected(self) -> None:
        for bad in (-0.1, 1.0, 1.5):
            with self.assertRaises(InputValidationError):
                scheduled_agents(11, bad)


class ShrinkageFactorTests(unittest.TestCase):
    def test_components_are_additive(self) -> None:
        total = shrinkage_factor(
            breaks=0.07,
            training=0.04,
            meetings=0.03,
            absenteeism=0.08,
            system_downtime=0.02,
            other=0.06,
        )
        self.assertAlmostEqual(total, 0.30, places=9)

    def test_no_components_is_zero(self) -> None:
        self.assertEqual(shrinkage_factor(), 0.0)

    def test_negative_component_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            shrinkage_factor(breaks=-0.05)

    def test_total_reaching_one_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            shrinkage_factor(breaks=0.5, absenteeism=0.5)

    def test_composes_with_scheduled_agents(self) -> None:
        factor = shrinkage_factor(breaks=0.07, absenteeism=0.08)
        self.assertEqual(scheduled_agents(11, factor), 13)


class AgentsRequiredWithShrinkageTests(unittest.TestCase):
    BASE = dict(sla=0.80, service_time=20, calls_per_interval=25, aht=180)

    def test_zero_shrinkage_matches_agents_required(self) -> None:
        self.assertEqual(
            agents_required_with_shrinkage(**self.BASE),
            agents_required(**self.BASE),
        )

    def test_applies_shrinkage_on_top_of_erlang(self) -> None:
        # agents_required(...) = 11; 11 / 0.7 -> 16
        self.assertEqual(
            agents_required_with_shrinkage(**self.BASE, shrinkage=0.3), 16
        )

    def test_forwards_max_occupancy(self) -> None:
        # Com o teto de ocupação o floor sobe o HC na fila antes do
        # shrinkage: o resultado deve partir do mesmo valor de
        # agents_required com o mesmo teto.
        on_phone = agents_required(**self.BASE, max_occupancy=0.6)
        self.assertEqual(
            agents_required_with_shrinkage(
                **self.BASE, shrinkage=0.3, max_occupancy=0.6
            ),
            scheduled_agents(on_phone, 0.3),
        )

    def test_forwards_patience(self) -> None:
        on_phone = agents_required(**self.BASE, patience=60)
        self.assertEqual(
            agents_required_with_shrinkage(**self.BASE, shrinkage=0.3, patience=60),
            scheduled_agents(on_phone, 0.3),
        )

    def test_invalid_shrinkage_rejected_before_calculation(self) -> None:
        for bad in (-0.1, 1.0):
            with self.assertRaises(InputValidationError):
                agents_required_with_shrinkage(**self.BASE, shrinkage=bad)

    def test_underlying_validation_still_applies(self) -> None:
        with self.assertRaises(InputValidationError):
            agents_required_with_shrinkage(
                sla=0.80, service_time=20, calls_per_interval=-5, aht=180
            )


if __name__ == "__main__":
    unittest.main()
