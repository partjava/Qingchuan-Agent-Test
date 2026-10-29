# -*- coding: utf-8 -*-
"""
现代 NLP 语义检索核心：基于 BGE 中文向量模型 (BAAI/bge-small-zh-v1.5)
实现高精度语义密集向量嵌入与相似度计算
"""

from __future__ import annotations
import os
import hashlib
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel


def corpus_model_fingerprint(corpus, model_dir):
    """Hash every input text plus the model identity and local model assets."""
    digest = hashlib.sha256()
    digest.update(json.dumps({"version": 2, "model": str(model_dir), "max_length": 512,
                              "pooling": "cls", "normalize": True, "corpus": corpus},
                             ensure_ascii=False, sort_keys=True).encode("utf-8"))
    model_path = Path(model_dir)
    if model_path.is_dir():
        for asset in sorted(model_path.rglob("*")):
            if not asset.is_file():
                continue
            relative = str(asset.relative_to(model_path))
            digest.update(relative.encode("utf-8"))
            if asset.suffix in {".json", ".txt", ".model"}:
                digest.update(asset.read_bytes())
            else:
                stat = asset.stat()
                digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
    return digest.hexdigest()


def valid_cached_embeddings(embeddings, count, dimension):
    return (isinstance(embeddings, np.ndarray) and embeddings.ndim == 2
            and embeddings.shape == (count, dimension)
            and np.issubdtype(embeddings.dtype, np.floating)
            and bool(np.isfinite(embeddings).all()))


class BgeSemanticRetriever:
    def __init__(self, chunks: List[Dict[str, Any]], model_dir: str | Path = None):
        self.chunks = chunks
        self.corpus = [c["text"] for c in chunks]

        # 确定本地模型目录
        if model_dir is None:
            default_p = Path(__file__).resolve().parents[1] / "models" / "bge-small-zh-v1.5"
            if default_p.exists():
                self.model_dir = str(default_p)
            else:
                self.model_dir = "BAAI/bge-small-zh-v1.5"
        else:
            self.model_dir = str(model_dir)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[BgeRetriever] 正在加载 BGE 向量模型 ({self.model_dir}) 到 {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        self.model = AutoModel.from_pretrained(self.model_dir).to(self.device)
        self.model.eval()

        # 检查向量缓存以实现毫秒级快速启动
        cache_dir = Path(__file__).resolve().parents[1] / "data"
        cache_file = cache_dir / "bge_embeddings_cache.npy"
        hash_file = cache_dir / "bge_hash.txt"
        current_sig = corpus_model_fingerprint(self.corpus, self.model_dir)
        dimension = self.model.config.hidden_size

        cached_loaded = False
        if cache_file.exists() and hash_file.exists():
            try:
                saved_sig = hash_file.read_text(encoding="utf-8").strip()
                if saved_sig == current_sig:
                    self.doc_embeddings = np.load(cache_file, allow_pickle=False)
                    if valid_cached_embeddings(self.doc_embeddings, len(self.corpus), dimension):
                        print(f"[BgeRetriever] 命中向量磁盘缓存，成功秒级载入 {self.doc_embeddings.shape} 向量！")
                        cached_loaded = True
            except Exception as e:
                print(f"[BgeRetriever] 读取向量缓存失败，将重新计算: {e}")

        if not cached_loaded:
            print(f"[BgeRetriever] 正在对 {len(self.corpus)} 个知识块进行向量化离线建库...")
            self.doc_embeddings = self._encode_texts(self.corpus)
            print(f"[BgeRetriever] 向量知识库构建完毕，维度: {self.doc_embeddings.shape}")
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                np.save(cache_file, self.doc_embeddings)
                hash_file.write_text(current_sig, encoding="utf-8")
                print(f"[BgeRetriever] 已持久化向量缓存至: {cache_file}")
            except Exception as e:
                print(f"[BgeRetriever] 保存向量缓存异常: {e}")

    def _encode_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.empty((0, self.model.config.hidden_size), dtype=np.float32)
        all_embeddings = []
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                encoded = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt"
                ).to(self.device)

                outputs = self.model(**encoded)
                # CLS token 或 mean pooling (BGE 官方推荐取 [CLS] 即 outputs[0][:, 0])
                cls_embeddings = outputs[0][:, 0]
                norm_embeddings = F.normalize(cls_embeddings, p=2, dim=1)
                all_embeddings.append(norm_embeddings.cpu().numpy())

        return np.vstack(all_embeddings)

    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """计算查询与知识块的语义余弦相似度并排序返回 Top-K"""
        if not query.strip():
            return []

        # BGE 建议对于短查询可加入特定前缀，通用场景直接编码即可
        query_embedding = self._encode_texts([query])[0] # shape: (dim,)
        
        # 因为向量已经做过 L2 归一化，点积即为余弦相似度
        scores = np.dot(self.doc_embeddings, query_embedding) # shape: (num_docs,)

        top_k = min(max(1, top_k), len(scores))
        top_indices = np.argsort(-scores)[:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            results.append((self.chunks[idx], score))

        return results


if __name__ == "__main__":
    from document_loader import load_and_chunk_documents
    chunks = load_and_chunk_documents("last/qinchuan_rag/data/docs")
    retriever = BgeSemanticRetriever(chunks)

    test_q = "图书馆几点关闭？"
    res = retriever.retrieve(test_q, top_k=3)
    print(f"\n=== BGE 语义检索测试: '{test_q}' ===")
    for rank, (chunk, score) in enumerate(res, 1):
        print(f"[{rank}] 来源: {chunk['source']} | 分数: {score:.4f}")
        print(f"    内容: {chunk['text'][:70]}...")
