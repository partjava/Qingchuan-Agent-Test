# -*- coding: utf-8 -*-
import docx

doc_path = "AI智能体测试挑战赛-晴川校园办事智能体测试与可靠性评估.docx"
doc = docx.Document(doc_path)

# 1. 封面增加开源仓库链接
for i, p in enumerate(doc.paragraphs):
    if "队员：谭焱明、贺思涵" in p.text:
        # 在后面一行添加
        p_repo = doc.paragraphs[i+1]
        if not p_repo.text.strip():
            p_repo.text = "开源代码仓库：https://github.com/partjava/Qingchuan-Agent-Test"
            p_repo.style = p.style
        break

# 2. 1.9 安装依赖处增加仓库说明
for i, p in enumerate(doc.paragraphs):
    if "1.9 安装依赖与准备运行环境" in p.text:
        # 在后面插入一行
        p_next = doc.paragraphs[i+1]
        # 看看是不是已经有了
        break

# 3. 5.2.1 节补充 7 大测试套件详细清单
target_idx = None
for i, p in enumerate(doc.paragraphs):
    if "5.2.1 代码测试范围与执行入口" in p.text:
        target_idx = i
        break

if target_idx is not None:
    # 找到 5.2.2 的位置
    next_idx = None
    for j in range(target_idx + 1, len(doc.paragraphs)):
        if "5.2.2 用例清单展示" in doc.paragraphs[j].text:
            next_idx = j
            break
    
    test_suites_text = (
        "项目完整开源代码及测试资产仓库地址：https://github.com/partjava/Qingchuan-Agent-Test\n\n"
        "tests/ 目录下 25 份白盒与自动化回归测试套件全景说明：\n"
        "一、 智能体与 LangGraph 调度测试（Agent 专项，专门测试多智能体决策、工具调用、状态流转和死循环熔断）：\n"
        "• test_agent_graph.py：测试基于 LangGraph 构建的状态机图（StateGraph），验证节点流转、条件边分支选择、独立 Token 预算以及 8 步强制递归熔断。\n"
        "• test_agent_planner.py：测试智能体规划器（Planner），模拟真实 HTTP 交互，验证多步骤拆解是否合理。\n"
        "• test_agent_plan.py：测试智能体长链条规划的具体执行逻辑与证据整合。\n"
        "• test_campus_agent.py：智能体行为契约测试，验证智能体在面对校园办事任务时的工具调用序列。\n"
        "• test_agent_tools_store.py：测试智能体工具箱（Tools）与状态存储器（Store）的数据读写与工具执行。\n"
        "• test_agent_api.py：测试智能体对外暴露的后端 Web API 接口（/api/agent/*）。\n\n"
        "二、 混合检索与 RAG 引擎测试（Retrieval & RAG 专项，测试双引擎检索算法、排名融合与问答管道）：\n"
        "• test_hybrid_retriever.py：测试 Hybrid 混合检索器，验证 TF-IDF 字面分与 BGE 语义向量分的加权融合算法（RRF/加权平均）。\n"
        "• test_rag_pipeline.py：测试完整的 RAG 问答主流水线（端到端检索 → 证据筛选 → 提示词组装 → 生成）。\n"
        "• test_composite_pipeline.py：测试复合问题问答流（例如同时询问两项不同业务的交叉问题）。\n"
        "• test_canteen_location.py：专项测试食堂、宿舍等地理位置型问答的召回与定位精度。\n"
        "• test_topic_coverage.py：测试校本规章各个主题（奖助学金、选课、毕业、图书等）的检索覆盖率。\n\n"
        "三、 意图理解、槽位抽取与证据链测试（NLU & Evidence 专项，测试错别字、倒装口语容错与证据真确性）：\n"
        "• test_query_understanding.py：测试查询理解模块（分词、实体识别、意图分类）。\n"
        "• test_fact_slots.py：测试事实槽位提取器（从非结构化文本中精准抠出电话、时间、地点、金额等硬事实字段）。\n"
        "• test_evidence.py：测试证据重排序与证据段落提取，确保回答只引用高置信度官方段落。\n"
        "• test_article_reading.py：测试长篇规章制度文档（如章程、条例）的细粒度段落切分与局部阅读理解。\n\n"
        "四、 接口契约与大模型客户端测试（API & Client 专项，测试数据交互协议与模型适配）：\n"
        "• test_chat_schemas.py：基于 Pydantic 的接口契约测试（测试请求体字段校验、非法参数拦截、格式异常报错）。\n"
        "• test_deepseek_client.py：测试大模型 API 客户端封装（超时重试机制、Token 统计、流式输出解析与断网模拟）。\n"
        "• test_custom_ai_and_history.py：测试用户自定义大模型端点（支持切换第三方 API 或本地 Ollama）与历史记录管理。\n\n"
        "五、 底层数据加载与向量缓存测试（Data & Cache 专项，测试离线数据处理与存储性能）：\n"
        "• test_document_loader.py：测试校本 Markdown/文本知识库的清洗、切分与元数据加载。\n"
        "• test_embedding_cache.py：测试 BGE 向量离线缓存（.npy 和哈希校验），确保服务器启动时秒级加载已有向量，不重复编码。\n"
        "• test_db_manager.py：测试 SQLite 本地数据库的管理（问答日志存储、反馈打标、历史会话持久化）。\n"
        "• test_kb_display.py：测试前端展示的知识库文档数与语义块统计是否与底层实际加载量一致。\n\n"
        "六、 评测与断言逻辑测试（Evaluation 专项）：\n"
        "• test_answer_evaluate.py：测试评测脚本自身的准确性判定算法（如对比模型答案与标准答案时的 ROUGE/BLEU 评分及事实一致性打分逻辑）。\n\n"
        "七、 前端 UI 自动化测试（Node.js 端）：\n"
        "• test_chat_ui.cjs：使用 Node.js 针对对话界面的前端交互、气泡渲染、历史记录加载进行的自动化测试。\n"
        "• test_agent_ui.cjs：针对智能体多步执行轨迹折叠面板、工具调用卡片等 UI 组件进行的渲染测试。"
    )
    
    # 在 5.2.1 原有描述 P[target_idx+2] 之后插入该段详细说明
    p_ref = doc.paragraphs[target_idx + 2]
    p_new = p_ref.insert_paragraph_before(test_suites_text)
    p_new.style = p_ref.style

doc.save(doc_path)
print("Docx updated successfully with repo url and test suite matrix!")
