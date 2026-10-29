import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient


class AgentApiTests(unittest.TestCase):
    def setUp(self):
        from web.agent_api import create_agent_router
        from core.agent.store import AgentStore
        self.temp=tempfile.TemporaryDirectory()
        self.store=AgentStore(Path(self.temp.name)/'agent.db')
        self.seen=[]
        def factory(req):
            def planner(messages, remaining):
                self.seen.append(str(messages))
                return {'action':'clarify','question':'请补充起点。'}
            return planner if req.deepseek_key else None
        app=FastAPI();app.include_router(create_agent_router(lambda:None,self.store,factory))
        self.client=TestClient(app)

    def tearDown(self):self.client.close();self.temp.cleanup()

    def test_unconfigured_and_request_constraints(self):
        r=self.client.post('/api/agent/chat',json={'question':'查图书馆','session_id':'a'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['agent']['stop_reason'],'not_configured')
        self.assertEqual(self.client.post('/api/agent/chat',json={'question':' ','session_id':'a'}).status_code,422)
        self.assertEqual(self.client.post('/api/agent/chat',json={'question':'查'}).status_code,422)

    def test_history_is_authoritative_and_scoped(self):
        self.client.post('/api/agent/chat',json={'question':'从南大门出发','session_id':'a','deepseek_key':'sk-fake'})
        self.client.post('/api/agent/chat',json={'question':'去图书馆','session_id':'a','deepseek_key':'sk-fake'})
        self.assertIn('从南大门出发',self.seen[-1])
        self.client.post('/api/agent/chat',json={'question':'它在哪里','session_id':'b','deepseek_key':'sk-fake',
                         'history':[{'role':'user','content':'来自另一会话的消息'}]})
        self.assertNotIn('从南大门出发',self.seen[-1])
        self.assertNotIn('来自另一会话',self.seen[-1])
        r=self.client.get('/api/agent/runs',params={'session_id':'b'})
        self.assertEqual(len(r.json()['runs']),1)
        self.assertNotIn('sk-fake',r.text)
        self.client.delete('/api/agent/runs',params={'session_id':'a'})
        self.assertEqual(self.client.get('/api/agent/runs',params={'session_id':'a'}).json()['runs'],[])

    def test_offline_quality_not_claimed_live(self):
        r=self.client.post('/api/agent/quality/run')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['kind'],'offline_contract')
        self.assertFalse(r.json()['real_model_evaluation'])

if __name__=='__main__':unittest.main()

class AgentHistorySessionTests(AgentApiTests):
    def test_session_list_survives_reopening_store_and_delete_is_scoped(self):
        for sid,q in [('a','还书'),('b','选课'),('a','从南门出发')]:
            self.client.post('/api/agent/chat',json={'question':q,'session_id':sid,'deepseek_key':'fake'})
        r=self.client.get('/api/agent/sessions')
        self.assertEqual(r.status_code,200)
        sessions=r.json()['sessions']
        self.assertEqual([s['session_id'] for s in sessions],['a','b'])
        self.assertEqual(sessions[0]['title'],'还书')
        self.assertEqual(sessions[0]['turn_count'],2)
        from core.agent.store import AgentStore
        self.assertEqual(len(AgentStore(self.store.path).sessions()),2)
        self.client.delete('/api/agent/runs',params={'session_id':'a'})
        self.assertEqual([s['session_id'] for s in self.client.get('/api/agent/sessions').json()['sessions']],['b'])
        self.assertEqual(len(self.client.get('/api/agent/runs',params={'session_id':'b','limit':200}).json()['runs']),1)
