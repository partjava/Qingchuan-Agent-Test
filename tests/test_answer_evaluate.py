import unittest
import json
from pathlib import Path
from eval.answer_evaluate import evaluate_answers


class FakeEngine:
    def __init__(self, result):
        self.result = result

    def query(self, question, **kwargs):
        return self.result


class AnswerEvaluationTests(unittest.TestCase):
    def test_composite_must_cover_each_expected_subanswer_and_partial_state(self):
        case = dict(self.case(), expected_partial=True,
                    expected_subanswers=[{'label_contains': '闭馆', 'expected_facts': ['22:00'], 'expected_refusal': False},
                                         {'label_contains': '馆长', 'expected_facts': [], 'expected_refusal': True}])
        result = self.result()
        result['partial'] = False
        result['sub_answers'] = [{'label': '图书馆闭馆', 'answer': '22:00 [1]', 'refused': False}]
        self.assertFalse(evaluate_answers(FakeEngine(result), [case])['cases'][0]['passed'])
        result['partial'] = True
        result['sub_answers'].append({'label': '馆长手机号', 'answer': '没有依据', 'refused': True})
        self.assertTrue(evaluate_answers(FakeEngine(result), [case])['cases'][0]['passed'])
    def test_dataset_schema_and_local_reference_facts(self):
        root = Path(__file__).resolve().parents[1]
        cases = json.loads((root / 'eval' / 'answer_dataset.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(cases), 40)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        from eval.answer_evaluate import normalize
        for case in cases:
            self.assertIsInstance(case['expected_refusal'], bool)
            self.assertIsInstance(case['history'], list)
            if case['expected_refusal'] or case.get('expected_clarification'):
                continue
            sources = case['expected_sources'] + case.get('expected_source_alternatives', [])
            self.assertTrue(sources, case['id'])
            self.assertTrue(case['expected_facts'], case['id'])
            corpus = normalize(' '.join((root / 'data' / 'docs' / (Path(s).stem + '.md')).read_text(encoding='utf-8') for s in sources))
            for fact in case['expected_facts']:
                self.assertIn(normalize(fact), corpus, case['id'])

    def case(self):
        return dict(id='hours', question='几点关门', history=[], expected_refusal=False,
                    expected_sources=['library.md'], expected_facts=['22:00'])

    def result(self):
        return dict(answer='闭馆 **22:00**。[1]', refused=False,
                    citations=[dict(index=1, source='library.md', evidence_text='闭馆22:00')],
                    evidence=[dict(citation_index=1, text='闭馆22:00')])

    def score(self, result, case=None):
        return evaluate_answers(FakeEngine(result), [case or self.case()], 'hybrid')

    def test_unused_reading_reference_does_not_break_answer_citations(self):
        result=self.result()
        result['citations'].append(dict(index=2,source='news_xxyw',evidence_text='阅读参考',used_for_answer=False))
        self.assertEqual(self.score(result)['expected_answer_accuracy'],1)
        result['citations'][0]['source']='wrong_source'
        result['citations'][1]['source']='library'
        self.assertEqual(self.score(result)['expected_answer_accuracy'],0)

    def test_supported_reference(self):
        self.assertEqual(self.score(self.result())['expected_answer_accuracy'], 1)

    def test_missing_reference_is_not_vacuously_correct(self):
        case = self.case(); case['expected_facts'] = []
        self.assertEqual(self.score(self.result(), case)['expected_answer_accuracy'], 0)

    def test_wrong_source(self):
        result = self.result(); result['citations'][0]['source'] = 'course_selection.md'
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 0)

    def test_source_stem_and_filename_are_equivalent(self):
        result = self.result(); result['citations'][0]['source'] = 'library'
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 1)

    def test_acceptable_alternative_source(self):
        case = self.case(); case['expected_sources'] = []
        case['expected_source_alternatives'] = ['library', 'office_contacts.md']
        result = self.result(); result['citations'][0]['source'] = 'office_contacts'
        self.assertEqual(self.score(result, case)['expected_answer_accuracy'], 1)

    def test_unlisted_alternative_source_fails(self):
        case = self.case(); case['expected_sources'] = []
        case['expected_source_alternatives'] = ['library', 'office_contacts']
        result = self.result(); result['citations'][0]['source'] = 'course_selection'
        self.assertEqual(self.score(result, case)['expected_answer_accuracy'], 0)

    def test_alternatives_do_not_replace_required_sources(self):
        case = self.case(); case['expected_source_alternatives'] = ['office_contacts']
        self.assertEqual(self.score(self.result(), case)['expected_answer_accuracy'], 0)

    def test_unsupported_answer(self):
        result = self.result(); result['evidence'][0]['text'] = '图书馆'; result['citations'][0]['evidence_text'] = '图书馆'
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 0)

    def test_refusal_false_positive(self):
        result = self.result(); result['refused'] = True
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 0)

    def test_missing_and_invalid_citation(self):
        result = self.result(); result['answer'] = '22:00 [9]'
        self.assertEqual(self.score(result)['cases'][0]['citation_alignment'], 0)

    def test_empty_dataset(self):
        result = evaluate_answers(FakeEngine({}), [], 'tfidf')
        self.assertEqual(result['total_cases'], 0)
        self.assertEqual(result['unknown_refusal_accuracy'], 0)

    def test_extra_numeric_claim_is_not_supported(self):
        result = self.result(); result['answer'] += '借书可以借99天。[1]'
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 0)

    def test_citation_at_end_of_multi_sentence_bullet(self):
        result = self.result()
        result['answer'] = '• 22:00闭馆。周末07:30开放。[1]'
        result['citations'][0]['evidence_text'] = '22:00闭馆。周末07:30开放。'
        result['evidence'][0]['text'] = result['citations'][0]['evidence_text']
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 1)

    def test_unknown_refusal_separate_denominator(self):
        case = self.case(); case['expected_refusal'] = True
        result = self.result(); result['refused'] = True
        report = self.score(result, case)
        self.assertEqual(report['unknown_refusal_accuracy'], 1)
        self.assertEqual(report['answerable_count'], 0)

    def test_evidence_cannot_point_to_unrelated_citation(self):
        result = self.result(); result['citations'][0]['evidence_text'] = '不同的内容'
        self.assertEqual(self.score(result)['expected_answer_accuracy'], 0)


if __name__ == '__main__':
    unittest.main()
