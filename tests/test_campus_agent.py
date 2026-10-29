"""Agent contract tests: a scripted decision source is not a real model evaluation."""
import importlib.util
import unittest
import time


class CampusAgentTests(unittest.TestCase):
    def runtime(self, actions, tools=None, **options):
        self.assertIsNotNone(importlib.util.find_spec('core.agent.runtime'), 'Agent runtime must exist')
        from core.agent.runtime import AgentRuntime
        self.messages = []
        def planner(messages, remaining):
            self.messages.append(messages)
            return actions.pop(0)
        self.calls = []
        def search(args, timeout):
            self.calls.append(args)
            return {'status': 'ok', 'facts': [{'text': '图书馆工作日21:30停止借还。', 'source': 'library', 'title': '开放时间', 'url': 'https://example.org/library'}]}
        return AgentRuntime(planner, tools or {'search_knowledge': search}, **options)

    def test_tool_observation_drives_next_decision_and_evidence_answer(self):
        runtime = self.runtime([
            {'action': 'tool', 'tool': 'search_knowledge', 'arguments': {'query': '图书馆借还时间'}},
            {'action': 'finish', 'evidence_ids': ['e1']},
        ])
        result = runtime.run('图书馆几点停止借还？')
        self.assertEqual(result['agent']['stop_reason'], 'completed')
        self.assertIn('21:30', result['answer'])
        self.assertEqual(result['citations'][0]['index'], 1)
        self.assertIn('e1', str(self.messages[1]))
        self.assertEqual(len(self.calls), 1)

    def test_model_cannot_fabricate_answer_or_unknown_evidence(self):
        r = self.runtime([{'action': 'finish', 'evidence_ids': ['e900'], 'answer': '馆长电话123456'}]).run('馆长电话')
        self.assertNotIn('123456', r['answer'])
        self.assertTrue(r['refused'])

    def test_repeated_unknown_tool_is_bounded(self):
        action = {'action': 'tool', 'tool': 'delete_files', 'arguments': {}}
        r = self.runtime([action.copy(), action.copy()]).run('查询')
        self.assertEqual(r['agent']['stop_reason'], 'repeated_action')
        self.assertEqual(r['agent']['trace'][0]['status'], 'unknown_tool')

    def test_exception_is_observation_not_raw_error(self):
        def broken(args, timeout): raise RuntimeError('Authorization: Bearer sk-secret')
        r = self.runtime([
            {'action': 'tool', 'tool': 'search_knowledge', 'arguments': {'query': '图书馆'}},
            {'action': 'clarify', 'question': '请说明需要查询哪项图书馆服务。'},
        ], {'search_knowledge': broken}).run('查询图书馆')
        self.assertTrue(r['clarification'])
        self.assertNotIn('sk-secret', str(r))
        self.assertEqual(r['agent']['trace'][0]['status'], 'tool_error')

    def test_step_budget_stops(self):
        r = self.runtime([{'action':'tool','tool':'search_knowledge','arguments':{'query':'图书馆'}}], max_steps=1).run('图书馆')
        self.assertEqual(r['agent']['stop_reason'], 'step_limit')

    def test_invalid_model_json_is_bounded(self):
        r = self.runtime(['not json', 'still not json']).run('查询')
        self.assertEqual(r['agent']['stop_reason'], 'invalid_decision')

    def test_missing_parameters_do_not_execute(self):
        r = self.runtime([{'action':'tool','tool':'search_knowledge','arguments':{}}, {'action':'clarify','question':'请补充事项。'}]).run('查询')
        self.assertEqual(self.calls, [])
        self.assertEqual(r['agent']['trace'][0]['status'], 'invalid_arguments')

    def test_timeout_is_reported(self):
        def slow(messages, remaining): raise TimeoutError()
        from core.agent.runtime import AgentRuntime
        r = AgentRuntime(slow, {}).run('查询')
        self.assertEqual(r['agent']['stop_reason'], 'timeout')

    def test_no_model_does_not_claim_autonomy(self):
        from core.agent.runtime import AgentRuntime
        r = AgentRuntime(None, {}).run('查询')
        self.assertEqual(r['agent']['stop_reason'], 'not_configured')
        self.assertFalse(r['agent']['model_called'])

    def test_nested_invalid_arguments_never_echo_credentials(self):
        r=self.runtime([{'action':'tool','tool':'search_knowledge','arguments':{'query':{'password':'secret123'}}},
                        {'action':'finish','evidence_ids':[]}]).run('查询')
        self.assertNotIn('secret123',str(r))

    def test_quoted_json_credentials_are_redacted(self):
        from core.agent.runtime import redact
        self.assertNotIn('secret123',redact('用户提供 {"api_key": "secret123"}'))

    def test_blocked_planner_is_bounded_by_wall_time(self):
        from core.agent.runtime import AgentRuntime
        def slow(messages,remaining):
            time.sleep(.3)
            return {'action':'clarify','question':'请补充。'}
        start=time.monotonic()
        r=AgentRuntime(slow,{},time_budget=.04).run('查询')
        self.assertEqual(r['agent']['stop_reason'],'timeout')
        self.assertLess(time.monotonic()-start,.2)

    def test_safe_clarification_does_not_claim_task_completed(self):
        r = self.runtime([{'action':'clarify','question':'请问你从哪里出发？'}]).run('帮我安排去图书馆的路线')
        self.assertTrue(r['clarification'])
        self.assertEqual(r['agent']['stop_reason'], 'clarification')

if __name__ == '__main__': unittest.main()
