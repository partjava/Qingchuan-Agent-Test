import unittest
from unittest.mock import Mock, patch
from tests import test_rag_pipeline
from core.evidence import select_evidence
from core.deepseek_client import generate_from_evidence

QUESTION = '武汉晴川学院是一所什么性质的学校？'
FACT = '武汉晴川学院是经教育部批准设置的全日制普通本科高校。'
ARTICLE = '2018年招生问答\n1、' + QUESTION + '\n' + FACT

class ArticleReadingTests(unittest.TestCase):
    def test_question_is_not_answer_evidence(self):
        result = select_evidence(QUESTION, [dict(text=QUESTION, source='news_xxyw', title='招生问答')])
        self.assertEqual(result, [])

    def test_expand_article_before_selecting_answer(self):
        engine = test_rag_pipeline.RagPipelineTests().engine(QUESTION)
        engine._resolve_chunk_article = lambda *args: ('https://example.org', ARTICLE)
        result = engine.query(QUESTION, allow_generation=False)
        self.assertIn(FACT, result['answer'])
        self.assertNotIn('• ' + QUESTION, result['answer'])

    @patch('core.deepseek_client.requests.post')
    def test_model_reads_article_body_not_just_selected_sentence(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'choices': [{'finish_reason':'stop', 'message':{'content':FACT+'[1]'}}]}
        generate_from_evidence(QUESTION, [], [{'index':1, 'evidence_text':QUESTION, 'full_text':ARTICLE}], 'test-key')
        self.assertIn(FACT, post.call_args.kwargs['json']['messages'][1]['content'])

    def test_document_title_and_catalog_description_are_not_answers(self):
        result = select_evidence('武汉晴川学院是什么学校', [dict(text='# 武汉晴川学院学校概况\n> 本知识库收录武汉晴川学院官方权威信息。\n' + FACT, source='school_overview', title='武汉晴川学院学校概况')])
        self.assertEqual([r['text'] for r in result], [FACT])

    def test_school_nature_does_not_select_logo_or_special_admissions(self):
        text = '武汉晴川学院20周年LOGO以数字20为核心。\n专升本教育：武汉晴川学院具有普通专升本招生资格。\n' + FACT
        result = select_evidence('武汉晴川学院是什么学校', [dict(text=text, source='school_overview', title='学校概况')])
        self.assertEqual([r['text'] for r in result], [FACT])

    def test_article_expansion_stops_at_next_peer_heading(self):
        from core.rag_engine import QingchuanRagEngine
        engine = test_rag_pipeline.RagPipelineTests().engine()
        engine._docs_cache={'sample':'## 第一篇招生文章\nhttps://example.org/first\n第一篇正文。\n## 第二篇招生文章\n' + '第二篇正文。'*1000}
        _,article=QingchuanRagEngine._resolve_chunk_article(engine,'sample','第一篇招生文章','第一篇正文。')
        self.assertIn('第一篇正文',article)
        self.assertNotIn('第二篇正文',article)
