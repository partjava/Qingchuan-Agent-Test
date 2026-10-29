# 复合问题、事实槽位、Flash接入与按钮修复

**用户授权范围：** 实现上一轮前两项（多个对象/问题拆解，实体—属性—条件解析），纠正DeepSeek V4.1 Flash API配置，修复并解释导出前面的三个检索按钮。

**Architecture:** 保留当前query作为公共入口，增加基于结构化slots的子问句规划。每个子问题独立检索、证据校验，聚合引用并重编号，返回每项是否可回答及partial状态；不把一道子题的事实代替另一道。模型接入使用官方Chat Completions、model=deepseek-flash、thinking默认disabled，无Key运行本地。按钮通过data-mode而非显示文字同步状态，明确下次提问生效，重答由单独按钮触发。

## 分工和接口

- [x] 1. 问句理解与证据（core/query_understanding.py、core/evidence.py、tests/test_fact_slots.py）：新增slots字段，结构subject、attribute、conditions；plan_subqueries(question,history=None)返回列表，每项含question、label、slots。兼容既有analyze_query。覆盖多实体同属性、多属性同实体、并列等级、多少本/册/借阅上限、读者条件，约束事实单位、等级与事件。单问返回一项，不扩增无关主题，限制最多6子项并显式处理超过上限。
- [x] 2. 引擎集成（core/rag_engine.py、web/schemas.py、web/app.py）：公共query拆解后调用单题链路，避免递归规划，合并所有子项答案、引用和evidence，重新映射编号；全拒答refused=True，部分支持partial=True；逐项标明未知而不丢失其他部分；分析信息保留用户原句。一次复合问句最多一次生成调用。
- [x] 3. DeepSeek客户端与契约测试（core/deepseek_client.py、tests/test_deepseek_client.py）：官方URL固定，默认deepseek-flash，显式thinking disabled；只读取最终content；处理空/截断结果、401/402/404/429/5xx、超时与非JSON；不记录Key/原始错误体；失败回退并返回可见但无敏感内容的原因。未接入用户真实Key，不做付费连通测试。
- [x] 4. 前端（web/static/js/chat.js、web/templates/index.html、web/static/css/chat.css、tests/test_chat_ui.cjs）：data-mode、aria-pressed、高亮、作用说明和重答上一题；模型默认Flash，移除旧V3/R1显示与选择，安全迁移旧浏览器配置，思考开关默认关闭。发送thinking字段。明确保存配置不等于连通成功。显示复合问句分析与各项状态。保留地图和导出。
- [x] 5. 回归与真实验证：测试先失败再实现；原有64测试及43题回归不退化，新增复合/改写样例；启动本地8016服务，浏览器实际点击三模式并核对请求mode、选中样式，重答与Flash配置模拟请求，无真实Key调用；更新说明与结果。

## API补充约定

query(user_question,...,history=None,allow_generation=True,thinking=False)。ChatRequest新增thinking:bool=False。复合返回sub_answers:[{question,label,slots,answer,refused,clarification,citation_indices}]、partial:bool，query_analysis.subqueries字段便于展示。原有单题返回字段保持兼容。

官方依据： https://api-docs.deepseek.com/updates/ （V4.1 Flash模型名deepseek-flash）；https://api-docs.deepseek.com/guides/thinking_mode/ （thinking.type=enabled/disabled）。当前目录无Git元数据，直接修改用户指定项目，不创建仓库。

## 验收结果
104项Python回归、9项Node回归通过。原有43题Hybrid43/43，新增12题复合/变式Hybrid12/12。桌面与窄屏浏览器交互已验证；真实DeepSeek Key/余额/网络生成未测试，仅模拟官方接口契约与错误回退。
