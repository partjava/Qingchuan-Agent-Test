"""聚合独立子问题的答案和引用，不将一项的证据挪给另一项。"""
import re


def combine_answers(question, mode, analysis, plans, results):
    citations, evidence, sub_answers, blocks = [], [], [], []
    by_source, seen_evidence = {}, set()
    for sub_index, (plan, result) in enumerate(zip(plans, results)):
        remap = {}
        for citation in result.get('citations', []):
            # 同一章节的不同事实可以共用一个编号，证据必须合并而不是覆盖。
            key = (citation['source'], citation.get('url') or citation.get('section_id') or citation.get('title'))
            if key not in by_source:
                merged = dict(citation, index=len(citations) + 1)
                by_source[key] = merged
                citations.append(merged)
            else:
                merged = by_source[key]
                extra = citation.get('evidence_text', '')
                if extra and extra not in merged.get('evidence_text', ''):
                    merged['evidence_text'] = merged.get('evidence_text', '') + '\n' + extra
                full = citation.get('full_text', '')
                if full and full not in merged.get('full_text', ''):
                    merged['full_text'] = merged.get('full_text', '') + '\n' + full
            remap[citation['index']] = merged['index']
        answer = re.sub(r'\[(\d+)\]', lambda m: f"[{remap.get(int(m.group(1)), m.group(1))}]", result['answer'])
        body = re.sub(r'^🎯【核心解答】\s*', '', answer).strip()
        blocks.append(f"**{plan['label']}**\n{body}")
        for item in result.get('evidence', []):
            new_index = remap[item['citation_index']]
            key = (new_index, item['text'])
            if key not in seen_evidence:
                evidence.append(dict(item, citation_index=new_index, subquestion_index=sub_index))
                seen_evidence.add(key)
        sub_answers.append(dict(question=plan['question'], label=plan['label'], slots=plan['slots'],
            answer=answer, refused=result.get('refused', False), clarification=result.get('clarification', False),
            citation_indices=list(dict.fromkeys(remap.values()))))
    missing = [r.get('refused', False) or r.get('clarification', False) for r in results]
    all_missing = all(missing)
    partial = any(missing) and not all_missing
    ablation = {}
    for name in ('tfidf', 'bge', 'hybrid'):
        entries = [r.get('ablation', {}).get(name) for r in results if r.get('ablation')]
        entries = [entry for entry in entries if entry]
        if entries:
            ablation[name] = dict(entries[0], time_ms=round(sum(entry['time_ms'] for entry in entries), 1),
                mechanism='各子问题累计检索耗时。' + entries[0]['mechanism'],
                top_chunks=[chunk for entry in entries for chunk in entry['top_chunks'][:1]][:3])
    entities, images, related = [], [], []
    entity_keys = set()
    for result in results:
        for entity in result.get('entities', []):
            key = (entity.get('type'), entity['text'])
            if key not in entity_keys:
                entities.append(entity)
                entity_keys.add(key)
        images.extend(result.get('images', []))
        related.extend(result.get('related_questions', []))
    analysis = dict(analysis, subqueries=[dict(plan) for plan in plans])
    mode_label = {'hybrid': '混合检索与精排', 'bge': 'BGE 稠密语义', 'tfidf': 'TF-IDF 统计词频'}.get(mode, '本地检索')
    return dict(question=question, mode=mode, answer='🎯【核心解答】\n\n' + '\n\n'.join(blocks),
        query_analysis=analysis, sub_answers=sub_answers, partial=partial,
        refused=all_missing and any(r.get('refused') for r in results),
        clarification=all(r.get('clarification', False) for r in results),
        citations=citations, evidence=evidence,
        evidence_status='partial' if partial else 'insufficient' if all_missing else 'supported',
        llm_provider=f"{mode_label} · 复合问题分项事实抽取", security_flag=False, ablation=ablation or None,
        entities=entities, images=list(dict.fromkeys(images))[:4],
        related_questions=list(dict.fromkeys(related))[:3],
        target_landmark=next((r['target_landmark'] for r in results if r.get('target_landmark')), None),
        retrieved_chunks=[dict(item, subquestion_index=i) for i, r in enumerate(results) for item in r.get('retrieved_chunks', [])])
