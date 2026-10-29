import unittest
from core.hybrid_retriever import HybridRetriever
from core.evidence import select_evidence

class TopicCoverageTests(unittest.TestCase):
    def chunks(self):
        return [dict(global_id=i, source='news_xxyw', section_id=section, title=title, text=text, url=url)
            for i,(section,title,text,url) in enumerate([
                ('old','2025小米杯','发布时间：2025-09-01。2025年小米杯获三等奖。','https://example.org/old'),
                ('old','2025小米杯','2025年小米杯比赛在武汉大学落幕。','https://example.org/old'),
                ('old','2025小米杯','小米杯培养创新能力。','https://example.org/old'),
                ('new','2026赛事','发布时间：2026-09-01。2026年小米杯获一等奖。','https://example.org/new')])]

    def test_short_topic_covers_articles_by_relevance(self):
        chunks=self.chunks()
        retriever=type('Memory',(),{'chunks':chunks})()
        hybrid=HybridRetriever(retriever,retriever)
        result=hybrid.fuse('小米杯',[(c,.9) for c in chunks[:3]],[(c,.9) for c in chunks[:3]],3)
        self.assertEqual(len({row[0]['url'] for row in result}),2)
        self.assertEqual(len({row[0]['url'] for row in result}),2)

    def test_topic_evidence_covers_more_than_one_article(self):
        chunks=self.chunks()
        result=select_evidence('小米杯',chunks)
        self.assertEqual(len({chunks[r['chunk_index']]['url'] for r in result}),2)

    def test_news_caption_and_header_not_answer(self):
        text = '## 29. 点赞！计算机系统能力大赛获一等奖\n- 现场配图：\n![计算机系统能力大赛获一等奖](/images/a.png)\n- **核心新闻正文**：\n2026年计算机系统能力大赛全国总决赛落幕。'
        result = select_evidence('计算机系统能力大赛', [dict(text=text, source='news_xxyw', title='29. 点赞！计算机系统能力大赛获一等奖')])
        self.assertEqual([r['text'] for r in result], ['2026年计算机系统能力大赛全国总决赛落幕。'])

    def test_read_three_articles_answer_from_newest(self):
        from tests.test_rag_pipeline import RagPipelineTests
        chunks = [dict(global_id=i, source='news_xxyw', section_id=str(i), title=f'小米杯报道{i}',
                       text=f'{year}年小米杯获{award}。', published_at=f'{year}-09-01', url=f'https://example.org/{i}')
                  for i,(year,award) in enumerate([(2025,'三等奖'),(2026,'一等奖'),(2024,'二等奖')])]
        engine=RagPipelineTests().engine()
        engine.tfidf_retriever.chunks=chunks
        engine.bge_retriever.chunks=chunks
        engine.hybrid_retriever=HybridRetriever(engine.tfidf_retriever,engine.bge_retriever)
        engine._resolve_chunk_article=lambda source,title,text: ('',text)
        result=engine.query('小米杯',allow_generation=False)
        self.assertEqual(len(result['citations']),3)
        self.assertIn('2026年小米杯获一等奖',result['answer'])
        self.assertNotIn('2025年小米杯获三等奖',result['answer'])
        self.assertEqual(sum(c['used_for_answer'] for c in result['citations']),1)

    def test_model_request_contains_three_articles_and_dates(self):
        import json
        from unittest.mock import patch, Mock
        from core.deepseek_client import generate_from_evidence
        citations=[dict(index=i+1,evidence_text=f'证据{i}',full_text=f'完整文章正文{i}',published_at=f'{2024+i}-09-01') for i in range(3)]
        with patch('core.deepseek_client.requests.post') as post:
            post.return_value=Mock(status_code=200)
            post.return_value.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'回答[3]'}}]}
            generate_from_evidence('小米杯',[],citations,'unit-test-key')
            messages=post.call_args.kwargs['json']['messages']
            entries=json.loads(messages[1]['content'])['selected_evidence']
            self.assertEqual(len(entries),3)
            self.assertEqual(entries[2]['article'],'完整文章正文2')
            self.assertEqual(entries[2]['published_at'],'2026-09-01')
            self.assertIn('先阅读全部',messages[0]['content'])
