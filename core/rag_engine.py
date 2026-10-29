# -*- coding: utf-8 -*-

"""

晴川 RAG 智能问答中枢引擎

集成：提示词工程 + 双引擎检索调用 + 知识溯源 + 安全防御（防注入/防幻觉）+ 3D 地标智能联动 + 智能自然语言答案清洗合成

"""

from __future__ import annotations

import os

import re

import json

import time

import requests

from pathlib import Path

from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.ner_extractor import QingchuanNERExtractor

from core.query_suggester import CampusQuerySuggester

from core.direct_extractor import CampusDirectAnswerExtractor

from core.query_understanding import analyze_query, plan_subqueries, extract_navigation_route

from core.evidence import select_evidence, plain_text, is_topic_lookup, lexical_overlap, SOURCE_PREFERENCES

from core.composite_answer import combine_answers

from core.deepseek_client import generate_from_evidence, canonicalize_model

from core.school_constants import (

    DOC_NAME_MAPPING,

    DEFAULT_CHANNEL_URLS,

    INJECTION_KEYWORDS,

    LANDMARK_ALIASES,

    NAV_PLACES,

    NAV_PLACE_NAMES,

    clean_markdown_text

)

class QingchuanRagEngine:

    def __init__(self, tfidf_retriever, bge_retriever, hybrid_retriever):

        self.tfidf_retriever = tfidf_retriever

        self.bge_retriever = bge_retriever

        self.hybrid_retriever = hybrid_retriever

        self.ner = QingchuanNERExtractor()

        self.suggester = CampusQuerySuggester()

        self.direct_extractor = CampusDirectAnswerExtractor()

    def _append_reading_sources(self, question, citations, candidates):
        """Keep up to three relevant article contexts even if slot extraction failed."""
        result = [dict(c) for c in citations]
        seen = {(c['source'], c.get('url') or c.get('section_id') or c.get('title')) for c in result}
        topic = analyze_query(question)['topic']
        preferred = SOURCE_PREFERENCES.get(topic, ())
        for row in candidates:
            if len(result) >= 3:
                break
            chunk = row[0]
            if (chunk['source'] not in preferred and
                    lexical_overlap(question, chunk.get('context_text') or chunk['text']) < .18):
                continue
            url, article = self._resolve_chunk_article(chunk['source'], chunk.get('title', ''), chunk['text'])
            url = chunk.get('url') or url
            # A large category/collection is not a standalone reading article.
            if len(article) > 24000:
                continue
            key = (chunk['source'], url or chunk.get('section_id') or chunk.get('title'))
            if key in seen:
                continue
            seen.add(key)
            article = article or chunk.get('context_text') or chunk['text']
            result.append(dict(index=len(result)+1, source=chunk['source'],
                doc_name=DOC_NAME_MAPPING.get(chunk['source'], chunk['source']),
                title=plain_text(chunk.get('title', '')), preview=plain_text(chunk['text'])[:180],
                full_text=article, evidence_text=plain_text(chunk['text'])[:500], url=url,
                section_id=chunk.get('section_id', ''), published_at=chunk.get('published_at', ''),
                used_for_answer=False, images=[]))
        return result

    def _check_security(self, query: str) -> Optional[str]:

        """检查输入安全性：拦截提示注入与恶意越权请求"""

        query_lower = query.lower()

        for kw in INJECTION_KEYWORDS:

            if kw.lower() in query_lower:

                return "【安全风控提醒】检测到潜在的提示词注入或越权指令，该请求已被系统安全护栏拦截。请围绕晴川校园信息进行规范咨询。"

        return None

    def _detect_navigation(self, query: str) -> Optional[Dict[str, Any]]:
        """检测并解析从起点到终点的路线规划意图，提供步行时间预估与3D地图导航联动"""
        nav_info = extract_navigation_route(query)
        if not nav_info:
            return None

        from_id = nav_info['from_id']
        to_id = nav_info['to_id']
        from_name = nav_info['from_name']
        to_name = nav_info['to_name']

        is_duration_inquiry = any(w in query for w in ('多长时间', '多久', '多远', '几分钟', '多少米', '远吗', '远不远', '耗时', '时长', '几小时'))

        desc = f"🚩 晴川校园步行导航：从【{from_name}】前往【{to_name}】\n\n"

        if (from_id == "south_gate" and to_id == "library") or (from_id == "library" and to_id == "south_gate"):
            desc += "1. 从南正大门出发，沿迎宾大道主干道笔直向北步行约 140 米，途经行政综合楼与教3栋路口；\n"
            desc += "2. 行至情缘湖（惜缘湖）环湖步道岔口，沿湖东林荫小道前行约 80 米；\n"
            desc += "3. 前方即可看到晴川图书馆正门大厅入口。\n\n"
            desc += "🚶 全程约 320 米，步行用时约 4 分钟。左侧 3D 地图已为你自动绘制【红色导航轨迹线】并联动带路！"
        elif (from_id == "teach_1" and to_id == "canteen_main") or (from_id == "canteen_main" and to_id == "teach_1"):
            desc += "1. 从教学楼1（教1栋）西侧大门出发，经过教3栋前广场；\n"
            desc += "2. 沿中心主道向西直行约 160 米，穿越羽毛球场北侧通道；\n"
            desc += "3. 前方即是一食堂主楼，配有多层学生就餐大厅。\n\n"
            desc += "🚶 全程约 240 米，步行用时约 3 分钟。左侧 3D 地图已为你实时高亮【红色导航轨迹】！"
        elif (from_id == "south_gate" and to_id == "canteen_main") or (from_id == "canteen_main" and to_id == "south_gate"):
            desc += "1. 从南正大门出发，沿迎宾大道主干道向北直行约 160 米，途经行政综合楼与教3栋路口；\n"
            desc += "2. 在中心主道十字路口往西（左转）进入博雅路林荫道，沿羽毛球场南侧直行约 220 米；\n"
            desc += "3. 途经教1栋与超市商业街，正前方即达学生一食堂（主食堂）正门就餐大厅。\n\n"
            desc += "🚶 全程约 480 米，正常步行耗时约 5~6 分钟（快走约 4 分钟，骑行共享单车约 2 分钟）。左侧 3D 地图已为你自动绘制【红色导航轨迹线】并联动带路！"
        elif (from_id == "south_gate" and to_id in ("stadium", "gym")) or (from_id in ("stadium", "gym") and to_id == "south_gate"):
            desc += "1. 从南正大门出发，沿迎宾大道向北直行至行政楼路口；\n"
            desc += "2. 向东北方向沿环湖东路直行约 320 米，经过教4栋与体育运动区岔口；\n"
            desc += "3. 正前方即可看到晴川田径运动场看台与室内综合体育馆。\n\n"
            desc += "🚶 全程约 520 米，步行用时约 6~7 分钟。左侧 3D 地图已为你点亮【红色导航轨迹】！"
        elif (from_id == "library" and to_id == "canteen_main") or (from_id == "canteen_main" and to_id == "library"):
            desc += "1. 从晴川图书馆正门出发，沿惜缘湖环湖小道向西南步行约 120 米；\n"
            desc += "2. 穿过博学路主路口，沿一食堂东侧林荫便道直行约 180 米；\n"
            desc += "3. 正前方即达学生一食堂与商业街入口。\n\n"
            desc += "🚶 全程约 300 米，步行用时约 4 分钟。左侧 3D 地图已为你点亮【红色导航轨迹】！"
        elif from_id == "south_gate" and to_id.startswith("teach_"):
            desc += f"1. 从南正大门出发，沿迎宾大道向北直行约 150 米；\n"
            desc += f"2. 在教学中心区路标指引下行至【{to_name}】东/南入口；\n"
            desc += f"3. 到达教学楼大厅，内设多媒体教室与公共自习空间。\n\n"
            desc += f"🚶 全程约 220~350 米，步行用时约 3~5 分钟。左侧 3D 地图已为你点亮【红色导航轨迹】！"
        else:
            desc += f"1. 从【{from_name}】出发，进入就近校园干道；\n"
            desc += f"2. 沿校区规划林荫大道沿线行进，前往【{to_name}】方位；\n"
            desc += f"3. 到达【{to_name}】正门入口。\n\n"
            desc += f"🚶 全程约 300~450 米，正常步行用时约 4~6 分钟（骑行约 2 分钟）。左侧 3D 校园已实时调用最短路径算法，为你点亮【红色导航轨迹】并完成视角居中跟踪！"

        if is_duration_inquiry:
            time_match = re.search(r'全程约\s*([0-9~～\s]+米).*?步行(?:用时|耗时)?约\s*([0-9~～\s]+分钟)', desc)
            if time_match:
                dist_str = time_match.group(1).strip()
                min_str = time_match.group(2).strip()
                prefix = f"⏱️ 【步行时间与距离预估】\n从【{from_name}】前往【{to_name}】全程约 {dist_str}，正常步行耗时约 {min_str}（快走约 4 分钟，骑行共享单车约 2 分钟）。\n\n"
                desc = prefix + desc

        return {
            "from_id": from_id,
            "from_name": from_name,
            "to_id": to_id,
            "to_name": to_name,
            "answer": desc
        }

    def _detect_landmark(self, query: str, chunks: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:

        """检测问题或检索片段中涉及的 3D 校园地标 ID 与展示名称"""

        query_lower = query.lower()

        # 1. 优先从 query 匹配地标别名

        for lid, aliases in LANDMARK_ALIASES.items():

            for a in aliases:

                if a in query_lower:

                    name_map = {

                        "admin_1": "综合楼1栋 (行政中枢/教务处)",

                        "admin_2": "综合楼2栋 (学院行政/招就处)",

                        "library": "晴川图书馆",

                        "lake": "惜缘湖",

                        "stadium": "田径场/足球场",

                        "gym": "体育馆",

                        "teach_1": "教学楼1栋",

                        "teach_2": "教学楼2栋",

                        "teach_3": "教学楼3栋",

                        "teach_4": "教学楼4栋",

                        "computer_center": "计算机实验中心",

                        "lab_1": "实验楼1栋",

                        "lab_2": "实验楼2栋",

                        "art_museum": "晴川美术馆",

                        "canteen_main": "学生第一食堂",

                        "theater_market": "晴川小剧场 & 综合超市",

                        "south_gate": "正大门",

                        "dorm_1": "学生公寓园区"

                    }

                    display_name = name_map.get(lid, a)

                    if a in ("教务处", "科研处", "财务处", "人事处", "一站式"):

                        display_name = f"综合楼1栋（{a}所在地）"

                    elif a in ("招就处", "招生处", "就业处", "校团委"):

                        display_name = f"综合楼2栋（{a}所在地）"

                    return {"id": lid, "trigger": display_name}

        # 2. 从检索出的高相关 chunk 中寻找

        for chunk in chunks[:2]:

            lid = chunk.get("landmark_id")

            if lid:

                mapped_id = {

                    "admin": "admin_1",

                    "canteen": "canteen_main",

                    "dorm": "dorm_1"

                }.get(lid, lid)

                if mapped_id in LANDMARK_ALIASES:

                    return {"id": mapped_id, "trigger": chunk.get("title", mapped_id)}

        return None

    def _resolve_chunk_article(self, source: str, title: str, text: str) -> tuple[str, str]:

        """为检索切块精准解析其在晴川官网的原始链接与完整文章全文"""

        if not hasattr(self, "_docs_cache"):

            self._docs_cache = {}

            

        doc_text = self._docs_cache.get(source)

        if doc_text is None:

            p = PROJECT_ROOT / "data" / "docs" / f"{source}.md"

            doc_text = p.read_text(encoding="utf-8") if p.exists() else ""

            self._docs_cache[source] = doc_text

            

        if doc_text and title and len(title) >= 4:

            heading_match = re.search(r'(?m)^#{1,3}\s+' + re.escape(title) + r'\s*$', doc_text)
            pos = heading_match.start() if heading_match else doc_text.find(title)

            if pos != -1:

                end_pos = doc_text.find("\n---", pos)
                current_heading = re.match(r'(#{1,3})\s', doc_text[pos:])
                if current_heading:
                    level = len(current_heading.group(1))
                    next_heading = re.search(r'\n#{1,' + str(level) + r'}\s', doc_text[pos:])
                    if next_heading:
                        boundary = pos + next_heading.start()
                        end_pos = min(end_pos, boundary) if end_pos != -1 else boundary

                article_text = doc_text[pos:end_pos].strip() if end_pos != -1 else doc_text[pos:].strip()

                url_match = (

                    re.search(r'官网原文链接[^\n]*?(https?://[^\s\n\)\]]+)', article_text) or

                    re.search(r'学院官方主页[^\n]*?(https?://[^\s\n\)\]]+)', article_text) or

                    re.search(r'官方网站[^\n]*?(https?://[^\s\n\)\]]+)', article_text) or

                    re.search(r'机构主页[^\n]*?(https?://[^\s\n\)\]]+)', article_text) or

                    re.search(r'(https?://[^\s\n\)\]]+)', article_text)

                )

                found_url = (url_match.group(1) if (url_match and url_match.groups()) else (url_match.group(0) if url_match else "")).rstrip(']').rstrip(')').rstrip('。')

                if found_url:

                    return found_url, article_text

        # 尝试从切块文本自身提取

        url_match = (

            re.search(r'官网原文链接[^\n]*?(https?://[^\s\n\)\]]+)', text) or

            re.search(r'学院官方主页[^\n]*?(https?://[^\s\n\)\]]+)', text) or

            re.search(r'官方网站[^\n]*?(https?://[^\s\n\)\]]+)', text) or

            re.search(r'机构主页[^\n]*?(https?://[^\s\n\)\]]+)', text) or

            re.search(r'(https?://[^\s\n\)\]]+)', text)

        )

        fallback_url = (url_match.group(1) if (url_match and url_match.groups()) else (url_match.group(0) if url_match else DEFAULT_CHANNEL_URLS.get(source, "https://www.qcuwh.edu.cn"))).rstrip(']').rstrip(')').rstrip('。')

        return fallback_url, text

    def query(self, user_question: str, mode: str = "hybrid", top_k: int = 3,

              use_ollama: bool = False, deepseek_key: Optional[str] = None,

              model: Optional[str] = None, history=None, allow_generation: bool = True,

              thinking: bool = False, api_url: Optional[str] = None,

              ollama_url: Optional[str] = None, ollama_model: Optional[str] = None) -> Dict[str, Any]:

        if not isinstance(user_question, str) or not user_question.strip():

            raise ValueError('问题不能为空')

        if mode not in ('hybrid', 'bge', 'tfidf') or not isinstance(top_k, int) or not 1 <= top_k <= 10:

            raise ValueError('mode 或 top_k 不合法')

        original = user_question.strip()

        analysis = analyze_query(original, history)

        # 整句检查，不能通过拆句将恶意部分丢弃后继续执行。

        if self._check_security(original) or self._check_security(analysis['rewritten_query']) or analysis['clarification']:

            return self._query_single(original, mode, top_k, use_ollama, deepseek_key, model, history, allow_generation, thinking, api_url, ollama_url, ollama_model)

        plans = plan_subqueries(original, history)

        if len(plans) == 1:

            result = self._query_single(original, mode, top_k, use_ollama, deepseek_key, model, history, allow_generation, thinking, api_url, ollama_url, ollama_model)

            result['partial'] = False

            return result

        results = [self._query_single(plan['question'], mode, top_k, history=[], allow_generation=False, collect_reading=False)

                   for plan in plans]

        result = combine_answers(original, mode, analysis, plans, results)

        if len(result['citations']) < 3:
            reading_retriever = {'hybrid': self.hybrid_retriever, 'tfidf': self.tfidf_retriever, 'bge': self.bge_retriever}[mode]
            candidates = reading_retriever.retrieve(analysis['rewritten_query'], top_k=30) if reading_retriever else []
            result['citations'] = self._append_reading_sources(original, result['citations'], candidates)

        if result['citations']:

            generation_chunks = [dict(source=c['source'], text=c['evidence_text']) for c in result['citations']]

            answer, provider, generation = self._maybe_generate(original, generation_chunks, result['citations'],

                result['evidence'], result['answer'], use_ollama, deepseek_key, model, allow_generation, thinking,

                require_all=True, partial=result['partial'], mode=mode,

                api_url=api_url, ollama_url=ollama_url, ollama_model=ollama_model)

            result.update(answer=answer, llm_provider=provider, generation=generation, raw_model_answer=(generation or {}).get('raw_model_answer'))
            if generation.get('status') == 'success':
                result['local_partial'] = result['partial']
                result['answer_assessment'] = 'model_reading'
                result['refused'] = False
                result['evidence_status'] = 'model_reading'
            used = {int(n) for n in re.findall(r'\[(\d+)\]', answer)}
            for citation in result['citations']:
                citation['used_for_answer'] = citation['index'] in used

        return result

    def _query_single(self, user_question: str, mode: str = 'hybrid', top_k: int = 3,

                      use_ollama: bool = False, deepseek_key: Optional[str] = None,

                      model: Optional[str] = None, history=None, allow_generation: bool = True,

                      thinking: bool = False, api_url: Optional[str] = None,

                      ollama_url: Optional[str] = None, ollama_model: Optional[str] = None, collect_reading=True) -> Dict[str, Any]:

        if not isinstance(user_question, str) or not user_question.strip():

            raise ValueError("问题不能为空")

        if mode not in ("hybrid", "bge", "tfidf") or not isinstance(top_k, int) or not 1 <= top_k <= 10:

            raise ValueError("mode 或 top_k 不合法")

        original = user_question.strip()

        analysis = analyze_query(original, history)

        question = analysis['rewritten_query']

        base = dict(question=original, mode=mode, query_analysis=analysis, evidence=[],

                    refused=False, clarification=False, citations=[], entities=[],

                    target_landmark=None, ablation=None, related_questions=[], images=[],

                    retrieved_chunks=[], security_flag=False)

        # 安全检查必须先于导航以及历史重写。

        alert = self._check_security(original) or self._check_security(question)

        if alert:

            return dict(base, answer=alert, security_flag=True, refused=True)

        if analysis['clarification']:

            return dict(base, answer="请明确你指的是哪个地点、部门或事项，例如图书馆、实验室或奖学金。",

                        clarification=True)

        nav = self._detect_navigation(question)

        if nav:

            return dict(base, answer=nav['answer'],

                target_landmark={'id': nav['to_id'], 'trigger': nav['to_name']},

                navigation={k: nav[k] for k in ('from_id', 'from_name', 'to_id', 'to_name')},

                related_questions=[f"{nav['to_name']}开放时间是什么？"],

                llm_provider='校园道路导航')

        pool_size = max(30, top_k * 8)

        times, raw = {}, {}

        for name, retriever in (('tfidf', self.tfidf_retriever), ('bge', self.bge_retriever)):

            start = time.perf_counter()

            raw[name] = retriever.retrieve(question, top_k=pool_size) if retriever else []

            times[name] = (time.perf_counter() - start) * 1000

        start = time.perf_counter()

        raw['hybrid'] = (self.hybrid_retriever.fuse(question, raw['tfidf'], raw['bge'], pool_size)

                         if self.hybrid_retriever else [])

        times['hybrid'] = times['tfidf'] + times['bge'] + (time.perf_counter() - start) * 1000

        names = {'tfidf': '字符 TF-IDF 基线', 'bge': 'BGE 语义检索', 'hybrid': '加权 RRF + 证据精排'}

        mechanisms = {'tfidf': '字符 1–2 gram TF-IDF 余弦相似度',

            'bge': 'BGE 归一化向量余弦相似度',

            'hybrid': '关键词权重0.35、语义权重0.65，扩大召回后按问题与证据精排；耗时含两路召回'}

        ablation = {}

        for name in names:

            ablation[name] = dict(name=names[name], time_ms=round(times[name], 1),

                mechanism=mechanisms[name], top_chunks=[dict(rank=i+1,

                title=plain_text(row[0].get('title', '')), source=DOC_NAME_MAPPING.get(row[0]['source'], row[0]['source']),

                score=round(float(row[1]), 5), snippet=plain_text(row[0]['text'])[:85])

                for i, row in enumerate(raw[name][:3])])

        article_reading = analysis['intent'] == 'general'
        selected = raw[mode][:top_k]
        if article_reading:
            selected, seen_articles = [], set()
            for row in raw[mode]:
                chunk = row[0]
                key = chunk.get('url') or (chunk['source'], chunk.get('section_id', chunk.get('title', '')))
                if key not in seen_articles:
                    _, article = self._resolve_chunk_article(chunk['source'], chunk.get('title', ''), chunk['text'])
                    expanded = dict(chunk, context_text=article or chunk.get('context_text') or chunk['text'])
                    if select_evidence(question, [expanded], 1):
                        seen_articles.add(key)
                        selected.append((expanded, *row[1:]))
                if len(selected) >= 3:
                    break

        chunks = [row[0] for row in selected]

        entities = self.ner.extract(question)

        # General/FAQ questions need the answer paragraph beyond the hit sentence.
        if analyze_query(question)['intent'] == 'general':
            chunks = [dict(chunk) for chunk in chunks]
            for chunk in chunks:
                _, article = self._resolve_chunk_article(chunk['source'], chunk.get('title', ''), chunk['text'])
                if article:
                    chunk['context_text'] = article
        evidence = select_evidence(question, chunks)

        reading_sources = self._append_reading_sources(question, [], raw[mode]) if collect_reading else []
        base.update(ablation=ablation, entities=entities)


        mode_label = {'hybrid': '混合检索与精排', 'bge': 'BGE 稠密语义', 'tfidf': 'TF-IDF 统计词频'}.get(mode, '本地检索')

        if not evidence:
            missing_message = '现有知识库没有找到能直接回答这个问题的明确依据。请补充具体事项，或向相关部门核实。'
            if analysis['intent'] == 'location':
                target = self._detect_landmark(question, chunks)
                if target:
                    base['target_landmark'] = target
                    missing_message = '已在左侧校园示意图中定位相关地标。现有原文未明确记载其准确楼栋或校园方位，请结合示意图查看，并以学校实际标识为准。'

            key = deepseek_key or os.environ.get('DEEPSEEK_API_KEY', '').strip()

            if reading_sources:
                fallback = missing_message
                generation_chunks = [dict(source=c['source'], text=c['full_text']) for c in reading_sources]
                answer, provider, state = self._maybe_generate(question, generation_chunks, reading_sources, [], fallback,
                    use_ollama, deepseek_key, model, allow_generation, thinking, mode=mode,
                    api_url=api_url, ollama_url=ollama_url, ollama_model=ollama_model)
                success = state.get('status') == 'success'
                used = {int(n) for n in re.findall(r'\[(\d+)\]', answer)}
                for citation in reading_sources:
                    citation['used_for_answer'] = citation['index'] in used
                return dict(base, refused=not success, answer=answer, citations=reading_sources, evidence=[],
                    llm_provider=provider, generation=state,
                    evidence_status='model_reading' if success else 'insufficient',
                    related_questions=self.suggester.suggest(question, entities, []))

            return dict(base, refused=True,

                answer=missing_message,

                related_questions=self.suggester.suggest(question, entities, []),

                evidence_status='insufficient', llm_provider=f'{mode_label} · 证据不足（已规范拒答）')

        # 仅保留实际用于回答的块；重新编号确保每句话与证据一一对应。

        reading_evidence = list(evidence)
        # Keep all three reading sources, even when the answer uses only the newest.
        if article_reading:
            reading_evidence = []
            for index, chunk in enumerate(chunks):
                reading_evidence.extend(dict(item, chunk_index=index) for item in select_evidence(question, [chunk], 3))
            evidence = reading_evidence
            if not re.search(r'20\d{2}|历年|历史|对比|比较|分别|往年', question):
                dated = [i for i, chunk in enumerate(chunks) if chunk.get('published_at')]
                if dated:
                    newest = max(chunks[i]['published_at'] for i in dated)
                    newest_indices = {i for i in dated if chunks[i]['published_at'] == newest}
                    recent = [item for item in reading_evidence if item['chunk_index'] in newest_indices]
                    if recent:
                        evidence = recent[:3]
        used_indices = (list(range(len(chunks))) if article_reading
                        else list(dict.fromkeys(item['chunk_index'] for item in evidence)))

        supported_chunks = [chunks[i] for i in used_indices]

        remap = {old: new + 1 for new, old in enumerate(used_indices)}

        citations = []

        for old in used_indices:

            chunk = chunks[old]

            url, article = self._resolve_chunk_article(chunk['source'], chunk.get('title', ''), chunk['text'])

            support = '\n'.join(item['text'] for item in reading_evidence if item['chunk_index'] == old)

            article_images = []
            if article:
                for m_img in re.finditer(r'!\[([^\]]*)\]\((/images/[^)]+)\)', article):
                    u = m_img.group(2).strip()
                    if not any(x['url'] == u for x in article_images):
                        article_images.append({'alt': m_img.group(1).strip(), 'url': u})
            for m_img in re.finditer(r'!\[([^\]]*)\]\((/images/[^)]+)\)', chunk.get('text', '')):
                u = m_img.group(2).strip()
                if not any(x['url'] == u for x in article_images):
                    article_images.append({'alt': m_img.group(1).strip(), 'url': u})

            full_doc_text = article.strip() if article and article.strip() else chunk['text'].strip()

            citations.append(dict(index=remap[old], source=chunk['source'],

                doc_name=DOC_NAME_MAPPING.get(chunk['source'], chunk['source']),

                published_at=chunk.get('published_at', ''),
                title=plain_text(chunk.get('title', '')), preview=plain_text(chunk['text'])[:180],

                full_text=full_doc_text, url=chunk.get('url') or url, evidence_text=support,
                images=article_images,

                section_id=chunk.get('section_id', '')))

        linked = [dict(citation_index=remap[item['chunk_index']], text=item['text'], score=item['score']) for item in evidence]

        answer_lines = [f"• {item['text']} [{item['citation_index']}]" for item in linked]

        answer = "🎯【核心解答】\n" + '\n'.join(answer_lines)

        if collect_reading:
            citations = self._append_reading_sources(question, citations, raw[mode])
        generation_chunks = [dict(source=c['source'], text=c['full_text']) for c in citations]

        answer, provider, generation = self._maybe_generate(question, generation_chunks, citations, linked, answer,

            use_ollama, deepseek_key, model, allow_generation, thinking, mode=mode,

            api_url=api_url, ollama_url=ollama_url, ollama_model=ollama_model)

        cited_indices = {int(index) for index in re.findall(r'\[(\d+)\]', answer)}
        for citation in citations:
            citation['used_for_answer'] = citation['index'] in cited_indices
        scores = [dict(chunk_id=row[0]['global_id'], score=round(float(row[1]), 5),

                       source=row[0]['source'], details=row[2] if len(row) > 2 else {}) for row in selected]

        images = list(dict.fromkeys(
            [im for c in supported_chunks for im in re.findall(r'!\[.*?\]\((/images/[^)]+)\)', c['text'])] +
            [img['url'] for cite in citations for img in cite.get('images', [])]
        ))

        return dict(base, answer=answer, citations=citations, evidence=linked, evidence_status='supported',

            llm_provider=provider, target_landmark=self._detect_landmark(question, supported_chunks),

            related_questions=self.suggester.suggest(question, entities, citations),

            retrieved_chunks=scores, images=images[:4], generation=generation, raw_model_answer=(generation or {}).get('raw_model_answer'))

    def _maybe_generate(self, question, chunks, citations, evidence, fallback, use_ollama=False,

                        deepseek_key=None, model=None, allow_generation=True, thinking=False,

                        require_all=False, partial=False, mode='hybrid',

                        api_url=None, ollama_url=None, ollama_model=None):

        import os

        raw_model = model or os.environ.get('DEEPSEEK_MODEL') or 'deepseek-flash'

        mode_label = {'hybrid': '混合检索与精排', 'bge': 'BGE 稠密语义', 'tfidf': 'TF-IDF 统计词频'}.get(mode, '本地检索')

        if api_url:

            model_name = (model or 'deepseek-flash').strip()

        else:

            try:

                model_name = canonicalize_model(raw_model)

            except ValueError:

                return fallback, f'{mode_label} · 本地事实证据抽取（模型名不支持，已回退）', dict(status='failed',

                    model=raw_model, error_code='invalid_model', message='模型名不支持，请使用 deepseek-flash。')

        key = deepseek_key or os.environ.get('DEEPSEEK_API_KEY', '').strip()

        state = dict(model=model_name, thinking=bool(thinking), status='not_configured', error_code=None,

                     message='未配置 API Key，使用本地证据抽取。')

        if not allow_generation:

            state.update(status='disabled', message='本次请求关闭外部生成。')

            return fallback, f'{mode_label} · 本地事实证据抽取', state

        if not key and not use_ollama:

            return fallback, f'{mode_label} · 本地事实证据抽取', state

        if key:

            if api_url:

                reply = self._call_deepseek_api(question, chunks, citations, key, model_name, thinking, api_url=api_url)

            else:

                reply = self._call_deepseek_api(question, chunks, citations, key, model_name, thinking)

            # 兼容旧调用方和测试中替换的字符串返回值，不保存请求级共享状态。

            generated = reply if isinstance(reply, str) else getattr(reply, 'content', None)

            state.update(status=getattr(reply, 'status', 'success' if generated else 'failed'),

                error_code=getattr(reply, 'error_code', None),

                message=getattr(reply, 'message', '模型未返回可用答案。' if not generated else '接口返回成功。'))

        else:

            local_model = ollama_model or 'deepseek-r1:latest'

            generated = self._call_ollama(question, chunks, citations, local_model, ollama_url=ollama_url)

            state.update(model=local_model, status='success' if generated else 'failed', message='本地 Ollama 生成模型调用。')

        article_evidence = []
        from core.evidence import sentence_units
        for citation in citations:
            for unit in sentence_units(citation.get('full_text') or citation['evidence_text']):
                if not unit.rstrip().endswith(('？', '?')):
                    article_evidence.append(dict(citation_index=citation['index'], text=unit))

        if (analyze_query(question)['intent'] == 'general'
                and not re.search(r'20\d{2}|历年|历史|对比|比较|分别|往年', question)):
            dated_citations = [c for c in citations if c.get('published_at')]
            if dated_citations:
                newest_date = max(c['published_at'] for c in dated_citations)
                newest_ids = {c['index'] for c in dated_citations if c['published_at'] == newest_date}
                article_evidence = [e for e in article_evidence if e['citation_index'] in newest_ids]

        compact = lambda value: re.sub(r'\s+', '', plain_text(value))

        complete = True
        if require_all and generated:
            for plan in plan_subqueries(question):
                slots = plan['slots']
                labels = slots['subject'] + slots.get('conditions', {}).get('grade', [])
                if labels and not all(label in generated for label in labels):
                    complete = False
        state['reading_count'] = len(citations)

        # 部分缺失时保留逐项缺失说明，生成器不能只返回有答案的项。

        if generated and complete and self._grounded_generation(generated, article_evidence or evidence, question=question):

            if key:

                disp_model = model_name if api_url else f"DeepSeek ({model_name})"

                prov = f"{disp_model} · 结合{mode_label}（证据核验通过）"

            else:

                prov = f"本地 Ollama ({ollama_model or 'deepseek-r1:latest'}) · 结合{mode_label}（证据核验通过）"

            return generated, prov, state

        if generated:

            state.update(status='validation_failed', error_code='evidence_validation',

                message='模型结果未完整通过逐项证据校验，已回退本地答案。', raw_model_answer=generated)

        return fallback, f'{mode_label} · 本地事实证据抽取（大模型结果未通过核验，已回退）', state

    @staticmethod

    def _grounded_generation(answer, evidence, question=None):
        """严格抽取与事实语义校验：每个有内容的句子必须由对应证据支撑，杜绝幻觉数字/实体与条件倒置。"""
        by_index = {}
        for item in evidence:
            key = str(item['citation_index'])
            by_index.setdefault(key, []).append(item['text'])
        claims = [line.strip() for line in answer.splitlines() if line.strip()]
        found = False
        compact = lambda s: re.sub(r'\s+', '', plain_text(s))
        wrapper_patterns = r'^(根据|综上|官方|以下|具体|注[：:]|温馨提示|如需|联系方式如下|相关信息如下|公开资料显示).*'
        
        for line in claims:
            if line in ('🎯【核心解答】', '📖【官方依据与详细参考】', '---') or line.startswith('💡') or line.startswith('📌'):
                continue
            uncertainty = re.sub(r'^(?:根据|依据)(?:现有|所给|提供的)?(?:公开)?(?:资料|原文|信息)[，,:：\s]*', '', line)
            uncertainty = re.sub(r'[（(][^（）()]*[）)]', '', uncertainty)
            if (re.search(r'^(?:原文|资料|所给原文|现有资料)(?:中)?(?:并)?(?:未明确记载|未记载|未提供|未列出)', uncertainty)
                    and not re.search(r'\d|[，,；;]|可以申请|不得申请|奖励.*元', uncertainty)):
                found = True
                continue
            if not re.findall(r'\[\d+\]', line) and re.search(wrapper_patterns, line):
                continue

            if (re.search(r'未明确|未记载|未找到|未提供|未列出|没有记载|缺少.*依据|无法确认', line)
                    and len(line) < 120
                    and not re.search(r'\d|[，,；;]|可以申请|不得申请|奖励.*元|截止.*[日周月]', line)):
                found = True
                continue
            markers = re.findall(r'\[(\d+)\]', line)
            claim = plain_text(re.sub(r'\[\d+\]', '', line)).lstrip('•- ').strip()
            if not markers or any(index not in by_index for index in markers):
                return False

            c_claim = compact(claim)
            units = [unit for index in markers for unit in by_index[index]]
            unit_compacts = [compact(u) for u in units]
            all_allowed_text = ''.join(unit_compacts) + compact(question or '')

            # 1. 完全一致直接放行
            if any(c_claim == u for u in unit_compacts):
                found = True
                continue

            # 2. 检查数字与时间是否幻觉 (如 03:00, 23:00)
            claim_nums = set(re.findall(r'\d+[:：.]?\d*', c_claim))
            allowed_nums = set(re.findall(r'\d+[:：.]?\d*', all_allowed_text))
            if not claim_nums.issubset(allowed_nums):
                return False

            # 3. 检查否定与前置条件倒置 (如 不可以 -> 可以)
            inverted_or_truncated = False
            for u in unit_compacts:
                if ('不可以' in u or '不得' in u or '严禁' in u or '禁止' in u) and ('可以' in c_claim or '允许' in c_claim):
                    if not any(neg in c_claim for neg in ('不可', '不得', '严禁', '禁止', '不能', '并未')):
                        inverted_or_truncated = True
                        break
                    for cond in re.findall(r'([^，。；]+(?:者|人员|学生|教师|条件|记录))', u):
                        if cond not in c_claim:
                            inverted_or_truncated = True
                            break
            if inverted_or_truncated:
                return False

            # 4. 去除停用词与标点后进行关键实体核验
            stop_pattern = r'[是为有的在和与及，。；、\s:：/]|根据|官方|公开|学校|资料|现有|记载|目前|现任|包括|以及|主页|网站|网址|信息|如下'
            segments = [s for s in re.split(stop_pattern, c_claim) if len(s) >= 2]
            is_valid = True
            for seg in segments:
                if seg.startswith('http'):
                    continue
                if any(neg in seg for neg in ('未记载', '未明确', '暂无', '未公开', '未直接提及', '未记录')):
                    continue
                if seg not in all_allowed_text:
                    is_valid = False
                    break

            if not is_valid:
                return False

            found = True
        return found

    def _call_deepseek_api(self, query, chunks, citations, api_key, model_name='deepseek-flash', thinking=False, api_url=None):

        return generate_from_evidence(query, chunks, citations, api_key, model_name, thinking, api_url=api_url)

    def _call_ollama(self, query: str, chunks: List[Dict[str, Any]], citations: List[Dict[str, Any]], model_name: str = "deepseek-r1:latest", ollama_url: Optional[str] = None) -> Optional[str]:

        try:

            base_url = (ollama_url or "http://localhost:11434").strip()

            if not base_url.startswith("http://") and not base_url.startswith("https://"):

                base_url = "http://" + base_url

            base_url = base_url.rstrip("/")

            context_pieces = [f"[{c['index']}] 《{c['doc_name']}》:\n" + chunks[idx]['text'] for idx, c in enumerate(citations)]

            context_str = "\n\n".join(context_pieces)

            prompt = (

                "你是校园证据问答助手。只从用户提供的选定证据中逐字摘录完整原句或完整证据条目。\n"

                "每行只写一个完整证据条目，并在行末标注它对应的引用编号，如 [1]。\n"

                "保留全部主语、否定、读者类别、等级、时间条件及例外，不得截取片段改变原意。\n"

                "不得添加、改写或推断事实；无法回答的部分不得编造。\n\n"

                f"参考资料：\n{context_str}\n\n学生问题：{query}\n助手解答："

            )

            r = requests.post(f"{base_url}/api/generate", json={"model": model_name, "prompt": prompt, "stream": False}, timeout=15)

            if r.status_code == 200:

                resp_text = r.json().get("response", "").strip()

                if resp_text:

                    return clean_markdown_text(resp_text)

        except Exception:

            pass

        return None

    def _extract_direct_answer(self, query: str, chunks: List[Dict[str, Any]]) -> Optional[str]:

        """优先直接从针对性知识抽取清晰明了的直奔主题答案，杜绝先堆砌冗长历史背景"""

        return self.direct_extractor.extract(query, chunks)

    def _intelligent_synthesis(self, query, chunks, citations):

        direct = self.direct_extractor.extract(query, chunks)

        return "🎯【核心解答】\n" + direct if direct else "现有知识库没有足够明确的回答依据。"

    def _generate_open_domain(self, question, key, model=None, use_ollama=False, thinking=False,

                              api_url=None, ollama_url=None, ollama_model=None):

        """当本地校园知识库无相关事实依据时，由大模型结合通用常识进行客观兜底解答，并打上明确标识"""

        import os

        raw_model = model or os.environ.get('DEEPSEEK_MODEL') or 'deepseek-flash'

        if api_url:

            model_name = (model or 'deepseek-flash').strip()

        else:

            try:

                model_name = canonicalize_model(raw_model)

            except ValueError:

                return None, None, None

        if not key and not use_ollama:

            return None, None, None

        system_prompt = (

            "你是智能助手。用户的问题在本地校园规章知识库中未收录直接依据。"

            "请结合通用生活与科学常识，以客观、严谨、友善的态度简要回答该问题。"

            "回答直接切入主题，条理清晰，字数控制在 200 字以内。"

            "若涉及医疗、法律或校园具体办事流程，请在回答末尾提醒用户以专业医生或学校官方公告为准。"

        )

        if key:

            endpoint = api_url.strip() if (isinstance(api_url, str) and api_url.strip()) else 'https://api.deepseek.com/chat/completions'

            if not endpoint.startswith('http://') and not endpoint.startswith('https://'):

                endpoint = 'https://' + endpoint

            if not endpoint.endswith('/chat/completions'):

                endpoint = endpoint.rstrip('/') + '/chat/completions'

            payload = {

                'model': model_name,

                'messages': [

                    {'role': 'system', 'content': system_prompt},

                    {'role': 'user', 'content': question},

                ],

                'thinking': {'type': 'enabled' if thinking else 'disabled'},

                'max_tokens': 2048,

                'stream': False,

            }

            try:

                response = requests.post(

                    endpoint,

                    headers={'Authorization': 'Bearer ' + key.strip(), 'Content-Type': 'application/json'},

                    json=payload,

                    timeout=(5, 30)

                )

                if response.status_code == 200:

                    body = response.json()

                    content = body.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

                    if content:

                        prefixed = (

                            "💡【本地知识库未收录相关规章，以下由 AI 结合通用常识解答，仅供参考】\n\n"

                            + content

                        )

                        disp = model_name if api_url else f"DeepSeek ({model_name})"

                        provider = f"{disp} · 通用常识解答（无本地证据）"

                        gen_state = dict(status='open_domain_success', model=model_name, message='知识库无匹配依据，已转由大模型开放域解答。')

                        return prefixed, provider, gen_state

            except Exception:

                pass

        elif use_ollama:

            base_url = (ollama_url or "http://localhost:11434").strip()

            if not base_url.startswith("http://") and not base_url.startswith("https://"):

                base_url = "http://" + base_url

            base_url = base_url.rstrip("/")

            local_model = (ollama_model or "deepseek-r1:latest").strip()

            try:

                r = requests.post(f"{base_url}/api/generate", json={

                    "model": local_model,

                    "prompt": f"{system_prompt}\n\n问题：{question}\n回答：",

                    "stream": False

                }, timeout=20)

                if r.status_code == 200:

                    content = r.json().get("response", "").strip()

                    if content:

                        prefixed = (

                            f"💡【本地知识库未收录相关规章，以下由 本地 Ollama ({local_model}) 结合通用常识解答，仅供参考】\n\n"

                            + content

                        )

                        provider = f"本地 Ollama ({local_model}) · 通用常识解答（无本地证据）"

                        gen_state = dict(status='open_domain_success', model=local_model, message='知识库无匹配依据，已转由本地模型开放域解答。')

                        return prefixed, provider, gen_state

            except Exception:

                pass

        return None, None, None

