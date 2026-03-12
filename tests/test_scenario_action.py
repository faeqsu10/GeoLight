import unittest

from config import (
    ACTION_AGGRESSIVE_SCENARIOS,
    ACTION_MODE_FLOW,
    ACTION_URGENT_RULES,
    INDICATORS,
)
from domain import action_engine
from domain.action_engine import get_action_result
from domain.scenario_engine import find_best_scenario


class ScenarioActionRegressionTests(unittest.TestCase):
    def setUp(self):
        action_engine._last_action = None
        action_engine._last_action_time = 0.0
        action_engine._today_result = None
        action_engine._today_date = None

    def test_scenario_alias_uses_oil_change_pct_inputs(self):
        indicators = {
            "oil_wti_change_pct": 6.2,
            "oil_brent_change_pct": 5.8,
            "vix": 27.0,
            "oil_wti": 90.0,  # 절대 수준 조건
        }

        best = find_best_scenario(indicators)

        self.assertIsNotNone(best)
        self.assertEqual(best["key"], "escalation")
        self.assertEqual(best["score"], 1.0)
        self.assertIn("oil_change_pct=6.0 (>=5.0)", best["matched"])
        self.assertTrue(best["exit_signals"])

    def test_action_cooldown_never_invents_rebalance_mode(self):
        action_engine._last_action = {
            "mode_key": "normal_dca",
            "mode": {"name": "일반 분할매수"},
            "risk_score": 0,
            "scenario_name": "없음",
        }
        action_engine._last_action_time = action_engine.time.time()

        indicators = {
            "usd_krw_change_pct": 1.8,
            "vix": 27.0,
            "usd_krw": 1398.2,
        }
        scenario = {
            "key": "escalation",
            "name": "확전 시나리오",
            "score": 1.0,
            "beneficiary_sectors": ["방산", "LNG"],
        }

        result = get_action_result(indicators, scenario, events=[])

        self.assertEqual(result["risk_score"], 6)
        self.assertEqual(result["mode_key"], "conservative_dca")
        self.assertNotEqual(result["mode_key"], "rebalance")

    def test_action_mode_flow_and_aggressive_scenarios_are_config_driven(self):
        self.assertEqual(
            ACTION_MODE_FLOW,
            ["aggressive", "normal_dca", "conservative_dca", "hold"],
        )
        self.assertEqual(ACTION_AGGRESSIVE_SCENARIOS, {"de_escalation", "rate_easing"})

    def test_indicator_metadata_and_urgent_rules_are_config_driven(self):
        self.assertEqual(INDICATORS["oil_wti"]["ticker"], "CL=F")
        self.assertEqual(INDICATORS["kospi"]["display_name"], "KOSPI")
        self.assertEqual(
            ACTION_URGENT_RULES,
            [
                {"indicator": "vix", "abs": False, "threshold": 30.0},
                {"indicator": "usd_krw_change_pct", "abs": True, "threshold": 2.0},
                {"indicator": "oil_wti_change_pct", "abs": True, "threshold": 5.0},
                {"indicator": "kospi_change_pct", "abs": True, "threshold": 3.0},
            ],
        )


if __name__ == "__main__":
    unittest.main()
