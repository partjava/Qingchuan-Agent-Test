"""Real HTTP transport against a local scripted server, not a live model benchmark."""
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from core.agent.planner import JsonPlanner
from core.agent.runtime import AgentRuntime


class PlannerHttpTests(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        received=self.requests
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append({'path':self.path,'payload':payload})
                messages=payload['messages']
                has_observation=any('e1' in m['content'] for m in messages if m['role']=='user')
                action=({'action':'finish','evidence_ids':['e1']} if has_observation else
                        {'action':'tool','tool':'search_knowledge','arguments':{'query':'图书馆借还时间'}})
                body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(action)}}],
                                 'message':{'content':json.dumps(action)}}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()

    def test_cloud_transport_observation_round_trip(self):
        p=JsonPlanner(api_key='test-only-key',model='local-http-fixture',api_url=self.url+'/v1')
        tools={'search_knowledge':lambda args,timeout:{'status':'ok','facts':[{'text':'离线HTTP样例事实','source':'fixture'}]}}
        r=AgentRuntime(p,tools).run('查询')
        self.assertEqual(r['agent']['stop_reason'],'completed')
        self.assertEqual(len(self.requests),2)
        self.assertEqual(self.requests[0]['path'],'/v1/chat/completions')
        self.assertIn('e1',str(self.requests[-1]['payload']))
        self.assertNotIn('test-only-key',str(r))

    def test_ollama_uses_same_decision_contract(self):
        p=JsonPlanner(use_ollama=True,ollama_url=self.url,ollama_model='local-fixture')
        result=p([{'role':'user','content':'查询'}],3)
        self.assertEqual(json.loads(result)['action'],'tool')
        self.assertEqual(self.requests[0]['path'],'/api/chat')
        self.assertEqual(self.requests[0]['payload']['format'],'json')

    def test_credential_in_endpoint_rejected(self):
        with self.assertRaises(ValueError):JsonPlanner(api_url='http://user:secret@localhost')

if __name__=='__main__':unittest.main()
