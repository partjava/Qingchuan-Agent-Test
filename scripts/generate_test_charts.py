# -*- coding: utf-8 -*-
"""
生成智能体质量保障与性能压测科研级图表
输出：
1. image/测试/图表_并发性能与吞吐量趋势.png
2. image/测试/图表_7维测试用例分布与安全拦截矩阵.png
"""

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 配置通用字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
IMG_TEST_DIR = PROJECT_ROOT / "image" / "测试"

# 1. 绘制并发性能图
perf_path = EVAL_DIR / "performance_benchmark_results.json"
if perf_path.exists():
    with open(perf_path, "r", encoding="utf-8") as f:
        perf_data = json.load(f)
    
    concurrency = [v["concurrency"] for v in perf_data.values()]
    qps = [v["qps"] for v in perf_data.values()]
    avg_lat = [v["avg_latency_ms"] for v in perf_data.values()]
    p90_lat = [v["p90_latency_ms"] for v in perf_data.values()]
    p99_lat = [v["p99_latency_ms"] for v in perf_data.values()]
    
    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=200)
    
    # 柱状图：QPS
    color = '#1f77b4'
    ax1.set_xlabel('Concurrency Level (Threads)', fontsize=12, fontweight='bold', labelpad=8)
    ax1.set_ylabel('Throughput (QPS, req/sec)', color=color, fontsize=12, fontweight='bold')
    bars = ax1.bar([str(c) for c in concurrency], qps, width=0.4, color=color, alpha=0.75, label='Throughput (QPS)')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_ylim(0, max(qps) * 1.25)
    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f'{yval:.1f}', ha='center', va='bottom', color=color, fontweight='bold')

    # 折线图：P90 / P99 延迟
    ax2 = ax1.twinx()
    color2 = '#d62728'
    color3 = '#ff7f0e'
    ax2.set_ylabel('Latency (ms)', color=color2, fontsize=12, fontweight='bold')
    line1 = ax2.plot([str(c) for c in concurrency], p90_lat, color=color3, marker='o', linewidth=2.5, label='P90 Latency')
    line2 = ax2.plot([str(c) for c in concurrency], p99_lat, color=color2, marker='s', linewidth=2.5, label='P99 Latency')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim(0, max(p99_lat) * 1.35)
    for i, txt in enumerate(p99_lat):
        ax2.annotate(f"{txt:.1f}ms", (str(concurrency[i]), txt + 5), ha='center', color=color2, fontweight='bold')

    plt.title('Agent Concurrency Stress Benchmark: QPS & Latency Distribution', fontsize=14, fontweight='bold', pad=15)
    fig.tight_layout()
    
    # 合并图例
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
    
    out1 = IMG_TEST_DIR / "图表_并发性能与吞吐量趋势.png"
    plt.savefig(out1)
    plt.close()
    print(f"[✔] 成功生成并发性能图表: {out1}")

# 2. 绘制测试用例 7 维分布图
case_path = EVAL_DIR / "unified_test_cases.json"
if case_path.exists():
    with open(case_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    
    dims = {}
    for c in cases:
        d = c["dimension"]
        dims[d] = dims.get(d, 0) + 1
        
    labels = [
        "1. Functional (29)",
        "2. Tool & Plan (6)",
        "3. RAG Quality (26)",
        "4. Multi-turn (5)",
        "5. Adversarial (10)",
        "6. Boundary (8)",
        "7. Performance (2)"
    ]
    sizes = [dims.get(k, 0) for k in sorted(dims.keys())]
    colors = ['#2ca02c', '#1f77b4', '#ff7f0e', '#9467bd', '#d62728', '#8c564b', '#e377c2']
    
    fig, ax = plt.subplots(figsize=(8, 6), dpi=200)
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                      startangle=140, colors=colors, 
                                      wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2))
    
    for at in autotexts:
        at.set_color('white')
        at.set_fontweight('bold')
    for t in texts:
        t.set_fontsize(11)
        
    ax.set_title(f'Quality Assurance Test Matrix Distribution (Total: {len(cases)} Cases)', fontsize=14, fontweight='bold', pad=12)
    fig.tight_layout()
    
    out2 = IMG_TEST_DIR / "图表_7维测试用例分布图.png"
    plt.savefig(out2)
    plt.close()
    print(f"[✔] 成功生成测试用例分布图表: {out2}")
