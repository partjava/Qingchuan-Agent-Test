"""基于召回原文的事实抽取；没有证据时不返回固定校园事实。"""
from core.evidence import select_evidence


class CampusDirectAnswerExtractor:
    def extract(self, query, chunks=None):
        evidence = select_evidence(query, chunks or [])
        if not evidence:
            return None
        return '\n'.join(f"• {item['text']} [{item['chunk_index'] + 1}]" for item in evidence)
