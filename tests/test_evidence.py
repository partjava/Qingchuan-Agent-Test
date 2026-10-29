import unittest
from core.evidence import select_evidence, rerank_candidates
from core.direct_extractor import CampusDirectAnswerExtractor


def chunk(text, source='library', title='图书馆开放时间', gid=0):
    return dict(text=text, title=title, source=source, global_id=gid)


class EvidenceTests(unittest.TestCase):
    def test_hours_are_from_evidence_not_constants(self):
        evidence = [chunk('图书馆开放时间：周一至周日 07:30—22:00；工作日21:30停止借还业务，22:00闭馆清场。')]
        answer = CampusDirectAnswerExtractor().extract('图书馆几点闭馆？', evidence)
        self.assertIn('22:00', answer)
        self.assertNotIn('8:00', answer)
        self.assertIn('[1]', answer)

    def test_scholarship_deadline_uses_right_fact(self):
        answer = CampusDirectAnswerExtractor().extract('奖学金申请什么时候截止？', [chunk('奖学金材料在第 5 教学周周五前提交（以当年通知为准）。', 'scholarship', '评审时间')])
        self.assertIn('第 5 教学周', answer)
        self.assertNotIn('第 2 周', answer)

    def test_unknown_fact_and_wrong_subject_are_not_answered(self):
        self.assertEqual(select_evidence('图书馆馆长手机号是什么？', [chunk('图书馆业务电话：027-12345678。')]), [])
        self.assertEqual(select_evidence('图书馆2027年翻新预算多少钱？', [chunk('逾期每册每天0.1元。')]), [])
        self.assertEqual(select_evidence('国家奖学金多少钱？', [chunk('晴川奖学金一等奖3000元。', 'scholarship')]), [])

    def test_no_chunks_no_fabricated_answer(self):
        self.assertIsNone(CampusDirectAnswerExtractor().extract('图书馆几点闭馆？', []))

    def test_nonexistent_facility_is_not_replaced_by_generic_booking(self):
        result = select_evidence('图书馆地下三层VR游戏中心怎么预约？', [chunk('考研座位预约申请需要提交学生证。')])
        self.assertEqual(result, [])

    def test_requested_relation_and_currency_unit_are_required(self):
        self.assertEqual(select_evidence('图书馆学生借多久？', [chunk('图书馆、学生宿舍区实行24小时值班。')]), [])
        self.assertEqual(select_evidence('图书馆学生借多久？', [chunk('图书馆集借、藏、阅于一体，周开放时间70小时。')]), [])
        self.assertEqual(select_evidence('计算机学院学费多少钱？', [chunk('计算机学院2026年组织多元文化交流。', 'news_xxyw')]), [])
        result = select_evidence('晴川奖学金什么时候发放？', [chunk('奖学金材料第5教学周周五提交。', 'scholarship')])
        self.assertEqual(result, [])

    def test_parent_context_completes_truncated_sentence(self):
        sample = chunk('规定》第2条：普通图书借期为30')
        sample['context_text'] = '借阅规定\n依据《读者借阅规定》第2条：普通图书借期为30天（教职工60天）。'
        result = select_evidence('普通图书借期多久？', [sample])
        self.assertIn('30天', result[0]['text'])

    def test_borrow_quota_is_not_donation_or_wrong_audience(self):
        donation = chunk('图书馆收到捐赠图书共计2018册。', 'news_xxyw')
        self.assertEqual(select_evidence('图书馆老师可以借几本？', [donation]), [])
        self.assertEqual(select_evidence('图书馆研究生能借多少册？', [chunk('本科学生每人限借10册图书。')]), [])

    def test_majors_are_not_news_about_a_professional_event(self):
        news = chunk('计算机学院老师申报的AI+专业实践入选国家级高等教育案例。', 'school_overview')
        self.assertEqual(select_evidence('计算机学院有哪些专业？', [news]), [])
        monitoring = chunk('计算机学院参与湖北省本科专业监测评估。', 'school_overview')
        self.assertEqual(select_evidence('计算机学院有哪些专业？', [monitoring]), [])

    def test_disbursement_and_booking_duration_are_distinct_events(self):
        policy = chunk('奖学金第5周提交申请。公示期满无异议后，将奖学金一次性划拨发放至银行卡。', 'scholarship')
        evidence = select_evidence('晴川奖学金什么时候发到银行卡？', [dict(policy, context_text='晴川奖学金\n'+policy['text'])])
        self.assertIn('公示期满', evidence[0]['text'])
        booking = chunk('GPU实验机房单次默认预约时长为3小时。', 'laboratory')
        evidence = select_evidence('GPU实验机房单次默认能预约多长时间？', [booking])
        self.assertIn('3小时', evidence[0]['text'])

    def test_policy_precedes_news_for_rule_question(self):
        candidates = [(chunk('图书馆举办开馆仪式，师生积极参加。', 'news_xxyw', gid=0), .9, {}),
                      (chunk('图书馆开放时间：07:30—22:00，22:00闭馆。', gid=1), .7, {})]
        result = rerank_candidates('图书馆几点闭馆？', candidates)
        self.assertEqual(result[0][0]['global_id'], 1)

    def test_borrowing_duration_does_not_return_compensation(self):
        result = select_evidence('普通图书可以借多少天？', [chunk('普通图书借期为30天。遗失图书按原价2到5倍赔偿。')])
        self.assertTrue(result)
        self.assertIn('30天', result[0]['text'])


if __name__ == '__main__':
    unittest.main()
