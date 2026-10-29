import unittest
from core.query_understanding import analyze_query
from core.rag_engine import QingchuanRagEngine
from tests import test_rag_pipeline

class CanteenLocationTests(unittest.TestCase):
    def test_generic_canteen_not_forced_to_first(self):
        analysis=analyze_query('武汉晴川学院食堂在哪？')
        self.assertNotIn('一食堂',analysis['rewritten_query'])
        self.assertEqual(analysis['slots']['subject'],['食堂'])

    def test_location_missing_still_has_map_target(self):
        engine=test_rag_pipeline.RagPipelineTests().engine('食堂有三层，提供各类餐饮服务。')
        result=engine.query('食堂在哪里？',allow_generation=False)
        self.assertEqual(result['target_landmark']['id'],'canteen_main')
        self.assertIn('示意图',result['answer'])

    def test_explicit_missing_location_can_be_stated_naturally(self):
        self.assertTrue(QingchuanRagEngine._grounded_generation(
            '根据现有公开资料，原文未明确记载食堂的具体位置（如所在楼栋、校园内方位等）。',[],question='食堂在哪？'))

    def test_canteen_event_and_dorm_description_are_not_canteen_address(self):
        from core.evidence import select_evidence
        chunks=[dict(source='campus_landmarks',title='校园',text='楼层与功能导览：寝1栋至寝4栋为男生公寓园区（近大食堂与运动场）。\n文化节在食堂三楼举行。')]
        self.assertEqual(select_evidence('食堂在哪里？',chunks),[])
