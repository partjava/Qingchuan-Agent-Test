import unittest
from core import query_understanding as qu
from core.evidence import select_evidence


def chunk(text, title='图书馆', source='library'):
    return {'text': text, 'title': title, 'source': source}


class FactSlotTests(unittest.TestCase):
    def test_hours_require_opening_relation_and_clock_values(self):
        chunks = [chunk('实验室开放备案申请须在周五15:00前提交。', '实验室备案', 'laboratory'),
                  chunk('实验室全面推进实训开放，工作日开展教学。', '实训新闻', 'news_xxyw'),
                  chunk('教学工作日：周一至周五08:00—20:30全天候连续开放。', '开放时间', 'laboratory')]
        result = select_evidence('实验室几点关门', chunks)
        self.assertTrue(result)
        self.assertTrue(all('20:30' in e['text'] for e in result))

    def test_location_requires_position_relation_and_prefers_topic_policy(self):
        chunks = [chunk('图书馆馆内开展考察交流，落实各项规定。', '图书馆考察', 'news_xxyw'),
                  chunk('政策依据：《图书馆规章制度》与图书馆阅览室规定。', '图书馆政策依据'),
                  chunk('晴川图书馆坐落于惜缘湖畔，建筑地上4层。', '馆藏布局', 'library'),
                  chunk('图书馆在哪里：图书馆位于晴缘湖旁。', '图书馆位置新闻', 'news_xxyw')]
        result = select_evidence('图书馆在哪里', chunks)
        self.assertTrue(result)
        self.assertTrue(all('惜缘湖' in e['text'] for e in result))
        floors = select_evidence('图书馆几层', chunks)
        self.assertTrue(floors)
        self.assertIn('4层', floors[0]['text'])

    def test_library_context_can_anchor_fee_without_repeated_subject(self):
        overdue = chunk('超过规定借期归还的图书，按照每册每天0.1元收取逾期滞还金。', '图书借还与流通规则')
        history = [{'role': 'user', 'content': '图书馆几点关门'}]
        question = qu.plan_subqueries('那逾期收费是多少？', history)[0]['question']
        self.assertTrue(select_evidence(question, [overdue]))
        processing = chunk('遗失图书须购买相同版次的新书赔偿，并缴纳5元加工费。', '图书损坏遗失赔偿')
        self.assertTrue(select_evidence('图书馆丢书买新书赔偿还要交多少加工费？', [processing]))

    def test_introductory_phrase_and_comma_separated_award_fact(self):
        question = '按知识库的标准，国家励志奖学金每年奖励多少元？'
        plan = qu.plan_subqueries(question)
        self.assertEqual(len(plan), 1)
        policy = chunk('国家励志奖学金：奖励品学兼优的家庭经济困难学生，奖励标准为每人每学年5000元。', '国家级奖学金', 'scholarship')
        self.assertTrue(select_evidence(plan[0]['question'], [policy]))
        self.assertEqual(len(qu.plan_subqueries('校训是什么？')), 1)

    def test_each_award_value_binds_its_nearest_grade(self):
        policy = chunk('晴川奖学金一等奖3000元、二等奖2000元。', '晴川奖学金', 'scholarship')
        self.assertTrue(select_evidence('晴川奖学金二等奖多少钱', [policy]))
        wrong = chunk('晴川奖学金一等奖3000元、二等奖10名。', '晴川奖学金', 'scholarship')
        self.assertEqual(select_evidence('晴川奖学金二等奖多少钱', [wrong]), [])
        total = chunk('晴川奖学金一等奖3000元、二等奖10名，总额600万元。', '晴川奖学金', 'scholarship')
        self.assertEqual(select_evidence('晴川奖学金二等奖多少钱', [total]), [])

    def test_each_award_value_binds_its_nearest_subject(self):
        policy = chunk('国家奖学金每人8000元、国家励志奖学金每人5000元。', '奖学金', 'scholarship')
        self.assertTrue(select_evidence('国家励志奖学金多少钱', [policy]))
        wrong = chunk('国家奖学金每人8000元、国家励志奖学金10名。', '奖学金', 'scholarship')
        self.assertEqual(select_evidence('国家励志奖学金多少钱', [wrong]), [])

    def test_natural_attribute_connectors_and_grade_followup(self):
        self.assertTrue(callable(getattr(qu, 'plan_subqueries', None)))
        cases = [
            ('图书馆在哪里？咨询电话是多少？', ['location', 'contact']),
            ('图书馆在哪里以及咨询电话是多少', ['location', 'contact']),
            ('图书馆几点闭馆和一次能借多少本？', ['time', 'quota']),
            ('奖学金一等奖多少钱，二等奖呢？', ['amount', 'amount']),
            ('我想知道图书馆开放时间与借阅上限', ['time', 'quota']),
        ]
        for question, attributes in cases:
            plan = qu.plan_subqueries(question)
            self.assertEqual([p['slots']['attribute'] for p in plan], attributes, question)
            self.assertTrue(all(len(p['slots']['subject']) == 1 for p in plan), question)
        plan = qu.plan_subqueries(cases[3][0])
        self.assertEqual([p['slots']['conditions']['grade'] for p in plan], [['一等奖'], ['二等奖']])

    def test_natural_split_preserves_proper_names_and_time_ranges(self):
        self.assertTrue(callable(getattr(qu, 'plan_subqueries', None)))
        for question in ('机械与电气工程学院在哪里', '图书馆周一至周日几点开放',
                         '计算机科学与技术专业有哪些课程'):
            self.assertEqual(len(qu.plan_subqueries(question)), 1, question)
        self.assertEqual(len(qu.plan_subqueries('图书馆和实验室分别几点关门')), 2)
        with self.assertRaises(ValueError):
            qu.plan_subqueries('？'.join(['图书馆电话是多少'] * 7))

    def test_quantity_paraphrases_share_slots(self):
        for question in ('图书馆一次能借多少本书', '图书馆最多借多少册', '图书馆借几本', '图书馆借阅上限'):
            slots = qu.analyze_query(question).get('slots', {})
            self.assertEqual(slots.get('attribute'), 'quota')
            self.assertEqual(slots.get('subject'), ['图书馆'])

    def test_role_grade_event_conditions(self):
        slots = qu.analyze_query('老师在图书馆一次能借多少本书').get('slots', {})
        self.assertEqual(slots.get('conditions', {}).get('role'), '教职工')
        slots = qu.analyze_query('奖学金一等奖初评何时公示').get('slots', {})
        self.assertEqual(slots.get('conditions', {}).get('grade'), ['一等奖'])
        self.assertIn('初评', slots.get('conditions', {}).get('event', []))

    def test_plans_required_composites(self):
        cases = [
            ('图书馆和实验室分别几点关门', ['图书馆', '实验室'], ['time', 'time']),
            ('图书馆几点闭馆，一次最多能借多少册', ['图书馆', '图书馆'], ['time', 'quota']),
            ('图书馆在哪里，咨询电话是多少', ['图书馆', '图书馆'], ['location', 'contact']),
            ('奖学金一等奖和二等奖各多少钱', ['奖学金', '奖学金'], ['amount', 'amount']),
            ('国家奖学金和国家励志奖学金各多少钱', ['国家奖学金', '国家励志奖学金'], ['amount', 'amount']),
        ]
        self.assertTrue(callable(getattr(qu, 'plan_subqueries', None)))
        for question, subjects, attributes in cases:
            plan = qu.plan_subqueries(question)
            self.assertEqual(len(plan), 2, question)
            self.assertEqual([p['slots']['subject'][0] for p in plan], subjects)
            self.assertEqual([p['slots']['attribute'] for p in plan], attributes)
            self.assertTrue(all(p['question'] and p['label'] for p in plan))
        self.assertEqual([p['slots']['conditions']['grade'] for p in qu.plan_subqueries(cases[3][0])], [['一等奖'], ['二等奖']])

    def test_single_names_history_semicolon_and_limit(self):
        self.assertTrue(callable(getattr(qu, 'plan_subqueries', None)))
        for question in ('机械与电气工程学院有哪些专业', '计算机科学与技术专业在哪里', '图书馆几点关门'):
            self.assertEqual(len(qu.plan_subqueries(question)), 1)
        plan = qu.plan_subqueries('在哪里；电话是多少', [{'role': 'user', 'content': '图书馆几点关门'}])
        self.assertEqual(len(plan), 2)
        self.assertTrue(all(p['slots']['subject'] == ['图书馆'] for p in plan))
        with self.assertRaises(ValueError):
            qu.plan_subqueries('；'.join(['图书馆电话是多少'] * 7))

    def test_quota_synonyms_bind_role(self):
        chunks = [chunk('本科生限借20册。'), chunk('教职工限借30册。')]
        evidence = select_evidence('老师在图书馆一次能借多少本书', chunks)
        self.assertTrue(evidence)
        self.assertTrue(all('30册' in e['text'] for e in evidence))

    def test_grade_amount_cannot_use_unrelated_total_or_other_grade(self):
        chunks = [chunk('一等奖颁奖典礼举行，学校奖学金总额600万元。', '奖学金', 'news'),
                  chunk('晴川奖学金二等奖：奖励金额为2000元。', '奖学金', 'scholarship'),
                  chunk('晴川奖学金一等奖：奖励金额为3000元。', '奖学金', 'scholarship')]
        evidence = select_evidence('奖学金一等奖多少钱', chunks)
        self.assertTrue(evidence)
        self.assertTrue(all('3000元' in e['text'] for e in evidence))
        self.assertEqual(select_evidence('奖学金一等奖和二等奖各多少钱', chunks), [])

    def test_entity_amount_must_bind_same_fact(self):
        chunks = [chunk('国家奖学金颁奖，国家励志奖学金每人5000元。', '奖学金', 'scholarship')]
        self.assertEqual(select_evidence('国家奖学金多少钱', chunks), [])

    def test_grade_alias_in_real_policy_and_total_only_rejected(self):
        chunks = [chunk('晴川奖学金一等奖（甲等）：奖励金额为每人每学年3000元，全校10名。', '晴川奖学金', 'scholarship')]
        self.assertTrue(select_evidence('晴川奖学金一等奖多少钱', chunks))
        self.assertEqual(select_evidence('奖学金一等奖多少钱', [chunk('一等奖颁奖典礼举行，奖学金总额600万元。', '奖学金', 'news')]), [])

    def test_role_value_in_different_fact_cannot_satisfy_quota(self):
        chunks = [chunk('教职工可入馆，本科生每人限借20册。')]
        self.assertEqual(select_evidence('老师在图书馆一次能借多少本书', chunks), [])


if __name__ == '__main__':
    unittest.main()
