"""포트폴리오 관리 테스트."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.db import init_db
from domain.portfolio import (
    add_position,
    remove_position,
    get_user_positions,
    get_portfolio_summary,
    find_stock_in_sectors,
    analyze_portfolio_vs_scenario,
    format_portfolio,
    format_portfolio_action_advice,
)

# 테스트용 user_id (충돌 방지)
TEST_USER = 88888


class PortfolioTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        # 테스트 전 기존 데이터 정리
        for pos in get_user_positions(TEST_USER):
            remove_position(TEST_USER, pos["stock_name"])

    def tearDown(self):
        # 각 테스트 후 정리
        for pos in get_user_positions(TEST_USER):
            remove_position(TEST_USER, pos["stock_name"])

    def test_find_stock_in_sectors_matches_known_stock(self):
        result = find_stock_in_sectors("삼성전자")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "005930")
        self.assertIn("반도체", result["sectors"])

    def test_find_stock_in_sectors_returns_none_for_unknown(self):
        result = find_stock_in_sectors("없는종목XYZ")
        self.assertIsNone(result)

    def test_add_position_auto_resolves_sector(self):
        pos = add_position(TEST_USER, "삼성전자", 70000, 10)
        self.assertEqual(pos["stock_name"], "삼성전자")
        self.assertEqual(pos["stock_code"], "005930")
        self.assertEqual(pos["sector"], "반도체")
        self.assertEqual(pos["total"], 700000)

    def test_add_position_unknown_stock_still_works(self):
        pos = add_position(TEST_USER, "테스트종목", 5000, 100)
        self.assertEqual(pos["stock_name"], "테스트종목")
        self.assertEqual(pos["stock_code"], "")
        self.assertEqual(pos["sector"], "")
        self.assertEqual(pos["total"], 500000)

    def test_upsert_updates_existing_position(self):
        add_position(TEST_USER, "삼성전자", 70000, 10)
        add_position(TEST_USER, "삼성전자", 72000, 15)
        positions = get_user_positions(TEST_USER)
        samsung = [p for p in positions if p["stock_name"] == "삼성전자"]
        self.assertEqual(len(samsung), 1)
        self.assertEqual(samsung[0]["avg_price"], 72000)
        self.assertEqual(samsung[0]["quantity"], 15)

    def test_remove_position_by_name(self):
        add_position(TEST_USER, "현대차", 200000, 5)
        self.assertTrue(remove_position(TEST_USER, "현대차"))
        positions = get_user_positions(TEST_USER)
        self.assertEqual(len(positions), 0)

    def test_remove_nonexistent_returns_false(self):
        self.assertFalse(remove_position(TEST_USER, "없는종목"))

    def test_portfolio_summary_calculates_totals(self):
        add_position(TEST_USER, "삼성전자", 70000, 10)
        add_position(TEST_USER, "현대차", 200000, 5)
        summary = get_portfolio_summary(TEST_USER)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["total_invested"], 1700000)
        self.assertIn("반도체", summary["sector_weights"])
        self.assertIn("자동차", summary["sector_weights"])

    def test_analyze_portfolio_vs_scenario(self):
        add_position(TEST_USER, "삼성전자", 70000, 10)
        add_position(TEST_USER, "대한항공", 25000, 20)
        analysis = analyze_portfolio_vs_scenario(
            TEST_USER,
            beneficiary_sectors=["반도체", "자동차"],
            damaged_sectors=["항공", "여행"],
        )
        benefited_names = [p["name"] for p in analysis["benefited"]]
        at_risk_names = [p["name"] for p in analysis["at_risk"]]
        self.assertIn("삼성전자", benefited_names)
        self.assertIn("대한항공", at_risk_names)

    def test_format_portfolio_empty(self):
        text = format_portfolio(TEST_USER)
        self.assertIn("보유 종목이 없습니다", text)
        self.assertIn("/portfolio 삼성전자 70000 10", text)
        # 반복 버그 없는지 확인
        self.assertEqual(text.count("종목 추가 방법"), 1)

    def test_format_portfolio_with_positions(self):
        add_position(TEST_USER, "삼성전자", 70000, 10)
        text = format_portfolio(TEST_USER)
        self.assertIn("내 포트폴리오", text)
        self.assertIn("삼성전자", text)
        self.assertIn("700,000원", text)
        self.assertIn("섹터별 비중", text)

    def test_format_portfolio_action_advice_at_risk(self):
        analysis = {
            "benefited": [],
            "at_risk": [{"name": "대한항공", "amount": 500000, "quantity": 20, "sectors": ["항공"]}],
            "neutral": [],
        }
        text = format_portfolio_action_advice(analysis, "hold")
        self.assertIn("주의", text)
        self.assertIn("대한항공", text)
        self.assertIn("추가 매수 보류", text)

    def test_format_portfolio_action_advice_benefited(self):
        analysis = {
            "benefited": [{"name": "삼성전자", "amount": 700000, "quantity": 10, "sectors": ["반도체"]}],
            "at_risk": [],
            "neutral": [],
        }
        text = format_portfolio_action_advice(analysis, "normal_dca")
        self.assertIn("수혜", text)
        self.assertIn("삼성전자", text)


if __name__ == "__main__":
    unittest.main()
