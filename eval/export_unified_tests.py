# -*- coding: utf-8 -*-
"""
武汉晴川学院智能体全生命周期测试集构建与导出工具
将分散的 7 大测试维度汇总整合成一份官方标准的测试用例矩阵 (JSON + CSV)
便于直接导入 Excel 查看或作为大赛支撑附件
"""

import os
import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"

def load_json(filename):
    p = EVAL_DIR / filename
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def build_unified_test_suite():
    suite = []
    
    # 1. 功能准确性测试 (从 answer_dataset.json 中提取 33 道事实可答题)
    answer_cases = load_json("answer_dataset.json")
    for item in answer_cases:
        if not item.get("expected_refusal") and not item.get("expected_clarification") and not item.get("history"):
            suite.append({
                "test_id": f"TC-FUNC-{item['id']}",
                "dimension": "1. 功能准确性测试",
                "sub_category": "垂直业务事实问答",
                "test_name": f"校园规章精准事实验证: {item['question'][:15]}...",
                "input_prompt": item["question"],
                "context_history": "",
                "expected_behavior": "基于权威资料直出核心事实与数字，且附带来源依据",
                "assertion_criteria": f"需包含关键词事实: {', '.join(item.get('expected_facts', []))}，依据来源命中: {', '.join(item.get('expected_sources', []))}"
            })
            
    # 2. 多轮对话与指代消解测试 (从 answer_dataset 中带 history 的题目提取)
    for item in answer_cases:
        if item.get("history"):
            hist_str = " | ".join([f"{h['role']}: {h['content']}" for h in item["history"]])
            suite.append({
                "test_id": f"TC-MULTI-{item['id']}",
                "dimension": "4. 多轮对话与记忆测试",
                "sub_category": "上下文指代消解与省略问句恢复",
                "test_name": f"多轮省略提问继承: {item['question']}",
                "input_prompt": item["question"],
                "context_history": hist_str,
                "expected_behavior": "准确继承上轮对话实体，不发生语义漂移",
                "assertion_criteria": f"正确解析上下文主语并作答，命中核心事实: {', '.join(item.get('expected_facts', []))}"
            })

    # 3. 工具调用与规划测试 (从 agent_dataset.json 提取)
    agent_cases = load_json("agent_dataset.json")
    for item in agent_cases:
        tools_str = ", ".join(item.get("required_tools", [])) or "主动澄清/拒绝"
        suite.append({
            "test_id": f"TC-TOOL-{item['id']}",
            "dimension": "2. 工具调用与自主规划测试",
            "sub_category": "ReAct状态机工具选择与执行",
            "test_name": f"办事智能体任务调度: {item['question'][:16]}...",
            "input_prompt": item["question"],
            "context_history": "",
            "expected_behavior": f"按需自主触发工具链: [{tools_str}]",
            "assertion_criteria": f"工具调用序列包含 {tools_str}，返回结构化办事步骤与核查建议"
        })

    # 4. RAG 检索质量测试 (从 eval_dataset.csv 提取代表性检索用例)
    eval_csv_path = EVAL_DIR / "eval_dataset.csv"
    if eval_csv_path.exists():
        with open(eval_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, 1):
                suite.append({
                    "test_id": f"TC-RAG-{idx:02d}",
                    "dimension": "3. RAG 检索质量测试",
                    "sub_category": "密集+稀疏双路召回及重排",
                    "test_name": f"多模检索召回能力验证: {row.get('question','')[:15]}...",
                    "input_prompt": row.get("question", ""),
                    "context_history": "",
                    "expected_behavior": f"在 Top-3 召回候选中精确命中目标知识库: {row.get('target_source','')}",
                    "assertion_criteria": f"TF-IDF 与 BGE 混合 RRF 重排序后 Hit@3 = 1，排在首选推荐位"
                })

    # 5. 对抗性与安全防护测试 (从 security_dataset.json 提取)
    security_cases = load_json("security_dataset.json")
    for item in security_cases:
        suite.append({
            "test_id": f"TC-SEC-{item['id']}",
            "dimension": "5. 对抗性与安全测试",
            "sub_category": item.get("type", "越狱与安全注入"),
            "test_name": item.get("name", "对抗安全测试"),
            "input_prompt": item.get("prompt", ""),
            "context_history": "",
            "expected_behavior": item.get("expected_behavior", "拦截或拒答"),
            "assertion_criteria": item.get("pass_criteria", "严格防范注入与越狱")
        })

    # 6. 边界与异常鲁棒性测试 (从 boundary_dataset.json 提取)
    boundary_cases = load_json("boundary_dataset.json")
    for item in boundary_cases:
        suite.append({
            "test_id": f"TC-BOUND-{item['id']}",
            "dimension": "6. 边界与异常测试",
            "sub_category": item.get("type", "边界与异常"),
            "test_name": item.get("name", "边界鲁棒性测试"),
            "input_prompt": item.get("prompt", ""),
            "context_history": "",
            "expected_behavior": item.get("expected_behavior", "安全兜底或追问"),
            "assertion_criteria": item.get("pass_criteria", "系统鲁棒不崩溃，符合安全规范")
        })

    # 7. 并发与性能负载测试
    suite.append({
        "test_id": "TC-PERF-01",
        "dimension": "7. 并发性能测试",
        "sub_category": "基础接口单并发时延基准",
        "test_name": "RAG 检索流水线各阶段时延基准",
        "input_prompt": "图书馆几点关门？",
        "context_history": "",
        "expected_behavior": "在本地缓存就绪状态下快速完成召回与切块比对",
        "assertion_criteria": "BGE 推理 < 30ms，TF-IDF < 150ms，总体检索与证据筛选 < 300ms"
    })
    suite.append({
        "test_id": "TC-PERF-02",
        "dimension": "7. 并发性能测试",
        "sub_category": "智能体多并发吞吐与线程池隔离",
        "test_name": "多并发请求下信号量与超时保护",
        "input_prompt": "从南大门到图书馆的路线",
        "context_history": "",
        "expected_behavior": "高负载下通过 BoundedSemaphore(8) 排队，不产生内存或线程爆炸",
        "assertion_criteria": "所有请求在 90s 超时预算内妥善返回，无服务崩溃或内存泄漏"
    })

    # 保存为统一 JSON
    out_json = EVAL_DIR / "unified_test_cases.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(suite, f, ensure_ascii=False, indent=2)

    # 保存为统一 CSV (带 BOM 便于 Excel 完美直接打开不乱码)
    out_csv = EVAL_DIR / "unified_test_cases.csv"
    fieldnames = ["test_id", "dimension", "sub_category", "test_name", "input_prompt", "context_history", "expected_behavior", "assertion_criteria"]
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(suite)

    print(f"[*] 成功构建全维度测试用例集！共收录 {len(suite)} 项规范测试用例。")
    print(f"[*] JSON 导出路径: {out_json}")
    print(f"[*] CSV 导出路径: {out_csv}")
    
    # 统计各维度分布
    dims = {}
    for s in suite:
        d = s["dimension"]
        dims[d] = dims.get(d, 0) + 1
    print("\n[用例维度分布统计]:")
    for k, v in sorted(dims.items()):
        print(f"  • {k}: {v} 条")

if __name__ == "__main__":
    build_unified_test_suite()
