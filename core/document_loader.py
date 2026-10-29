# -*- coding: utf-8 -*-
"""
晴川知识文档加载与切分器
支持规章制度、校园地标导览（附带3D地标ID关联）、最新新闻的结构化切块
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import List, Dict, Any


def split_text_with_overlap(text: str, source: str, title: str, landmark_id: str = "", chunk_size: int = 240, overlap: int = 40) -> List[Dict[str, Any]]:
    if not isinstance(chunk_size, int) or not isinstance(overlap, int) or not 0 <= overlap < chunk_size:
        raise ValueError("chunk_size must be positive and 0 <= overlap < chunk_size")
    cleaned = text.strip()
    if not cleaned:
        return []
    # Prefer paragraph and sentence endings, then whitespace. Never bisect a
    # Latin word; a single oversized token is retained whole.
    paragraphs = {m.end() for m in re.finditer(r"\n\s*\n", cleaned)}
    sentences = {m.end() for m in re.finditer(r"[。！？!?；;]|[.](?=\s|$)", cleaned)}
    spaces = {m.end() for m in re.finditer(r"\s+", cleaned)}
    numeric_spans = [(m.start(), m.end()) for m in re.finditer(r"\d+(?:[.:]\d+)+", cleaned)]
    def word_safe(position):
        if any(left < position < right for left, right in numeric_spans):
            return False
        return not (0 < position < len(cleaned) and re.match(r"[A-Za-z0-9_]", cleaned[position - 1]) and re.match(r"[A-Za-z0-9_]", cleaned[position]))
    chunks = []
    start = 0
    while start < len(cleaned):
        limit = min(start + chunk_size, len(cleaned))
        end = limit
        if limit < len(cleaned):
            for boundaries in (paragraphs, sentences, spaces):
                minimum_end = start + max(overlap + 1, chunk_size // 2)
                candidates = [p for p in boundaries if minimum_end <= p <= limit]
                if candidates:
                    end = max(candidates)
                    break
            else:
                while end > start and not word_safe(end):
                    end -= 1
                if end == start:
                    end = limit
                    while end < len(cleaned) and not word_safe(end):
                        end += 1
        piece = cleaned[start:end].strip()
        if piece:
            prefix = title[:200] + "\n"
            budget = 1800 - len(prefix)
            context_start = max(0, min(start - max(0, (budget - (end - start)) // 2), len(cleaned) - budget))
            chunks.append({"source": source, "title": title, "landmark_id": landmark_id,
                           "chunk_id": len(chunks), "text": piece,
                           "context_text": prefix + cleaned[context_start:context_start + budget]})
        if end == len(cleaned):
            break
        next_start = end if end - start <= overlap else end - overlap
        while next_start < end and not word_safe(next_start):
            next_start += 1
        # A short sentence must still advance, without growing the overlap.
        start = next_start
    return chunks


def load_and_chunk_documents(docs_dir: str | Path, chunk_size: int = 240, overlap: int = 40) -> List[Dict[str, Any]]:
    if not isinstance(chunk_size, int) or not isinstance(overlap, int) or not 0 <= overlap < chunk_size:
        raise ValueError("chunk_size must be positive and 0 <= overlap < chunk_size")
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        raise FileNotFoundError(f"知识库目录不存在: {docs_path}")

    all_chunks = []
    for md_file in sorted(docs_path.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        source = md_file.stem

        sections = re.split(r'\n(?=#{1,3}\s)', text)
        doc_title = text.split("\n")[0].lstrip("# ").strip() or source
        for section_index, sec in enumerate(sections):
            sec = sec.strip()
            if not sec:
                continue
            heading = re.match(r"^#{1,3}\s+([^\n]+)", sec)
            sec_title = heading.group(1).strip() if heading else doc_title
            landmark = re.search(r"[（(]地标编号[:：]\s*([A-Za-z0-9_-]+)[）)]", sec_title)
            landmark_id = landmark.group(1) if landmark else ""
            if landmark:
                sec_title = sec_title[:landmark.start()].strip()
            sub_chunks = split_text_with_overlap(sec, source=source, title=sec_title,
                landmark_id=landmark_id, chunk_size=chunk_size, overlap=overlap)
            url = re.search(r"https?://[^\s<>\])）]+", sec)
            date = re.search(r'发布时间[^0-9]*(\d{4}-\d{2}-\d{2})', sec)
            for chunk in sub_chunks:
                chunk['published_at'] = date.group(1) if date else ''
                chunk["section_id"] = f"{source}:{section_index}"
                if url:
                    chunk["url"] = url.group(0)
            all_chunks.extend(sub_chunks)

    # 规范化唯一索引 ID
    for idx, c in enumerate(all_chunks):
        c["global_id"] = idx

    return all_chunks


if __name__ == "__main__":
    chunks = load_and_chunk_documents("last/qinchuan_rag/data/docs")
    print(f"成功加载并切分文本块: {len(chunks)} 个")
    if chunks:
        sample = chunks[0]
        print("样例块:", sample["source"], "|", sample["title"], "| landmark:", sample["landmark_id"])
        print("文本预览:", sample["text"][:80], "...")
