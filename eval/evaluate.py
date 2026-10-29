# -*- coding: utf-8 -*-
"""
武汉晴川学院 RAG 系统性能评测脚本
对比 TF-IDF 基线、BGE 语义检索与 Hybrid 混合检索的 Hit@1, Hit@3, Hit@5, MRR 与延迟
实现 TF-IDF vs BGE vs 加权融合 (Hybrid) 的多维检索对比与评测
"""

from __future__ import annotations
import os
import sys
import time
import csv
import json
import math
from pathlib import Path

# 添加项目根目录到 Python 路径
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.document_loader import load_and_chunk_documents
from core.tfidf_retriever import TfidfRetriever
from core.bge_retriever import BgeSemanticRetriever
from core.hybrid_retriever import HybridRetriever


def load_eval_data(csv_path: str | Path):
    items = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append({
                "question": row["question"].strip(),
                "target_doc": row["target_doc_id"].strip(),
                "reference": row["reference_answer"].strip()
            })
    return items


def evaluate_retriever(retriever, test_cases, name: str, is_hybrid: bool = False):
    total = len(test_cases)
    hit_1 = 0
    hit_3 = 0
    hit_5 = 0
    mrr_sum = 0.0
    ndcg_3_sum = 0.0
    ndcg_5_sum = 0.0
    latencies = []
    bad_cases = []
    good_cases = []

    for item in test_cases:
        q = item["question"]
        target = item["target_doc"]

        start_t = time.perf_counter()
        if is_hybrid:
            raw_res = retriever.retrieve(q, top_k=5)
            chunks = [c for c, _, _ in raw_res]
        else:
            raw_res = retriever.retrieve(q, top_k=5)
            chunks = [c for c, _ in raw_res]
        elapsed = (time.perf_counter() - start_t) * 1000 # ms
        latencies.append(elapsed)

        retrieved_sources = [c["source"] for c in chunks]

        # 检查命中位置
        rank = -1
        for idx, src in enumerate(retrieved_sources, 1):
            if src == target:
                rank = idx
                break

        if rank == 1:
            hit_1 += 1
            hit_3 += 1
            hit_5 += 1
            mrr_sum += 1.0
            ndcg_3_sum += 1.0
            ndcg_5_sum += 1.0
            if len(good_cases) < 2:
                good_cases.append({"question": q, "target": target, "rank": 1})
        elif 1 < rank <= 3:
            hit_3 += 1
            hit_5 += 1
            mrr_sum += 1.0 / rank
            ndcg_3_sum += 1.0 / math.log2(rank + 1)
            ndcg_5_sum += 1.0 / math.log2(rank + 1)
        elif 3 < rank <= 5:
            hit_5 += 1
            mrr_sum += 1.0 / rank
            ndcg_5_sum += 1.0 / math.log2(rank + 1)
        else:
            bad_cases.append({"question": q, "target": target, "top3_retrieved": retrieved_sources[:3]})

    return {
        "model_name": name,
        "total_queries": total,
        "hit_at_1": round(hit_1 / total * 100, 2),
        "hit_at_3": round(hit_3 / total * 100, 2),
        "hit_at_5": round(hit_5 / total * 100, 2),
        "mrr": round(mrr_sum / total, 4),
        "ndcg_at_3": round(ndcg_3_sum / total, 4),
        "ndcg_at_5": round(ndcg_5_sum / total, 4),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "good_cases": good_cases,
        "bad_cases": bad_cases
    }


def run_benchmark():
    docs_dir = PROJECT_ROOT / "data" / "docs"
    eval_csv = CURRENT_DIR / "eval_dataset.csv"

    print(f"[Benchmark] 加载知识库数据: {docs_dir}")
    chunks = load_and_chunk_documents(docs_dir)
    test_cases = load_eval_data(eval_csv)
    print(f"[Benchmark] 测试集样本数: {len(test_cases)}")

    print("[Benchmark] 初始化 TF-IDF 基线检索器...")
    tfidf = TfidfRetriever(chunks)

    print("[Benchmark] 初始化 BGE 语义检索器...")
    bge = BgeSemanticRetriever(chunks)

    print("[Benchmark] 初始化 Hybrid 混合检索器...")
    hybrid = HybridRetriever(tfidf, bge)

    results = []
    print("\n>>> 开始评测 TF-IDF 基线...")
    r_tfidf = evaluate_retriever(tfidf, test_cases, "TF-IDF (传统基线)")
    results.append(r_tfidf)

    print(">>> 开始评测 BGE 语义检索...")
    r_bge = evaluate_retriever(bge, test_cases, "BGE-small-zh (现代核心)")
    results.append(r_bge)

    print(">>> 开始评测 Hybrid 混合检索...")
    r_hybrid = evaluate_retriever(hybrid, test_cases, "Hybrid (RRF 混合增强)", is_hybrid=True)
    results.append(r_hybrid)

    # 打印对比表格
    print("\n" + "=" * 70)
    print("武汉晴川学院 RAG 检索系统基准对比评测结果 (Benchmark Results)")
    print("=" * 70)
    header = f"{'检索方法 (Method)':<24} | {'Hit@1 (%)':<9} | {'Hit@3 (%)':<9} | {'Hit@5 (%)':<9} | {'MRR':<7} | {'延迟(ms)':<8}"
    print(header)
    print("-" * 70)
    for r in results:
        line = f"{r['model_name']:<24} | {r['hit_at_1']:<9} | {r['hit_at_3']:<9} | {r['hit_at_5']:<9} | {r['mrr']:<7} | {r['avg_latency_ms']:<8}"
        print(line)
    print("=" * 70)

    # 保存 JSON
    out_json = CURRENT_DIR / "eval_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[Benchmark] 评测详细报告与案例分析已保存至: {out_json}")


if __name__ == "__main__":
    run_benchmark()
