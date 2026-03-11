import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from api import telegram_bot


class _FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


class _FakeBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text):
        self.sent_messages.append({"chat_id": chat_id, "text": text})


def _make_update(user_id=101, chat_id=202):
    message = _FakeMessage()
    return SimpleNamespace(
        message=message,
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=user_id),
    )


def _make_context(args=None):
    return SimpleNamespace(args=args or [], bot=_FakeBot())


class TelegramBotHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cmd_start_highlights_core_commands(self):
        update = _make_update()
        context = _make_context()

        await telegram_bot.cmd_start(update, context)

        self.assertIn("/now", update.message.replies[-1])
        self.assertIn("/action", update.message.replies[-1])
        self.assertIn("/help", update.message.replies[-1])

    async def test_cmd_profile_parses_korean_income_and_expenses(self):
        update = _make_update()
        context = _make_context(["공격", "소득", "500만", "지출", "300만"])

        with patch.object(
            telegram_bot,
            "update_profile",
            return_value={
                "risk_profile": "aggressive",
                "monthly_budget": 0,
                "monthly_income": 5000000,
                "fixed_expenses": 3000000,
            },
        ) as mock_update_profile:
            with patch.object(
                telegram_bot,
                "format_profile",
                return_value="formatted-profile",
            ):
                await telegram_bot.cmd_profile(update, context)

        mock_update_profile.assert_called_once_with(
            101, "공격", None, 5000000, 3000000
        )
        self.assertIn("설정이 저장되었습니다.", update.message.replies[-1])
        self.assertIn("formatted-profile", update.message.replies[-1])

    async def test_cmd_action_sends_progress_and_final_message(self):
        update = _make_update()
        context = _make_context()

        prices = {"vix": {"value": 18.0, "change_pct": -1.2}}
        scenario = {"key": "rate_easing", "name": "완화 시나리오", "score": 1.0}
        profile = {"risk_profile": "neutral", "monthly_budget": 1000000}
        action_result = {"mode_key": "aggressive"}
        budget = {"monthly_budget": 1000000}

        with patch.object(telegram_bot, "fetch_all_prices", return_value=prices), \
             patch.object(telegram_bot, "find_best_scenario", return_value=scenario), \
             patch.object(telegram_bot, "get_recent_events", return_value=[]), \
             patch.object(telegram_bot, "get_profile", return_value=profile), \
             patch.object(telegram_bot, "get_action_result", return_value=action_result), \
             patch.object(telegram_bot, "calculate_budget", return_value=budget), \
             patch.object(telegram_bot, "format_action_card", return_value="final-action-card"), \
             patch.object(telegram_bot, "_send_message", new=AsyncMock()) as mock_send_message:
            await telegram_bot.cmd_action(update, context)

        self.assertEqual(update.message.replies[0], "행동 모드 분석 중...")
        mock_send_message.assert_awaited_once_with(202, "final-action-card", context)

    async def test_cmd_action_handles_missing_prices_with_guidance(self):
        update = _make_update()
        context = _make_context()

        with patch.object(telegram_bot, "fetch_all_prices", return_value={}):
            await telegram_bot.cmd_action(update, context)

        self.assertEqual(update.message.replies[0], "행동 모드 분석 중...")
        self.assertIn("가격 지표", update.message.replies[-1])
        self.assertIn("/now", update.message.replies[-1])

    async def test_cmd_ask_requires_question(self):
        update = _make_update()
        context = _make_context([])

        await telegram_bot.cmd_ask(update, context)

        self.assertIn("질문을 입력해주세요.", update.message.replies[-1])

    async def test_cmd_now_uses_cached_events_and_price_summary(self):
        update = _make_update()
        context = _make_context()

        recent_events = [
            {"event_type": "geopolitical_tension", "title": "Test title"},
            {"event_type": "geopolitical_tension", "title": "Duplicate"},
        ]
        prices = {
            "vix": {"value": 21.5, "change_pct": 3.2},
            "kospi": {"value": 2550.0, "change_pct": -0.8},
        }

        with patch.object(telegram_bot, "get_recent_events", return_value=recent_events), \
             patch.object(
                 telegram_bot,
                 "map_event_to_sectors",
                 return_value={"event_type": "geopolitical_tension", "beneficiary": [], "damaged": []},
             ), \
             patch.object(
                 telegram_bot,
                 "format_sector_summary",
                 return_value="[geopolitical_tension]\n  수혜: 방산",
             ), \
             patch.object(telegram_bot, "fetch_all_prices", return_value=prices), \
             patch.object(telegram_bot, "_send_message", new=AsyncMock()) as mock_send_message:
            await telegram_bot.cmd_now(update, context)

        self.assertEqual(update.message.replies[0], "분석 중...")
        sent_text = mock_send_message.await_args.args[1]
        self.assertIn("GeoLight — 현재 이벤트 요약", sent_text)
        self.assertIn("한줄 해석:", sent_text)
        self.assertIn("주요 지표", sent_text)
        self.assertIn("VIX 공포지수: 21.50 (+3.20%)", sent_text)

    async def test_cmd_alert_explains_thresholds_with_examples(self):
        update = _make_update()
        context = _make_context()

        await telegram_bot.cmd_alert(update, context)

        text = update.message.replies[-1]
        self.assertIn("한줄 해석:", text)
        self.assertIn("예시", text)
        self.assertIn("USD/KRW", text)

    async def test_cmd_hot_hides_raw_exception(self):
        update = _make_update()
        context = _make_context()

        with patch.object(
            telegram_bot,
            "detect_hot_stocks",
            side_effect=RuntimeError("boom"),
        ):
            await telegram_bot.cmd_hot(update, context)

        self.assertEqual(update.message.replies[0], "종목 데이터 조회 중...")
        self.assertIn("/hot 결과를 지금 만들지 못했습니다.", update.message.replies[-1])
        self.assertNotIn("boom", update.message.replies[-1])

    async def test_cmd_help_groups_commands_by_use_case(self):
        update = _make_update()
        context = _make_context()

        await telegram_bot.cmd_help(update, context)

        text = update.message.replies[-1]
        self.assertIn("지금 시장 보기", text)
        self.assertIn("오늘 행동 정하기", text)
        self.assertIn("내 설정", text)
        self.assertIn("질문하기", text)

    async def test_cmd_scenario_sends_scenario_summary(self):
        update = _make_update()
        context = _make_context()

        prices = {
            "vix": {"value": 22.0, "change_pct": 1.4},
            "usd_krw": {"value": 1388.0, "change_pct": 0.5},
        }
        scenarios = [
            {"name": "확전 시나리오", "score": 0.5},
            {"name": "완화 시나리오", "score": 0.0},
        ]
        best = {"name": "확전 시나리오", "score": 0.5}

        with patch.object(telegram_bot, "fetch_all_prices", return_value=prices), \
             patch.object(telegram_bot, "get_all_scenarios_status", return_value=scenarios), \
             patch.object(telegram_bot, "find_best_scenario", return_value=best), \
             patch.object(telegram_bot, "format_scenario_card", return_value="scenario-card"), \
             patch.object(telegram_bot, "_send_message", new=AsyncMock()) as mock_send_message:
            await telegram_bot.cmd_scenario(update, context)

        sent_text = mock_send_message.await_args.args[1]
        self.assertIn("GeoLight — 시나리오 투자 지도", sent_text)
        self.assertIn("scenario-card", sent_text)
        self.assertIn("● 확전 시나리오: 50%", sent_text)

    async def test_cmd_budget_uses_auto_budget_when_income_exists(self):
        update = _make_update()
        context = _make_context()

        prices = {"vix": {"value": 17.0, "change_pct": -1.1}}
        profile = {
            "risk_profile": "neutral",
            "monthly_budget": 0,
            "monthly_income": 5000000,
            "fixed_expenses": 3000000,
        }
        action_result = {"mode_key": "normal_dca"}
        investable = {
            "disposable": 2000000,
            "invest_ratio": 0.35,
            "invest_amount": 700000,
            "savings_amount": 910000,
            "emergency_amount": 390000,
        }

        with patch.object(telegram_bot, "fetch_all_prices", return_value=prices), \
             patch.object(telegram_bot, "find_best_scenario", return_value=None), \
             patch.object(telegram_bot, "get_recent_events", return_value=[]), \
             patch.object(telegram_bot, "get_profile", return_value=profile), \
             patch.object(telegram_bot, "get_action_result", return_value=action_result), \
             patch.object(telegram_bot, "calculate_investable_amount", return_value=investable), \
             patch.object(telegram_bot, "calculate_budget", return_value={"monthly_budget": 700000}) as mock_calculate_budget, \
             patch.object(telegram_bot, "format_budget_card", return_value="budget-card"), \
             patch.object(telegram_bot, "_send_message", new=AsyncMock()) as mock_send_message:
            await telegram_bot.cmd_budget(update, context)

        mock_calculate_budget.assert_called_once_with(
            action_mode="normal_dca",
            monthly_budget=700000,
            risk_profile="neutral",
        )
        mock_send_message.assert_awaited_once_with(202, "budget-card", context)

    async def test_cmd_hot_sends_progress_and_result(self):
        update = _make_update()
        context = _make_context()

        with patch.object(
            telegram_bot,
            "detect_hot_stocks",
            return_value={"top_volume": [], "bounce_candidates": []},
        ), patch.object(
            telegram_bot,
            "format_hot_stocks",
            return_value="formatted-hot-stocks",
        ), patch.object(
            telegram_bot,
            "_send_message",
            new=AsyncMock(),
        ) as mock_send_message:
            await telegram_bot.cmd_hot(update, context)

        self.assertEqual(update.message.replies[0], "종목 데이터 조회 중...")
        sent_text = mock_send_message.await_args.args[1]
        self.assertIn("GeoLight — 관심 급증 종목", sent_text)
        self.assertIn("formatted-hot-stocks", sent_text)


if __name__ == "__main__":
    unittest.main()
