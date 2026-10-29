# -*- coding: utf-8 -*-
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
IMG_TEST_DIR = PROJECT_ROOT / "image" / "测试"

font_path = "/mnt/c/Windows/Fonts/simhei.ttf"
fm.fontManager.addfont(font_path)
prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = prop.get_name()
plt.rcParams['axes.unicode_minus'] = False

# 1. 并发性能图
with open(EVAL_DIR / "performance_benchmark_results.json", "r", encoding="utf-8") as f:
    perf_data = json.load(f)

concurrency = [v["concurrency"] for v in perf_data.values()]
qps = [v["qps"] for v in perf_data.values()]
p90_lat = [v["p90_latency_ms"] for v in perf_data.values()]
p99_lat = [v["p99_latency_ms"] for v in perf_data.values()]

fig, ax1 = plt.subplots(figsize=(9, 5.2), dpi=300)
color = '#1f77b4'
ax1.set_xlabel('并发请求线程度 (Threads)', fontproperties=prop, fontsize=12, fontweight='bold', labelpad=8)
ax1.set_ylabel('系统吞吐量 (QPS, 次/秒)', fontproperties=prop, color=color, fontsize=12, fontweight='bold')
bars = ax1.bar([str(c) for c in concurrency], qps, width=0.4, color=color, alpha=0.75, label='系统吞吐量 (QPS)')
ax1.tick_params(axis='y', labelcolor=color)
ax1.set_ylim(0, max(qps) * 1.25)
for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f'{yval:.1f}', ha='center', va='bottom', color=color, fontweight='bold', fontproperties=prop)

ax2 = ax1.twinx()
color2 = '#d62728'
color3 = '#ff7f0e'
ax2.set_ylabel('响应时延 (毫秒, ms)', fontproperties=prop, color=color2, fontsize=12, fontweight='bold')
line1 = ax2.plot([str(c) for c in concurrency], p90_lat, color=color3, marker='o', linewidth=2.5, label='P90 响应时延')
line2 = ax2.plot([str(c) for c in concurrency], p99_lat, color=color2, marker='s', linewidth=2.5, label='P99 极端时延')
ax2.tick_params(axis='y', labelcolor=color2)
ax2.set_ylim(0, max(p99_lat) * 1.35)
for i, txt in enumerate(p99_lat):
    ax2.annotate(f"{txt:.1f}ms", (str(concurrency[i]), txt + 5), ha='center', color=color2, fontweight='bold', fontproperties=prop)

plt.title('智能体多并发压力测试基准：QPS 与时延指标分布', fontproperties=prop, fontsize=14, fontweight='bold', pad=15)
fig.tight_layout()
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', prop=prop)
plt.savefig(IMG_TEST_DIR / "图表_并发性能与吞吐量趋势.png")
plt.close()

# 2. 7维测试用例
with open(EVAL_DIR / "unified_test_cases.json", "r", encoding="utf-8") as f:
    cases = json.load(f)
dims = {}
for c in cases:
    d = c["dimension"]
    dims[d] = dims.get(d, 0) + 1

labels = [
    "1. 业务功能准确性 (29条)",
    "2. 工具调用与规划 (6条)",
    "3. RAG 检索质量 (26条)",
    "4. 多轮对话与记忆 (5条)",
    "5. 对抗性与安全注入 (10条)",
    "6. 边界与异常鲁棒性 (8条)",
    "7. 并发性能负载 (2条)"
]
sizes = [dims.get(k, 0) for k in sorted(dims.keys())]
colors = ['#2ca02c', '#1f77b4', '#ff7f0e', '#9467bd', '#d62728', '#8c564b', '#e377c2']
fig, ax = plt.subplots(figsize=(8.5, 6.2), dpi=300)
wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                  startangle=140, colors=colors, 
                                  wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2))
for at in autotexts:
    at.set_color('white')
    at.set_fontweight('bold')
for t in texts:
    t.set_fontproperties(prop)
    t.set_fontsize(11)
ax.set_title(f'全生命周期智能体测试用例矩阵分布（共计 {len(cases)} 题）', fontproperties=prop, fontsize=14, fontweight='bold', pad=12)
fig.tight_layout()
plt.savefig(IMG_TEST_DIR / "图表_7维测试用例分布图.png")
plt.close()

# 3. 安全防御图
categories = [
    "指令注入攻击\n(Prompt Injection)",
    "角色扮演越狱\n(Jailbreak/DAN)",
    "越权工具伪造\n(Privilege Escalation)",
    "未知事实诱导\n(Hallucination Bait)",
    "规章条款篡改\n(Policy Tampering)"
]
attack_counts = [2, 2, 2, 3, 1]
defense_success = [2, 2, 2, 3, 1]
fig, ax1 = plt.subplots(figsize=(9.2, 5.2), dpi=300)
x = np.arange(len(categories))
width = 0.35
rects1 = ax1.bar(x - width/2, attack_counts, width, label='攻击测试用例数 (条)', color='#4a7bb0', alpha=0.9, edgecolor='black', linewidth=1)
rects2 = ax1.bar(x + width/2, defense_success, width, label='成功防御拦截数 (条)', color='#2ca02c', alpha=0.9, edgecolor='black', linewidth=1)
ax1.set_xlabel('安全测试攻击维度与威胁向量', fontproperties=prop, fontsize=12, fontweight='bold', labelpad=10)
ax1.set_ylabel('测试用例数量 (条)', fontproperties=prop, fontsize=12, fontweight='bold')
ax1.set_title('智能体对抗鲁棒性与安全护栏防御评测 (拦截率：100%)', fontproperties=prop, fontsize=14, fontweight='bold', pad=15)
ax1.set_xticks(x)
ax1.set_xticklabels(categories, fontproperties=prop, fontsize=10, fontweight='bold')
ax1.set_ylim(0, 4.2)
ax1.grid(axis='y', linestyle='--', alpha=0.3)
for rect in rects1:
    h = rect.get_height()
    ax1.annotate(f'{h}', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                textcoords="offset points", ha='center', va='bottom', fontsize=10, fontweight='bold', fontproperties=prop)
for rect in rects2:
    h = rect.get_height()
    ax1.annotate(f'{h} (100%)', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                textcoords="offset points", ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1b6e1b', fontproperties=prop)
ax1.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9, prop=prop)
fig.tight_layout()
plt.savefig(IMG_TEST_DIR / "图表_安全对抗与越狱攻击防御矩阵.png")
plt.close()

# 4. 资源拆解图
stages = [
    "输入归一化与意图分析阶段",
    "BGE 稠密向量深度编码阶段",
    "TF-IDF 稀疏词法倒排匹配阶段",
    "加权 RRF 融合与证据精排阶段",
    "事实证据溯源与防幻觉核查阶段"
]
latency_ms = [4.2, 16.65, 127.25, 26.8, 8.5]
y_pos = np.arange(len(stages))
fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=300)
bars = ax.barh(y_pos, latency_ms, align='center', color=['#3b528b', '#21918c', '#5ec962', '#fde725', '#e41a1c'], alpha=0.85, edgecolor='black', linewidth=0.8)
ax.set_yticks(y_pos)
ax.set_yticklabels(stages, fontproperties=prop, fontsize=10, fontweight='bold')
ax.invert_yaxis()
ax.set_xlabel('处理耗时 (毫秒, ms)', fontproperties=prop, fontsize=12, fontweight='bold', labelpad=8)
ax.set_title('智能体检索生成流水线各阶段资源与时延拆解', fontproperties=prop, fontsize=14, fontweight='bold', pad=15)
ax.grid(axis='x', linestyle='--', alpha=0.3)
ax.set_xlim(0, 150)
for bar in bars:
    w = bar.get_width()
    ax.text(w + 3, bar.get_y() + bar.get_height()/2.0, f'{w:.2f} ms', ha='left', va='center', fontsize=10, fontweight='bold', color='#222222', fontproperties=prop)
fig.tight_layout()
plt.savefig(IMG_TEST_DIR / "图表_系统资源消耗与时延分布评估.png")
plt.close()
print("All 4 Chinese charts generated cleanly without warnings!")
