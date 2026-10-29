"""Reference-based lexical answer checks; these are not semantic correctness scores.

No model dependencies are imported until run_answer_benchmark is called.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def normalize(text):
    """Ignore whitespace and Markdown decoration, preserving factual numbers."""
    text = unicodedata.normalize('NFKC', str(text)).lower()
    return re.sub(r'[\s*`_#>]+', '', text)


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def evaluate_answers(engine, cases, mode='hybrid'):
    """Evaluate a supplied engine without initializing models or writing files.

    Success requires all explicit facts, their presence in linked evidence,
    expected source coverage, valid inline citations, and the expected decision.
    Citation claim checks cover explicit reference facts and numeric literals;
    arbitrary paraphrased claims require human/semantic review.
    """
    rows = []
    for case in cases:
        start = time.perf_counter()
        result = engine.query(case['question'], mode=mode, top_k=3,
                              history=case.get('history', []), allow_generation=False)
        answer = str(result.get('answer', ''))
        facts = case.get('expected_facts', [])
        citations = {str(c['index']): c for c in result.get('citations', []) if 'index' in c}
        markers = re.findall(r'\[(\d+)\]', answer)
        sources = {Path(str(c.get('source', '')).replace('\\', '/')).stem for index, c in citations.items() if index in markers}
        expected_sources = {Path(str(s).replace('\\', '/')).stem for s in case.get('expected_sources', [])}
        alternatives = {Path(str(s).replace('\\', '/')).stem
                        for s in case.get('expected_source_alternatives', [])}
        source_coverage = _ratio(len(sources & expected_sources) + int(bool(sources & alternatives)),
                                 len(expected_sources) + int(bool(alternatives)))
        linked = []
        for evidence in result.get('evidence', []):
            index = str(evidence.get('citation_index', ''))
            citation = citations.get(index)
            if citation and index in markers:
                text = str(evidence.get('text', ''))
                # Check the evidence was actually supplied by the cited entry.
                if normalize(text) and normalize(text) in normalize(citation.get('evidence_text', '')):
                    linked.append(text)
        evidence_text = normalize(' '.join(linked))
        fact_coverage = _ratio(sum(normalize(f) in normalize(answer) for f in facts), len(facts))
        support = _ratio(sum(normalize(f) in evidence_text for f in facts), len(facts))
        alignment = float(bool(markers) and all(m in citations for m in markers) and
                          set(markers) == {index for index, citation in citations.items() if citation.get('used_for_answer') is not False} and bool(linked))
        # Each numeric claim must occur in the evidence of that claim's citation.
        claim_checks = []
        # A trailing citation applies to its preceding span, which may contain
        # several sentences in an extracted source bullet.
        claims = [span for line in answer.splitlines()
                  for span in re.findall(r'.*?\[\d+\]|.+$', line)]
        for claim in claims:
            claim_markers = re.findall(r'\[(\d+)\]', claim)
            plain_claim = re.sub(r'\[\d+\]', '', claim)
            numbers = re.findall(r'\d+(?:[.:~-]\d+)*', plain_claim)
            if numbers:
                cited_text = normalize(' '.join(str(citations.get(m, {}).get('evidence_text', ''))
                                                for m in claim_markers))
                claim_checks.append(bool(claim_markers) and all(n in cited_text for n in numbers))
        claim_support = float(all(claim_checks))
        keywords = case.get('evidence_keywords', [])
        keyword_support = all(normalize(k) in evidence_text for k in keywords)
        refused = bool(result.get('refused', False))
        clarification = bool(result.get('clarification', False))
        partial = bool(result.get('partial', False))
        expected_subanswers = case.get('expected_subanswers', [])
        subanswers = result.get('sub_answers', [])
        subanswer_checks = []
        for expected in expected_subanswers:
            matching = [item for item in subanswers if expected['label_contains'] in item.get('label', item.get('question', ''))]
            subanswer_checks.append(any(bool(item.get('refused')) == expected.get('expected_refusal', False)
                and all(normalize(fact) in normalize(item.get('answer', '')) for fact in expected.get('expected_facts', []))
                for item in matching))
        decision = (refused == case['expected_refusal'] and clarification == case.get('expected_clarification', False)
                    and partial == case.get('expected_partial', False) and all(subanswer_checks))
        if case['expected_refusal'] or case.get('expected_clarification', False):
            passed = decision
        else:
            passed = (decision and bool(facts) and bool(expected_sources or alternatives) and fact_coverage == 1
                      and support == 1 and source_coverage == 1 and alignment == 1
                      and claim_support == 1 and keyword_support)
        rows.append(dict(id=case['id'], question=case['question'], history=case.get('history', []),
                         answer=answer, citations=result.get('citations', []), evidence=result.get('evidence', []),
                         refused=refused, clarification=clarification, expected_refusal=case['expected_refusal'],
                         partial=partial, expected_partial=case.get('expected_partial', False),
                         sub_answers=subanswers, subanswer_coverage=_ratio(sum(subanswer_checks), len(subanswer_checks)) if subanswer_checks else None,
                         expected_clarification=case.get('expected_clarification', False),
                         expected_facts=facts, expected_sources=list(expected_sources),
                         expected_source_alternatives=sorted(alternatives),
                         lexical_fact_coverage=fact_coverage, evidence_fact_support=support,
                         source_coverage=source_coverage, citation_alignment=alignment,
                         numeric_claim_support=claim_support, passed=bool(passed),
                         latency_ms=(time.perf_counter()-start)*1000))
    answer_rows = [r for r in rows if not r['expected_refusal'] and not r['expected_clarification']]
    unknown_rows = [r for r in rows if r['expected_refusal']]
    clarification_rows = [r for r in rows if r['expected_clarification']]
    return dict(mode=mode, total_cases=len(rows), answerable_count=len(answer_rows),
                unknown_count=len(unknown_rows), clarification_count=len(clarification_rows),
                passed_count=sum(r['passed'] for r in rows),
                expected_answer_accuracy=_ratio(sum(r['passed'] for r in answer_rows), len(answer_rows)),
                unknown_refusal_accuracy=_ratio(sum(r['passed'] for r in unknown_rows), len(unknown_rows)),
                clarification_accuracy=_ratio(sum(r['passed'] for r in clarification_rows), len(clarification_rows)),
                metric_definitions={
                    'expected_answer_accuracy': 'All lexical reference facts and linked evidence/source/citation checks pass. Source coverage only checks document identifiers; citation checks validate linkage and numeric literals, not full claim entailment or semantic correctness.',
                    'unknown_refusal_accuracy': 'Expected unknown cases with correct refusal and clarification decisions / unknown count.',
                    'numeric_claim_support': 'All numeric literals occur in the evidence of their inline citation; not full entailment.',
                    'source_coverage': 'All expected_sources are required, plus at least one expected_source_alternatives when supplied. Identifiers are normalized to filename stems; this checks identifier coverage, not full source correctness.',
                    'zero_denominator': 'Reported as 0.0; counts distinguish absent categories.'}, cases=rows)


def run_answer_benchmark(modes=('tfidf', 'bge', 'hybrid'), dataset_path=None, output_path=None):
    sys.path.insert(0, str(ROOT))
    from core.document_loader import load_and_chunk_documents
    from core.tfidf_retriever import TfidfRetriever
    from core.bge_retriever import BgeSemanticRetriever
    from core.hybrid_retriever import HybridRetriever
    from core.rag_engine import QingchuanRagEngine
    modes = list(modes)
    if any(mode not in {'tfidf', 'bge', 'hybrid'} for mode in modes):
        raise ValueError('Supported modes: tfidf, bge, hybrid')
    cases = json.loads(Path(dataset_path or HERE / 'answer_dataset.json').read_text(encoding='utf-8'))
    chunks = load_and_chunk_documents(ROOT / 'data' / 'docs')
    tfidf = TfidfRetriever(chunks)
    bge = BgeSemanticRetriever(chunks) if any(m != 'tfidf' for m in modes) else None
    hybrid = HybridRetriever(tfidf, bge) if 'hybrid' in modes else None
    engine = QingchuanRagEngine(tfidf, bge, hybrid)
    reports = {mode: evaluate_answers(engine, cases, mode) for mode in modes}
    Path(output_path or HERE / 'answer_eval_results.json').write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes', nargs='+', default=['tfidf', 'bge', 'hybrid'])
    parser.add_argument('--dataset')
    parser.add_argument('--output')
    args = parser.parse_args()
    run_answer_benchmark(args.modes, args.dataset, args.output)
