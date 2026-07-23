"""Testes de regressão do dimensionamento multi-skill (Opção A)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# O pacote mod_turbotab resolve a partir do diretório pai do repo
# (package-dir mapeia o pacote para a raiz do repo).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mod_turbotab.calculations.multi_skill import agents_required_multi
from mod_turbotab.exceptions import InputValidationError

GROUPS = [
    {"name": "billing", "calls_per_interval": 25, "aht": 180},
    {"name": "tech", "calls_per_interval": 20, "aht": 240},
]
POOLS_CROSS = [
    {"skills": ["billing"], "count": 8},
    {"skills": ["tech"], "count": 9},
    {"skills": ["billing", "tech"], "count": 6},
]
POOLS_DEDICATED = [
    {"skills": ["billing"], "count": 11},
    {"skills": ["tech"], "count": 11},
]


def run(groups=GROUPS, pools=POOLS_CROSS, **kwargs):
    kwargs.setdefault("sla", 0.80)
    kwargs.setdefault("service_time", 20)
    return agents_required_multi(skill_groups=groups, agent_pools=pools, **kwargs)


class SharingTests(unittest.TestCase):
    def test_readme_example_totals(self) -> None:
        totals = run()["totals"]
        self.assertEqual(totals["naive_total_hc"], 22)
        self.assertEqual(totals["adjusted_total_hc"], 20)
        self.assertEqual(totals["savings_hc"], 2)
        self.assertTrue(totals["fits_in_pool_capacity"])

    def test_cross_skilled_reduction(self) -> None:
        # baseline 11 por skill; ceil(11 * 0.9) = 10 e o floor (ceil(A) + 1)
        # não domina: 9 para billing, 9 para tech.
        for skill in run()["per_skill"]:
            self.assertEqual(skill["baseline_hc"], 11)
            self.assertEqual(skill["adjusted_hc"], 10)
            self.assertTrue(skill["cross_skilled"])

    def test_dedicated_only_reproduces_single_skill(self) -> None:
        for skill in run(pools=POOLS_DEDICATED)["per_skill"]:
            self.assertEqual(skill["adjusted_hc"], skill["baseline_hc"])
            self.assertFalse(skill["cross_skilled"])

    def test_traffic_floor_dominates_aggressive_sharing(self) -> None:
        # Com s = 0.5, ceil(11 * 0.5) = 6 ficaria abaixo do floor
        # ceil(A) + 1 = 9: o floor prevalece para manter utilização < 100%.
        for skill in run(sharing_factor=0.5)["per_skill"]:
            self.assertEqual(skill["adjusted_hc"], 9)

    def test_sharing_factor_one_keeps_baseline(self) -> None:
        for skill in run(sharing_factor=1.0)["per_skill"]:
            self.assertEqual(skill["adjusted_hc"], skill["baseline_hc"])

    def test_occupancy_adjusted_is_offered_over_adjusted(self) -> None:
        for skill in run()["per_skill"]:
            self.assertAlmostEqual(
                skill["occupancy_adjusted"],
                skill["offered_traffic"] / skill["adjusted_hc"],
                places=9,
            )

    def test_pool_capacity_check(self) -> None:
        totals = run(pools=[{"skills": ["billing", "tech"], "count": 5}])["totals"]
        self.assertEqual(totals["pool_capacity_hc"], 5)
        self.assertFalse(totals["fits_in_pool_capacity"])

    def test_uncovered_skill_does_not_fit(self) -> None:
        # Capacidade agregada (22) cobre o total, mas tech não tem nenhum
        # pool elegível: o roster é impossível.
        result = run(pools=[{"skills": ["billing"], "count": 22}])
        self.assertFalse(result["totals"]["fits_in_pool_capacity"])
        tech = next(s for s in result["per_skill"] if s["name"] == "tech")
        self.assertEqual(tech["eligible_pool_hc"], 0)

    def test_skewed_capacity_does_not_fit(self) -> None:
        # Total 22 bate, mas só 2 agentes podem atender tech (precisa 11).
        totals = run(
            pools=[
                {"skills": ["billing"], "count": 20},
                {"skills": ["tech"], "count": 2},
            ]
        )["totals"]
        self.assertFalse(totals["fits_in_pool_capacity"])

    def test_overlapping_shared_pool_shortfall_does_not_fit(self) -> None:
        # billing e tech (10 ajustados cada) só têm um pool compartilhado de
        # 10 agentes; capacidade agregada e por-skill "batem", mas 20 agentes
        # não saem de um pool de 10 — só o fluxo máximo pega este caso.
        groups = GROUPS + [{"name": "retencao", "calls_per_interval": 25, "aht": 180}]
        result = run(
            groups=groups,
            pools=[
                {"skills": ["retencao"], "count": 30},
                {"skills": ["billing", "tech"], "count": 10},
            ],
        )
        self.assertFalse(result["totals"]["fits_in_pool_capacity"])

    def test_cross_pool_counts_for_all_its_skills(self) -> None:
        # Um único pool cross-skilled com 20 agentes é elegível para ambas
        # as skills (10 + 10 ajustadas): fits.
        result = run(pools=[{"skills": ["billing", "tech"], "count": 20}])
        self.assertTrue(result["totals"]["fits_in_pool_capacity"])
        for skill in result["per_skill"]:
            self.assertEqual(skill["eligible_pool_hc"], 20)

    def test_patience_passthrough(self) -> None:
        totals = run(patience=60)["totals"]
        self.assertEqual(totals["adjusted_total_hc"], 20)


class ValidationTests(unittest.TestCase):
    def test_invalid_sharing_factor(self) -> None:
        for bad in (0, -0.5, 1.5):
            with self.assertRaises(InputValidationError):
                run(sharing_factor=bad)

    def test_missing_skill_group_keys(self) -> None:
        with self.assertRaises(InputValidationError):
            run(groups=[{"name": "billing", "aht": 180}])

    def test_duplicate_skill_name(self) -> None:
        with self.assertRaises(InputValidationError):
            run(
                groups=[
                    {"name": "billing", "calls_per_interval": 25, "aht": 180},
                    {"name": "billing", "calls_per_interval": 10, "aht": 120},
                ]
            )

    def test_pool_references_unknown_skill(self) -> None:
        with self.assertRaises(InputValidationError):
            run(pools=[{"skills": ["retencao"], "count": 5}])

    def test_pool_with_empty_skills_or_negative_count(self) -> None:
        with self.assertRaises(InputValidationError):
            run(pools=[{"skills": [], "count": 5}])
        with self.assertRaises(InputValidationError):
            run(pools=[{"skills": ["billing"], "count": -1}])

    def test_non_positive_patience_rejected(self) -> None:
        # patience <= 0 degenera o Erlang A (SLA=1) e reduziria o HC
        # silenciosamente; deve falhar na validação.
        for bad in (0, -60):
            with self.assertRaises(InputValidationError):
                run(patience=bad)

    def test_pool_with_duplicated_skill_rejected(self) -> None:
        # ["billing", "billing"] marcaria billing como cross-skilled sem
        # nenhuma segunda skill coberta.
        with self.assertRaises(InputValidationError):
            run(pools=[{"skills": ["billing", "billing"], "count": 10}])

    def test_invalid_scalars(self) -> None:
        with self.assertRaises(InputValidationError):
            run(sla=1.5)
        with self.assertRaises(InputValidationError):
            run(interval=0)
        with self.assertRaises(InputValidationError):
            run(groups=[{"name": "billing", "calls_per_interval": -1, "aht": 180}])
        with self.assertRaises(InputValidationError):
            run(groups=[{"name": "billing", "calls_per_interval": 25, "aht": 0}])


if __name__ == "__main__":
    unittest.main()
