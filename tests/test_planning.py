import unittest
from fieldshift_data.planning import solve, at_date
from datetime import date


def row(sid, position, crop, net, application=2):
    return {"location": "Fixture", "system_id": sid, "system_name": sid, "record_type": "rotation_position",
            "rotation_position": position, "crop": crop, "application_p": application,
            "agronomic_p_budget": net, "overall_p_budget": net, "hydrologic_p_form": "TP"}


class PlanningTests(unittest.TestCase):
    def config(self):
        return dict(mode="reference_scenario", location="Fixture", start_year=2027, years=2,
                    allowed_crops=["Wheat", "Canola", "Soybean"], minimum_wheat_seasons=1,
                    minimum_distinct_crop_labels=2, max_annual_p_application=10,
                    max_abs_cumulative_p_change=3, budget_basis="field_tp",
                    require_complete_cycles=True, previous_crop="", top_k=3)

    def test_known_optimum_and_mass_balance(self):
        rows = [row("A", 1, "Wheat", -1), row("A", 2, "Canola", 2),
                row("B", 1, "Wheat", 4), row("B", 2, "Soybean", 1)]
        result = solve(rows, self.config())
        best = result["best"][0]
        self.assertEqual(best["system_id"], "A")
        self.assertEqual([r["crop"] for r in best["schedule"]], ["Wheat", "Canola"])
        self.assertEqual(best["sum_abs_cumulative_p_change"], 2)
        self.assertEqual(best["final_cumulative_p_change"], 1)
        self.assertEqual(at_date(result, date(2028, 7, 1))["crop"], "Canola")
        self.assertIsNone(at_date(result, date(2030, 7, 1)))

    def test_missing_p_not_imputed(self):
        rows = [row("A", 1, "Wheat", None), row("A", 2, "Canola", 2)]
        result = solve(rows, self.config())
        self.assertEqual(result["status"], "no_feasible_plan")
        self.assertIn("missing_budget", result["excluded"][0]["reason"])

    def test_dissolved_p_not_accepted_as_total_field_p(self):
        rows = [row("A", 1, "Wheat", -1), row("A", 2, "Canola", 2)]
        rows[0]["hydrologic_p_form"] = "DRP"
        result = solve(rows, self.config())
        self.assertFalse(result["best"])

    def test_previous_crop_and_incomplete_cycle_constraints(self):
        rows = [row("A", 1, "Wheat", -1), row("A", 2, "Canola", 2)]
        config = self.config()
        config["previous_crop"] = "Wheat"
        result = solve(rows, config)
        self.assertEqual(result["best"][0]["schedule"][0]["crop"], "Canola")
        config["years"] = 3
        self.assertEqual(solve(rows, config)["status"], "no_feasible_plan")

    def test_no_field_readiness_claim_or_nonfinite_bounds(self):
        config = self.config()
        config["mode"] = "field_recommendation"
        with self.assertRaises(ValueError):
            solve([], config)
        config = self.config()
        config["max_abs_cumulative_p_change"] = float("nan")
        with self.assertRaises(ValueError):
            solve([], config)


if __name__ == "__main__":
    unittest.main()
