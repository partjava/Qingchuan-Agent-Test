import tempfile
import unittest
from pathlib import Path


class AgentToolsTests(unittest.TestCase):
    def test_real_place_alias_and_unknown_place(self):
        from core.agent.tools import CampusTools
        tools=CampusTools(None)
        r=tools.lookup_place({'name':'图书馆'},10)
        self.assertEqual(r['places'][0]['id'],'library')
        self.assertEqual(tools.lookup_place({'name':'不存在的教学楼'},10)['status'],'not_found')

    def test_route_uses_packaged_road_graph_not_language_model(self):
        from core.agent.tools import CampusTools
        r=CampusTools(None).plan_route({'from_id':'south_gate','to_id':'library'},10)
        self.assertIn(r['status'],['ok','no-access','disconnected'])
        if r['status']=='ok':
            self.assertGreater(len(r['points']),2)
            self.assertIn('示意',r['facts'][0]['text'])
            self.assertNotIn('米',r['facts'][0]['text'])
        self.assertEqual(CampusTools(None).plan_route({'from_id':'unknown','to_id':'library'},10)['status'],'not_found')

    def test_search_does_not_invoke_model_and_only_uses_linked_evidence(self):
        from core.agent.tools import CampusTools
        class Engine:
            def query(self,q,**kwargs):
                assert kwargs['allow_generation'] is False
                return {'answer':'不要使用自由答案123456', 'citations':[{'index':1,'source':'library','title':'借阅','url':'https://example.org','full_text':'原文'}],
                        'evidence':[{'text':'借阅规则见原文。','citation_index':1}]}
        r=CampusTools(Engine()).search_knowledge({'query':'借阅规则'},5)
        self.assertEqual(r['facts'][0]['text'],'借阅规则见原文。')
        self.assertNotIn('123456',str(r))


class StoreTests(unittest.TestCase):
    def test_session_isolation_and_clear_invalidates_inflight_save(self):
        from core.agent.store import AgentStore
        with tempfile.TemporaryDirectory() as temp:
            store=AgentStore(Path(temp)/'agent.db')
            version=store.version('a')
            result={'answer':'请补充起点。','agent':{'run_id':'a1','model_called':True,'trace':[]}}
            self.assertTrue(store.save('a','去图书馆',result,version))
            self.assertEqual(store.history('b'),[])
            self.assertEqual(len(store.history('a')),1)
            store.clear('a')
            self.assertFalse(store.save('a','过期请求',result,version))
            self.assertEqual(store.history('a'),[])

    def test_storage_redacts_credentials(self):
        from core.agent.store import AgentStore
        with tempfile.TemporaryDirectory() as temp:
            store=AgentStore(Path(temp)/'agent.db')
            store.save('a','api_key=secret123',{'answer':'sk-secret456','agent':{'run_id':'id1','trace':[]}},store.version('a'))
            self.assertNotIn('secret',str(store.history('a')))

if __name__=='__main__': unittest.main()
