import unittest
from core.query_understanding import analyze_query


class QueryUnderstandingTests(unittest.TestCase):
    def test_scholarship_deadline_is_not_course_selection(self):
        result = analyze_query('奖学金申请什么时候截止？')
        self.assertEqual(result['topic'], 'scholarship')
        self.assertEqual(result['intent'], 'time')

    def test_alias_and_explicit_typo(self):
        self.assertEqual(analyze_query('计院有哪些专业')['rewritten_query'], '计算机学院有哪些专业')
        result = analyze_query('图书管几点关门')
        self.assertEqual(result['rewritten_query'], '图书馆几点关门')
        self.assertTrue(result['normalizations'])

    def test_followup_uses_user_topic(self):
        result = analyze_query('那周末呢？', [{'role': 'user', 'content': '图书馆几点关门？'}, {'role': 'assistant', 'content': '教务处通知'}])
        self.assertIn('图书馆', result['rewritten_query'])
        self.assertEqual(result['intent'], 'time')

    def test_new_topic_wins_and_unresolved_needs_clarification(self):
        result = analyze_query('奖学金多少钱？', [{'role': 'user', 'content': '图书馆在哪里'}])
        self.assertEqual(result['topic'], 'scholarship')
        self.assertNotIn('图书馆', result['rewritten_query'])
        self.assertTrue(analyze_query('它几点关门？')['clarification'])

    def test_ambiguous_multiple_subjects(self):
        history = [{'role': 'user', 'content': '图书馆和实验室分别在哪里？'}]
        self.assertTrue(analyze_query('它几点关门？', history)['clarification'])

    def test_continued_followups_keep_last_topic(self):
        history = [{'role': 'user', 'content': '图书馆几点关门'}, {'role': 'user', 'content': '那周末呢'}]
        self.assertIn('图书馆', analyze_query('能借几本？', history)['rewritten_query'])

    def test_short_level_followup_keeps_question_type(self):
        history = [{'role': 'user', 'content': '晴川奖学金一等奖多少钱？'}]
        result = analyze_query('那二等奖呢？', history)
        self.assertIn('晴川奖学金', result['rewritten_query'])
        self.assertEqual(analyze_query(result['rewritten_query'])['intent'], 'amount')

    def test_other_building_does_not_inherit_library(self):
        result = analyze_query('一食堂几点开放？', [{'role': 'user', 'content': '图书馆在哪里？'}])
        self.assertNotIn('图书馆', result['rewritten_query'])

    def test_new_topic_without_concrete_subject_is_context_barrier(self):
        history = [{'role': 'user', 'content': '图书馆几点开放？'}, {'role': 'user', 'content': '学校校长是谁？'}]
        result = analyze_query('它什么时候关闭？', history)
        self.assertTrue(result['clarification'])
        self.assertNotIn('图书馆', result['rewritten_query'])

    def test_teacher_borrowing_alias(self):
        self.assertIn('教职工', analyze_query('图书馆老师可以借几本？')['rewritten_query'])

    def test_unknown_standalone_topic_also_blocks_old_referent(self):
        history = [{'role': 'user', 'content': '图书馆几点开放？'}, {'role': 'user', 'content': '苹果公司的股票怎么购买？'}]
        self.assertTrue(analyze_query('它什么时候关闭？', history)['clarification'])

    def test_navigation_followup_duration_and_distance_rewriting(self):
        history = [{'role': 'user', 'content': '校门口到食堂'}]
        for q in ('要花多长时间？', '大概要多久？', '多远？', '步行需要几分钟？', '走过去要多久？'):
            result = analyze_query(q, history)
            self.assertIn('正大门', result['rewritten_query'])
            self.assertIn('一食堂', result['rewritten_query'])
            self.assertFalse(result['clarification'])
            self.assertEqual(result['topic'], 'campus_landmarks')

    def test_navigation_followup_change_destination(self):
        history = [{'role': 'user', 'content': '校门口到食堂'}]
        result = analyze_query('那去图书馆呢？', history)
        self.assertIn('正大门', result['rewritten_query'])
        self.assertIn('图书馆', result['rewritten_query'])
        self.assertFalse(result['clarification'])

    def test_navigation_from_assistant_reply_heritage(self):
        history = [{'role': 'assistant', 'content': '🚩 晴川校园步行导航：从【正大门】前往【一食堂】\n\n1. 从南正大门出发...'}]
        result = analyze_query('要花多长时间？', history)
        self.assertIn('正大门', result['rewritten_query'])
        self.assertIn('一食堂', result['rewritten_query'])
        self.assertFalse(result['clarification'])


if __name__ == '__main__':
    unittest.main()
