import unittest
from pydantic import ValidationError
from web.schemas import ChatRequest


class ChatSchemaTests(unittest.TestCase):
    def test_history_and_bounds(self):
        req = ChatRequest(question='那周末呢', history=[{'role': 'user', 'content': '图书馆几点开'}])
        self.assertEqual(req.history[0].role, 'user')
        for kwargs in ({'top_k': 0}, {'mode': 'unknown'}, {'question': 'x'*1001},
                       {'history': [{'role': 'system', 'content': 'x'}]},
                       {'history': [{'role': 'user', 'content': 'x'}]*13}):
            with self.assertRaises(ValidationError):
                ChatRequest(**({'question': 'hello'} | kwargs))

    def test_default_histories_are_isolated(self):
        first, second = ChatRequest(question='a'), ChatRequest(question='b')
        first.history.append('unshared')
        self.assertEqual(second.history, [])

    def test_flash_thinking_defaults_off_and_can_be_enabled(self):
        self.assertFalse(ChatRequest(question='test').thinking)
        self.assertTrue(ChatRequest(question='test', thinking=True).thinking)
