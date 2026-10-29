import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch

import requests

from core.deepseek_client import GenerationResult, canonicalize_model, generate_from_evidence


class DeepSeekClientTests(unittest.TestCase):
    def call(self, **kwargs):
        return generate_from_evidence('几点开放？', [{'text': '无关的完整文章'}],
            [{'index': 3, 'evidence_text': '每日07:30开放。'}], 'private-key', **kwargs)

    @patch('core.deepseek_client.requests.post')
    def test_official_contract_and_selected_evidence_only(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'choices': [{'finish_reason': 'stop',
            'message': {'content': '每日07:30开放。[3]', 'reasoning_content': '秘密推理'}}]}
        result = self.call()
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.content, '每日07:30开放。[3]')
        args, kw = post.call_args
        self.assertEqual(args, ('https://api.deepseek.com/chat/completions',))
        self.assertEqual(kw['headers']['Authorization'], 'Bearer private-key')
        self.assertEqual(kw['timeout'], (5, 90))
        payload = kw['json']
        self.assertEqual(payload['model'], 'deepseek-flash')
        self.assertEqual(payload['thinking'], {'type': 'disabled'})
        self.assertEqual(payload['max_tokens'], 2048)
        self.assertFalse(payload['stream'])
        self.assertNotIn('无关的完整文章', str(payload['messages']))
        self.assertIn('每日07:30开放。', str(payload['messages']))
        self.assertIn('[3]', str(payload['messages']))
        self.assertNotIn('temperature', payload)
        post.assert_called_once()
        with self.assertRaises(FrozenInstanceError):
            result.status = 'changed'

    def test_canonical_model_migration(self):
        for alias in ('deepseek-chat', 'deepseek-reasoner', 'deepseek-v4-flash',
                      'deepseek-v4.1-flash', 'deepseek-flash'):
            self.assertEqual(canonicalize_model(alias), 'deepseek-flash')
        self.assertEqual(canonicalize_model('deepseek-v4-pro'), 'deepseek-v4-pro')
        with self.assertRaises(ValueError):
            canonicalize_model('custom-random')

    @patch('core.deepseek_client.requests.post')
    def test_thinking_has_explicit_toggle_and_larger_budget(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': '答案'}}]}
        self.call(thinking=True)
        self.assertEqual(post.call_args.kwargs['json']['thinking'], {'type': 'enabled'})
        self.assertEqual(post.call_args.kwargs['json']['max_tokens'], 8192)
        self.assertNotIn('top_p', post.call_args.kwargs['json'])

    @patch('core.deepseek_client.requests.post')
    def test_http_errors_are_safe_and_never_retried(self, post):
        for status in (400, 401, 402, 404, 429, 500, 503):
            with self.subTest(status=status):
                post.reset_mock()
                post.return_value = Mock(status_code=status, text='private-key raw secret')
                result = self.call()
                self.assertEqual(result.status, 'failed')
                self.assertEqual(result.error_code, 'http_' + str(status))
                self.assertIsNone(result.content)
                self.assertNotIn('private-key', str(result))
                self.assertNotIn('raw secret', str(result))
                post.return_value.json.assert_not_called()
                post.assert_called_once()

    @patch('core.deepseek_client.requests.post')
    def test_connection_and_timeout_are_safe(self, post):
        for exception, code in ((requests.Timeout('private-key'), 'timeout'),
                                (requests.ConnectionError('private-key'), 'network_error')):
            post.side_effect = exception
            result = self.call()
            self.assertEqual(result.error_code, code)
            self.assertNotIn('private-key', str(result))

    @patch('core.deepseek_client.requests.post')
    def test_invalid_json_and_malformed_content(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.side_effect = ValueError('private-key')
        self.assertEqual(self.call().error_code, 'invalid_json')
        post.return_value.json.side_effect = None
        for body in (None, [], {}, {'choices': []}, {'choices': [None]},
                     {'choices': [{'message': None}]},
                     {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': '不能当最终答案'}}]},
                     {'choices': [{'message': {'content': 123}}]},
                     {'choices': [{'message': {'content': ['unsafe']}}]}):
            post.return_value.json.return_value = body
            self.assertEqual(self.call().error_code, 'invalid_response')
        for content in ('', '   ', None):
            post.return_value.json.return_value = {'choices': [{'finish_reason': 'stop',
                'message': {'content': content, 'reasoning_content': '不能作为答案'}}]}
            self.assertEqual(self.call().error_code, 'empty_content')

    @patch('core.deepseek_client.requests.post')
    def test_truncated_content_is_not_used(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'choices': [{'finish_reason': 'length',
            'message': {'content': '半句', 'reasoning_content': 'reason'}}]}
        result = self.call()
        self.assertEqual(result.status, 'truncated')
        self.assertEqual(result.error_code, 'length')
        self.assertIsNone(result.content)

    @patch('core.deepseek_client.requests.post')
    def test_invalid_inputs_do_not_make_paid_requests(self, post):
        self.assertEqual(self.call(model='random').error_code, 'unsupported_model')
        self.assertEqual(generate_from_evidence('问题', [], [], 'key').error_code, 'invalid_evidence')
        self.assertEqual(generate_from_evidence('问题', [], [{'index': 1, 'evidence_text': '原文'}], '').error_code, 'missing_api_key')
        post.assert_not_called()

    @patch('core.deepseek_client.requests.post')
    def test_evidence_numbering_must_be_unique_and_explicit(self, post):
        for citations in ([None], [{'index': True, 'evidence_text': '原文'}],
                          [{'index': 0, 'evidence_text': '原文'}],
                          [{'index': 1, 'evidence_text': ['wrong type']}],
                          [{'index': 1, 'evidence_text': ' '}],
                          [{'index': 1, 'evidence_text': '原文'}, {'index': 1, 'evidence_text': '其他'}]):
            result = generate_from_evidence('问题', [], citations, 'private-key')
            self.assertEqual(result.error_code, 'invalid_evidence')
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class ReadingBudgetTests(unittest.TestCase):
    @patch('core.deepseek_client.requests.post')
    def test_oversized_collection_uses_labeled_context_around_evidence(self, post):
        import json
        article='前文'*15000+'明确证据：奖学金每人3000元。'+'后文'*15000
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'奖学金每人3000元。[1]'}}]}
        generate_from_evidence('奖学金多少钱',[],[dict(index=1,evidence_text='明确证据：奖学金每人3000元。',full_text=article)],'offline-key')
        entry=json.loads(post.call_args.kwargs['json']['messages'][1]['content'])['selected_evidence'][0]
        self.assertLessEqual(len(entry['article']),16000)
        self.assertIn('明确证据：奖学金每人3000元',entry['article'])
        self.assertEqual(entry['context_kind'],'原文上下文节选')
