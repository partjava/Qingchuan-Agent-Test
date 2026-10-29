# -*- coding: utf-8 -*-
"""
混合检索模块 (Hybrid Retriever)
融合传统 TF-IDF 倒排关键词匹配与 BGE 稠密语义检索，采用倒数排名融合 (RRF, Reciprocal Rank Fusion)
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import re
from core.evidence import rerank_candidates, SOURCE_PREFERENCES, is_topic_lookup
from core.query_understanding import analyze_query


class HybridRetriever:
    def __init__(self, tfidf_retriever, bge_retriever, rrf_k: int = 60, sparse_weight: float = .35):
        self.tfidf_retriever = tfidf_retriever
        self.bge_retriever = bge_retriever
        self.rrf_k = rrf_k
        self.chunks = tfidf_retriever.chunks
        if rrf_k <= 0 or not 0 <= sparse_weight <= 1:
            raise ValueError('rrf_k must be positive; sparse_weight must be between 0 and 1')
        self.sparse_weight = sparse_weight
        self.source_chunks = defaultdict(list)
        for chunk in self.chunks:
            self.source_chunks[chunk['source']].append(chunk)

    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float, Dict[str, Any]]]:
        """
        返回: list of (chunk, rrf_score, debug_details)
        """
        if not query.strip():
            return []

        # 1. 分别获取候选
        if top_k < 1:
            raise ValueError('top_k must be positive')
        pool_size = max(30, top_k * 8)
        tfidf_res = self.tfidf_retriever.retrieve(query, top_k=pool_size)
        bge_res = self.bge_retriever.retrieve(query, top_k=pool_size)
        return self.fuse(query, tfidf_res, bge_res, top_k)

    def fuse(self, query, tfidf_res, bge_res, top_k=5):
        """复用已有召回结果，避免在线消融重复编码同一问题。"""
        chunk_by_id = {c['global_id']: c for c, _ in tfidf_res + bge_res}

        # 2. 计算 RRF 得分
        scores = defaultdict(float)
        meta_scores = defaultdict(lambda: {"tfidf_score": 0.0, "bge_score": 0.0, "tfidf_rank": 999, "bge_rank": 999})

        for rank, (chunk, score) in enumerate(tfidf_res, 1):
            gid = chunk["global_id"]
            scores[gid] += self.sparse_weight / (self.rrf_k + rank)
            meta_scores[gid]["tfidf_score"] = score
            meta_scores[gid]["tfidf_rank"] = rank

        for rank, (chunk, score) in enumerate(bge_res, 1):
            gid = chunk["global_id"]
            scores[gid] += (1 - self.sparse_weight) / (self.rrf_k + rank)
            meta_scores[gid]["bge_score"] = score
            meta_scores[gid]["bge_rank"] = rank

        # 3. 按最终分数降序
        sorted_gids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for gid in sorted_gids:
            chunk = chunk_by_id[gid]
            final_score = scores[gid]
            details = meta_scores[gid]
            results.append((chunk, final_score, details))

        # 规章类事实增加相应专题库候选，防止大量新闻占满两路召回。
        analysis = analyze_query(query)
        preferred = list(SOURCE_PREFERENCES.get(analysis['topic'], ()))
        if analysis['intent'] == 'contact':
            preferred.insert(0, 'office_contacts')
        if analysis['intent'] == 'website':
            preferred.insert(0, 'campus_organizations')
        if analysis['intent'] == 'location':
            preferred.insert(0, 'campus_landmarks')
        extras = [(chunk, 0.0, {'candidate_origin': 'topic_policy'})
                  for source in preferred for chunk in self.source_chunks[source]
                  if chunk['global_id'] not in chunk_by_id]
        if extras:
            results.extend(rerank_candidates(query, extras, 12))
        if is_topic_lookup(query):
            # Literal topic recall prevents short aliases losing a related article
            # before reranking. Group by article, not by collection or text block.
            candidates = {row[0]['global_id']: row for row in results}
            for chunk in self.chunks:
                if query in chunk.get('text', '') or query in chunk.get('title', ''):
                    candidates.setdefault(chunk['global_id'], (chunk, 0.0, {'candidate_origin': 'literal_topic'}))
            ranked = rerank_candidates(query, list(candidates.values()))
            exact = [row for row in ranked if query in row[0].get('text', '') or query in row[0].get('title', '')]
            if exact:
                unique, seen_articles = [], set()
                for row in exact:
                    chunk = row[0]
                    key = chunk.get('url') or (chunk.get('source'), chunk.get('section_id', chunk.get('title')))
                    if key not in seen_articles:
                        seen_articles.add(key)
                        unique.append(row)
                return unique[:top_k]
        return rerank_candidates(query, results, top_k)
