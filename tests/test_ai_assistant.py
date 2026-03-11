import unittest
from unittest.mock import Mock

import requests

from domain.ai_assistant import AIAssistant


class AIAssistantTests(unittest.TestCase):
    def test_ask_hides_raw_exception_message(self):
        assistant = AIAssistant()
        assistant._api_key = "test-key"
        assistant._client = Mock()
        assistant._client.post.side_effect = requests.RequestException("network down")

        text = assistant.ask("test question")

        self.assertIn("문제가 발생했습니다", text)
        self.assertNotIn("network down", text)


if __name__ == "__main__":
    unittest.main()
