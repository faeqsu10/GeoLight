import unittest

from domain.budget_allocator import format_budget_card
from domain.action_engine import format_action_card
from domain.scenario_engine import format_scenario_card
from domain.trend_detector import format_hot_stocks
from domain.user_profile import format_profile


class FormatterOutputTests(unittest.TestCase):
    def test_format_action_card_includes_scenario_description(self):
        result = {
            "mode_key": "normal_dca",
            "mode": {
                "emoji": "🟡",
                "name": "일반 분할매수",
                "guide": "투자예산의 25~50% 분할 집행",
                "budget_ratio": (25, 50),
            },
            "risk_score": 2,
            "scenario_name": "완화 시나리오",
            "scenario_description": "지정학 긴장 완화, 유가 하락, 위험자산 선호 복귀",
            "scenario_meaning": "전쟁이나 지정학 리스크가 누그러지는 구간입니다.",
            "risk_reasons": [],
            "opp_reasons": ["완화 이벤트 다수 감지 (4건)"],
            "warnings": [],
            "focus_sectors": ["항공", "여행"],
            "exit_signals": [
                "유가가 다시 급반등하거나 VIX가 재상승하면 여행·소비 회복주 비중을 줄입니다.",
                "전쟁 재확대 헤드라인이 나오면 완화 시나리오 전제는 약해지므로 분할 회수합니다.",
            ],
        }
        budget = {
            "monthly_budget": 700000,
            "execute_amount": (250000, 350000),
            "reserve_amount": 350000,
            "adjusted_ratio": (25, 50),
        }

        text = format_action_card(result, budget)

        self.assertIn("시나리오 설명", text)
        self.assertIn("지정학 리스크가 누그러지는", text)
        self.assertIn("줄이거나 뺄 때", text)
        self.assertIn("전쟁 재확대 헤드라인", text)

    def test_format_scenario_card_uses_friendly_language(self):
        scenario = {
            "name": "확전 시나리오",
            "description": "중동/지정학 긴장 확대",
            "meaning": "전쟁이나 분쟁 리스크가 커지는 구간입니다.",
            "score": 1.0,
            "matched": ["oil_change_pct=6.0 (>=5.0)", "vix=27.0 (>=25.0)"],
            "beneficiary_sectors": ["방산", "LNG"],
            "damaged_sectors": ["항공", "여행"],
        }

        text = format_scenario_card(scenario)

        self.assertIn("한줄 해석:", text)
        self.assertIn("이 시나리오가 뜻하는 것", text)
        self.assertIn("전쟁이나 분쟁 리스크가 커지는", text)
        self.assertIn("지금 이렇게 보는 이유", text)
        self.assertIn("유가 변화: 6.0 (>=5.0)", text)
        self.assertIn("지표 의미", text)
        self.assertIn("유가가 단기간에", text)
        self.assertIn("볼 섹터:", text)
        self.assertIn("피할 섹터:", text)

    def test_format_budget_card_is_actionable(self):
        budget = {
            "mode_name": "일반 분할매수",
            "monthly_budget": 700000,
            "execute_amount": (250000, 350000),
            "reserve_amount": 350000,
            "adjusted_ratio": (25, 50),
            "explanation": "unused",
        }
        action_result = {
            "mode_key": "normal_dca",
            "mode": {"emoji": "🟡", "name": "일반 분할매수"},
            "focus_sectors": ["항공", "여행"],
            "exit_signals": [
                "유가가 다시 급반등하거나 VIX가 재상승하면 여행·소비 회복주 비중을 줄입니다."
            ],
        }
        investable = {
            "disposable": 2000000,
            "invest_amount": 700000,
            "invest_ratio": 0.35,
            "savings_amount": 910000,
            "emergency_amount": 390000,
        }

        text = format_budget_card(budget, action_result, investable)

        self.assertIn("한줄 요약:", text)
        self.assertIn("이번 달 실행안", text)
        self.assertIn("섹터별 실행안", text)
        self.assertIn("회수 기준", text)
        self.assertIn("메모:", text)

    def test_format_hot_stocks_adds_context_and_checks(self):
        text = format_hot_stocks(
            {
                "top_volume": [
                    {"name": "삼성전자", "code": "005930", "trading_value": 123000000000}
                ],
                "bounce_candidates": [
                    {"name": "카카오", "code": "035720", "change_pct": -6.2, "close": 41200}
                ],
            }
        )

        self.assertIn("수급이 몰리는 종목", text)
        self.assertIn("오늘 거래대금 상위", text)
        self.assertIn("낙폭 큰 종목", text)
        self.assertIn("체크 포인트", text)

    def test_format_profile_prioritizes_current_state_and_examples(self):
        text = format_profile(
            {
                "risk_profile": "neutral",
                "monthly_budget": 700000,
                "monthly_income": 5000000,
                "fixed_expenses": 3000000,
            }
        )

        self.assertIn("투자 성향: 중립", text)
        self.assertIn("가용 자금: 2,000,000원", text)
        self.assertIn("빠른 설정 예시", text)
        self.assertIn("자주 쓰는 변경", text)


if __name__ == "__main__":
    unittest.main()
