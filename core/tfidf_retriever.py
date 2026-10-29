# -*- coding: utf-8 -*-
"""
传统 NLP 检索基线：TF-IDF + 余弦相似度
作为稀疏特征检索与加权融合的关键基线
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TfidfRetriever:
    def __init__(self, chunks: List[Dict[str, Any]]):
        self.chunks = chunks
        self.corpus = [c["text"] for c in chunks]
        
        # 中文使用字符级 n-gram (1, 2) 特征提取，兼顾单字与双字词统计，无需额外外部词典
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.corpus)

    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """计算查询与知识块的 TF-IDF 余弦相似度并排序返回 Top-K"""
        if not query.strip():
            return []
        
        query_vec = self.vectorizer.transform([query])
        sim_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # 取 Top-K 索引
        top_k = min(max(1, top_k), len(sim_scores))
        top_indices = np.argsort(-sim_scores)[:top_k]
        
        results = []
        for idx in top_indices:
            score = float(sim_scores[idx])
            results.append((self.chunks[idx], score))
            
        return results


if __name__ == "__main__":
    from document_loader import load_and_chunk_documents
    chunks = load_and_chunk_documents("last/qinchuan_rag/data/docs")
    retriever = TfidfRetriever(chunks)
    
    test_q = "图书馆几点关闭？"
    res = retriever.retrieve(test_q, top_k=3)
    print(f"=== TF-IDF 检索测试: '{test_q}' ===")
    for rank, (chunk, score) in enumerate(res, 1):
        print(f"[{rank}] 来源: {chunk['source']} | 分数: {score:.4f}")
        print(f"    内容: {chunk['text'][:70]}...")
