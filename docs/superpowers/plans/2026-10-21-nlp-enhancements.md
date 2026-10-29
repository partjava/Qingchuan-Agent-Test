# 校园问答六项 NLP 增强实施计划

**Goal:** 将意图与证据抽取、多轮指代、检索精排、用词归一化、语义分块、答案评测接入现有系统。

**Architecture:** 新增独立问句分析、证据评分模块；保留三种检索模式、地图和 API 返回字段。浏览器传递最近对话，服务端无共享会话状态。答案仅从当前召回证据生成；生成模型失败或证据校验失败时降级为原文抽取。

**Tech Stack:** Python、unittest、现有 Transformers / TF-IDF / FastAPI、原生 JavaScript。

## 实施与验收

- [x] 1. `core/query_understanding.py`：意图和主题、最长别名归一化、保守错字建议、仅对省略问句补充最近用户主题。测试奖学金截止与选课区分、主题切换、空历史、歧义。
- [x] 2. `core/document_loader.py`：按句与段落打包，长句兜底切割、保留重叠、每块携带章节上下文与稳定 section_id；BGE 缓存使用完整内容与模型指纹。测试原文覆盖、参数边界和上下文。
- [x] 3. `core/hybrid_retriever.py` / `core/evidence.py`：扩大召回、语义加权 RRF、主题与意图精排、同节重复抑制。支持可选本地交叉编码模型，无模型使用明确标记的规则精排。用相关性及事实槽位证据判定可回答，禁止用 RRF 当置信度。
- [x] 4. `core/direct_extractor.py` / `core/rag_engine.py`：从实际证据选择原句并附精确编号；未知事实拒答，冲突时间保留限定条件；删除固定事实回答路径。接入归一化、追问及安全检查。
- [x] 5. `web/app.py` / `chat.js` / `main.py`：受限历史参数、CLI 与浏览器多轮、清空上下文、问句处理和依据状态展示、正确错误响应处理。保持地图和原来的消融卡片。
- [x] 6. `eval/answer_evaluate.py` / `eval/answer_dataset.json`：多轮、别名、未知问题、具体证据与参考事实标注，输出答案事实覆盖、引用正确率、拒答准确率和逐题结果；增加命令入口与使用文档。

## 测试顺序

先编写每个模块的行为回归测试并确认失败，再实现并运行通过。运行 `python -m unittest discover -s tests -v`，真实本地 BGE 检索烟测与答案评测，`node --check web/static/js/chat.js`，FastAPI 请求验证。记录真实结果，不把旧评测描述为新结果。

当前目录没有 Git 元数据；直接修改用户指定项目，不创建提交或新仓库。六项由用户明确授权，可连续完成；无需重复审批。

## 完成记录
六项已接入API、浏览器与CLI；64项回归测试通过，43题答案级回归检查Hybrid43/43、BGE39/43、TF-IDF31/43。原有26题检索评测已重跑。浏览器实测与限制详见 docs/NLP_ENHANCEMENTS.md。
