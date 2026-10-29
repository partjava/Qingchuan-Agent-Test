"""Local HTTP integration with real campus tools; no real LLM or paid API calls."""
import argparse
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify(output_dir):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.agent.planner import JsonPlanner
    from core.agent.runtime import AgentRuntime, LANGGRAPH_VERSION
    from core.agent.store import AgentStore
    from core.bge_retriever import BgeSemanticRetriever
    from core.document_loader import load_and_chunk_documents
    from core.hybrid_retriever import HybridRetriever
    from core.rag_engine import QingchuanRagEngine
    from core.tfidf_retriever import TfidfRetriever
    from web.agent_api import create_agent_router

    chunks = load_and_chunk_documents(ROOT / 'data/docs')
    tfidf, bge = TfidfRetriever(chunks), BgeSemanticRetriever(chunks)
    engine = QingchuanRagEngine(tfidf, bge, HybridRetriever(tfidf, bge))
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            messages = payload['messages']
            observations = [json.loads(m['content'].split('：', 1)[1])
                            for m in messages if m['content'].startswith('工具观察（')]
            requests.append({'path': self.path, 'observations_received': len(observations)})
            sequence = [
                ('current_time', {}),
                ('lookup_place', {'name': '南大门'}),
                ('lookup_place', {'name': '图书馆'}),
                ('search_knowledge', {'query': '图书馆工作日停止借还时间'}),
                ('plan_route', {'from_id': 'south_gate', 'to_id': 'library'}),
            ]
            if len(observations) < len(sequence):
                name, arguments = sequence[len(observations)]
                action = {'action': 'tool', 'tool': name, 'arguments': arguments}
            else:
                ids = [f['evidence_id'] for f in observations[3]['facts']]
                route_ids = [f['evidence_id'] for f in observations[4]['facts']]
                action = {'action': 'finish', 'evidence_ids': ids+route_ids,
                          'plan': [{'instruction': '建议先去图书馆办理还书。', 'evidence_ids': ids[:1]}],
                          'missing': ['图书馆当日临时调整尚待核实']}
            body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps(action, ensure_ascii=False)}}]}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory() as folder:
            store = AgentStore(Path(folder) / 'agent.db')
            app = FastAPI()
            def planner_factory(req):
                return JsonPlanner(api_key='local-fixture-only', model='local-scripted-fixture',
                                   api_url=f'http://127.0.0.1:{server.server_port}/v1')
            app.include_router(create_agent_router(lambda: engine, store, planner_factory))
            with TestClient(app) as client:
                response = client.post('/api/agent/chat', json={
                    'question': '今天从南大门去图书馆还书，查询借还安排并规划示意路线。',
                    'session_id': 'langgraph-smoke'})
                assert response.status_code == 200, response.text
                result = response.json()
                assert result['agent']['framework'] == 'LangGraph'
                assert result['agent']['stop_reason'] == 'completed', result
                assert result['agent']['plan_status'] == 'checked', result
                trace = result['agent']['trace']
                assert [r['tool'] for r in trace] == [name for name, _ in sequence_names()]
                assert all(r['status'] == 'ok' for r in trace), trace
                assert result['navigation'] == {'from_id': 'south_gate', 'to_id': 'library'}
                assert result['agent']['saved']
                assert len(requests) == 6
                assert requests[-1]['observations_received'] == 5
                assert result['citations'] and result['evidence']
                citation_ids = {c['index'] for c in result['citations']}
                assert all(e['citation_index'] in citation_ids for e in result['evidence'])
                assert all(e['evidence_id'] for e in result['evidence'])
                history = client.get('/api/agent/runs', params={'session_id': 'langgraph-smoke'}).json()
                assert history['runs'][0]['result']['agent']['framework'] == 'LangGraph'
                client.delete('/api/agent/runs', params={'session_id': 'langgraph-smoke'})
                assert client.get('/api/agent/runs', params={'session_id': 'langgraph-smoke'}).json()['runs'] == []
        graph = AgentRuntime(None, {}).graph.get_graph()
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / 'workflow.mmd').write_text(graph.draw_mermaid(), encoding='utf-8')
        report = {'kind': 'local_http_integration', 'real_model_evaluation': False,
                  'created_at': datetime.now(timezone.utc).isoformat(),
                  'framework': 'LangGraph', 'framework_version': LANGGRAPH_VERSION,
                  'knowledge_chunks': len(chunks), 'model_requests': requests,
                  'description': '本地脚本模型HTTP服务配合真实知识库、地标、时间、路线工具及临时会话数据库。',
                  'checks': {'api_contract': True, 'all_four_tools': True, 'plan_verified': True,
                             'evidence_links': True, 'navigation': True, 'history_and_clear': True},
                  'result': result}
        (output_dir / 'integration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('LangGraph本地HTTP联调通过：四类工具、方案核验、路线、历史与清空。')
        print(f'框架版本：{LANGGRAPH_VERSION}；模型请求6次；真实模型评测：否。')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def sequence_names():
    return [('current_time', {}), ('lookup_place', {}), ('lookup_place', {}),
            ('search_knowledge', {}), ('plan_route', {})]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'report_work/langgraph_validation')
    verify(parser.parse_args().output_dir)
