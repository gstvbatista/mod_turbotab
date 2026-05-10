"""Intraday simulation regression tests."""

from __future__ import annotations

import unittest

from mod_turbotab.exceptions import InputValidationError
from mod_turbotab.simulation.intraday import (
    CURVE_FLAT,
    CURVE_SATURDAY,
    CURVE_SUNDAY,
    CURVE_WEEKDAY_VOZ,
    simulate_day,
)


class DefaultCurvesTests(unittest.TestCase):
    def test_curves_have_48_thirty_minute_intervals(self) -> None:
        for curve in (CURVE_WEEKDAY_VOZ, CURVE_SATURDAY, CURVE_SUNDAY, CURVE_FLAT):
            self.assertEqual(len(curve), 48)

    def test_curves_sum_to_one(self) -> None:
        for curve in (CURVE_WEEKDAY_VOZ, CURVE_SATURDAY, CURVE_SUNDAY, CURVE_FLAT):
            self.assertAlmostEqual(sum(curve), 1.0, places=12)

    def test_curves_are_non_negative(self) -> None:
        for curve in (CURVE_WEEKDAY_VOZ, CURVE_SATURDAY, CURVE_SUNDAY, CURVE_FLAT):
            self.assertTrue(all(v >= 0 for v in curve))

    def test_weekday_voice_peaks_at_ten_in_the_morning(self) -> None:
        # Index 20 == 10:00-10:30 bucket. The spec calls for peaks at 10h/14h.
        self.assertEqual(CURVE_WEEKDAY_VOZ.index(max(CURVE_WEEKDAY_VOZ)), 20)


class SimulateDayTests(unittest.TestCase):
    def test_returns_one_row_per_interval(self) -> None:
        report = simulate_day(1200, CURVE_WEEKDAY_VOZ, 180, 0.80, 20)
        self.assertEqual(len(report["intervals"]), 48)

    def test_report_shape(self) -> None:
        report = simulate_day(1200, CURVE_WEEKDAY_VOZ, 180, 0.80, 20)
        self.assertIn("peak_interval", report)
        self.assertIn("peak_agents", report)
        self.assertIn("total_agent_hours", report)
        row = report["intervals"][0]
        for key in ("start", "end", "volume", "agents_required",
                    "expected_sla", "expected_asa", "occupancy"):
            self.assertIn(key, row)

    def test_peak_is_during_morning_for_weekday_voice(self) -> None:
        report = simulate_day(1200, CURVE_WEEKDAY_VOZ, 180, 0.80, 20)
        # Peak interval should lie in the morning peak band 09:00-11:00.
        self.assertIn(report["peak_interval"], {"09:00", "09:30", "10:00", "10:30"})

    def test_curve_must_sum_to_one(self) -> None:
        with self.assertRaises(InputValidationError):
            simulate_day(100, [0.5, 0.3], 180, 0.80, 20)

    def test_curve_must_be_non_negative(self) -> None:
        with self.assertRaises(InputValidationError):
            simulate_day(100, [0.6, -0.1, 0.5], 180, 0.80, 20)

    def test_empty_curve_rejected(self) -> None:
        with self.assertRaises(InputValidationError):
            simulate_day(100, [], 180, 0.80, 20)

    def test_zero_volume_interval_uses_zero_agents(self) -> None:
        # Curve concentrates all volume in interval 0; rest are zero-volume.
        curve = [1.0] + [0.0] * 47
        report = simulate_day(10, curve, 180, 0.80, 20)
        self.assertEqual(report["intervals"][5]["volume"], 0)
        self.assertEqual(report["intervals"][5]["agents_required"], 0)
        self.assertEqual(report["intervals"][5]["expected_sla"], 1.0)

    def test_max_occupancy_integration(self) -> None:
        # Without cap → fewer agents; with tight cap → more agents at peak.
        without = simulate_day(2400, CURVE_FLAT, 180, 0.80, 20)
        with_cap = simulate_day(2400, CURVE_FLAT, 180, 0.80, 20, max_occupancy=0.50)
        self.assertGreaterEqual(with_cap["peak_agents"], without["peak_agents"])

    def test_shrinkage_adds_scheduled_headcount(self) -> None:
        report = simulate_day(
            2400, CURVE_FLAT, 180, 0.80, 20, shrinkage=0.30,
        )
        self.assertIn("peak_scheduled_agents", report)
        self.assertIn("total_scheduled_hours", report)
        # Scheduled must be >= on-phone for non-zero peaks.
        self.assertGreaterEqual(report["peak_scheduled_agents"], report["peak_agents"])
        # And scheduled hours should also be >= on-phone hours.
        self.assertGreaterEqual(
            report["total_scheduled_hours"], report["total_agent_hours"]
        )

    def test_total_agent_hours_matches_sum(self) -> None:
        report = simulate_day(1200, CURVE_WEEKDAY_VOZ, 180, 0.80, 20)
        manual = sum(r["agents_required"] for r in report["intervals"]) * 0.5
        self.assertAlmostEqual(report["total_agent_hours"], manual, places=9)

    def test_interval_minutes_must_be_positive(self) -> None:
        with self.assertRaises(InputValidationError):
            simulate_day(100, CURVE_FLAT, 180, 0.80, 20, interval_minutes=0)


if __name__ == "__main__":
    unittest.main()
