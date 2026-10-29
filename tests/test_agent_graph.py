"""Framework integration checks; deterministic planners do not measure LLM quality."""
import copy
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.agent.runtime import AgentRuntime


CALL = {'action': 'tool', 'tool': 'search_knowledge', 'arguments': {'query': '借还时间'}}
FACT = {'text': '图书馆工作日21:30停止借还，22:00闭馆。', 'source': 'library'}
GOOD = {'action': 'finish', 'evidence_ids': ['e1'], 'plan': [
    {'instruction': '建议先去图书馆还书。', 'evidence_ids': ['e1']}]}


def runtime_for(actions, **options):
    actions = copy.deepcopy(actions)
    return AgentRuntime(lambda messages, remaining: actions.pop(0), {
        'search_knowledge': lambda args, timeout: {'status': 'ok', 'facts': [FACT]},
    }, **options)


class AgentGraphTests(unittest.TestCase):
    def test_compiled_graph_runs_separate_decision_tool_verification_nodes(self):
        from langgraph.graph.state import CompiledStateGraph
        runtime = runtime_for([CALL, GOOD], require_plan=True)
        self.assertIsInstance(getattr(runtime, 'graph', None), CompiledStateGraph)
        events = list(runtime.graph.stream(runtime._initial_state('还书', []),
                                          config={'recursion_limit': 40}, stream_mode='updates'))
        self.assertEqual([next(iter(event)) for event in events],
                         ['decide', 'tools', 'decide', 'verify', 'finish'])
        result = events[-1]['finish']['result']
        self.assertEqual(result['agent']['framework'], 'LangGraph')
        self.assertEqual(result['agent']['stop_reason'], 'completed')
        self.assertEqual(result['agent']['plan_status'], 'checked')
        self.assertIn('[1]', result['answer'])

    def test_failed_verification_routes_back_to_model_then_finishes(self):
        bad = copy.deepcopy(GOOD)
        bad['plan'][0]['instruction'] = '建议20:00去图书馆还书。'
        result = runtime_for([CALL, bad, GOOD], require_plan=True).run('还书')
        self.assertEqual(result['agent'].get('graph_nodes'),
                         ['decide', 'tools', 'decide', 'verify', 'decide', 'verify', 'finish'])
        self.assertNotIn('20:00', result['answer'])
        self.assertEqual(result['agent']['trace'][1]['status'], 'plan_rejected')

    def test_eight_decisions_are_not_eight_graph_nodes(self):
        actions = [dict(action='tool', tool='search_knowledge', arguments={'query': str(i)})
                   for i in range(7)] + [GOOD]
        result = runtime_for(actions, max_steps=8, require_plan=True).run('还书')
        self.assertEqual(result['agent'].get('framework'), 'LangGraph')
        self.assertEqual(result['agent']['stop_reason'], 'completed')
        self.assertEqual(result['agent']['graph_nodes'].count('decide'), 8)
        self.assertEqual(len(result['agent']['trace']), 7)

    def test_step_limit_keeps_evidence_without_ninth_model_call(self):
        calls = []
        def planner(messages, remaining):
            calls.append(remaining)
            return dict(action='tool', tool='search_knowledge', arguments={'query': str(len(calls))})
        result = AgentRuntime(planner, {'search_knowledge': lambda a,t: {'facts': [FACT]}}).run('查询')
        self.assertEqual(result['agent'].get('framework'), 'LangGraph')
        self.assertEqual(len(calls), 8)
        self.assertEqual(result['agent']['stop_reason'], 'step_limit')
        self.assertEqual(len(result['evidence']), 1)

    def test_graph_loop_uses_requested_budget_above_default_recursion_limit(self):
        actions = [dict(action='tool', tool='search_knowledge', arguments={'query': str(i)})
                   for i in range(30)]
        result = runtime_for(actions, max_steps=30).run('查询')
        self.assertEqual(result['agent'].get('framework'), 'LangGraph')
        self.assertEqual(result['agent']['stop_reason'], 'step_limit')
        self.assertEqual(len(result['agent']['trace']), 30)

    def test_invalid_output_at_last_step_stops_without_retrying(self):
        result = runtime_for(['bad json'], max_steps=1).run('查询')
        self.assertEqual(result['agent'].get('graph_nodes'), ['decide', 'finish'])
        self.assertEqual(result['agent']['stop_reason'], 'step_limit')

    def test_unconfigured_model_still_finishes_via_graph(self):
        result = AgentRuntime(None, {}).run('查询')
        self.assertEqual(result['agent'].get('graph_nodes'), ['decide', 'finish'])
        self.assertFalse(result['agent']['model_called'])
        self.assertEqual(result['agent']['stop_reason'], 'not_configured')

    def test_slow_model_returns_before_its_worker_finishes(self):
        def slow(messages, remaining):
            time.sleep(.3)
            return {'action': 'clarify', 'question': '迟到回复'}
        runtime = AgentRuntime(slow, {}, time_budget=.04)
        start = time.monotonic()
        result = runtime.run('查询')
        self.assertEqual(result['agent'].get('framework'), 'LangGraph')
        self.assertEqual(result['agent']['stop_reason'], 'timeout')
        self.assertLess(time.monotonic() - start, .22)
        self.assertNotIn('迟到回复', result['answer'])

    def test_blocked_tool_times_out_without_accepting_late_facts(self):
        def slow_tool(args, timeout):
            time.sleep(.3)
            return {'facts': [{'text': '迟到工具事实', 'source': 'late'}]}
        runtime = AgentRuntime(lambda m,t: CALL, {'search_knowledge': slow_tool}, time_budget=.04)
        start = time.monotonic()
        result = runtime.run('查询')
        self.assertLess(time.monotonic()-start, .22)
        self.assertEqual(result['agent']['framework'], 'LangGraph')
        self.assertEqual(result['agent']['stop_reason'], 'timeout')
        self.assertEqual(result['agent']['trace'][0]['status'], 'tool_timeout')
        self.assertEqual(result['evidence'], [])
        self.assertNotIn('迟到工具事实', result['answer'])

    def test_same_runtime_can_be_reused_without_history_or_evidence_leak(self):
        def planner(messages, remaining):
            return CALL if len(messages) == 2 and '查资料' in messages[-1]['content'] else GOOD
        runtime = AgentRuntime(planner, {'search_knowledge': lambda a,t: {'facts': [FACT]}})
        first = runtime.run('查资料')
        second = runtime.run('无查询')
        self.assertEqual(second['agent'].get('framework'), 'LangGraph')
        self.assertEqual(first['agent']['stop_reason'], 'completed')
        self.assertEqual(second['agent']['stop_reason'], 'plan_rejected')
        self.assertEqual(second['evidence'], [])
        self.assertNotEqual(first['agent']['run_id'], second['agent']['run_id'])

    def test_concurrent_graph_invocations_do_not_share_clarifications(self):
        import json
        def planner(messages, remaining):
            task = json.loads(messages[1]['content'])['task']
            return {'action': 'clarify', 'question': '请补充' + task}
        runtime = AgentRuntime(planner, {})
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(runtime.run, ['甲', '乙', '丙', '丁']))
        for name, result in zip(['甲', '乙', '丙', '丁'], results):
            self.assertEqual(result['agent'].get('graph_nodes'), ['decide', 'finish'])
            self.assertEqual(result['answer'], '需要补充：请补充' + name)
        self.assertEqual(len({r['agent']['run_id'] for r in results}), 4)

    def test_api_history_stores_framework_metadata_and_keeps_response_contract(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.agent.store import AgentStore
        from web.agent_api import create_agent_router
        with tempfile.TemporaryDirectory() as folder:
            app = FastAPI()
            app.include_router(create_agent_router(lambda: None,
                AgentStore(Path(folder) / 'agent.db'),
                lambda req: lambda m,t: {'action': 'clarify', 'question': '请补充起点。'}))
            with TestClient(app) as client:
                result = client.post('/api/agent/chat', json={'question': '去图书馆', 'session_id': 'graph'}).json()
                self.assertEqual(result['agent'].get('framework'), 'LangGraph')
                self.assertTrue(result['agent']['saved'])
                self.assertTrue({'answer', 'citations', 'evidence', 'navigation', 'target_landmark'} <= result.keys())
                stored = client.get('/api/agent/runs', params={'session_id': 'graph'}).json()['runs']
                self.assertEqual(stored[0]['result']['agent']['framework'], 'LangGraph')

    def test_api_clear_during_graph_execution_discards_late_result(self):
        import threading
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.agent.store import AgentStore
        from web.agent_api import create_agent_router
        entered, release = threading.Event(), threading.Event()
        def planner(messages, remaining):
            entered.set()
            release.wait(2)
            return {'action': 'clarify', 'question': '迟到的会话回复'}
        with tempfile.TemporaryDirectory() as folder:
            app = FastAPI()
            app.include_router(create_agent_router(lambda: None,
                AgentStore(Path(folder) / 'agent.db'), lambda req: planner))
            with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(client.post, '/api/agent/chat',
                                     json={'question': '图书馆', 'session_id': 'cleared'})
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(client.delete('/api/agent/runs',
                        params={'session_id': 'cleared'}).status_code, 200)
                finally:
                    release.set()
                result = future.result(timeout=3).json()
                self.assertEqual(result['agent']['framework'], 'LangGraph')
                self.assertEqual(result['agent']['stop_reason'], 'session_cleared')
                self.assertFalse(result['agent']['saved'])
                self.assertNotIn('迟到的会话回复', result['answer'])
                self.assertEqual(client.get('/api/agent/runs',
                    params={'session_id': 'cleared'}).json()['runs'], [])


if __name__ == '__main__':
    unittest.main()
