# LangGraph迁移实施计划

**目标：**用LangGraph节点和条件边替换手写办事循环，保持原有应用行为。

**架构：**core/agent/runtime.py作为兼容入口，编译四节点StateGraph。core/agent/state.py定义每次运行的独立状态。现有工具、模型适配、证据函数和数据库接口继续使用。

**技术栈：**Python、LangGraph 1.2.6、Pydantic、FastAPI、现有Node路线工具。

## 1 准备与基线
- [x] 保存runtime.py、requirements.txt、README.md和相关说明的改前备份；无Git仓库不创建提交。
- [x] 执行python -m unittest discover -s tests -v和node --test tests/test_chat_ui.cjs tests/test_agent_ui.cjs，保存基线。

## 2 测试先行
- [x] 新增tests/test_agent_graph.py，验证CompiledStateGraph真实节点流、verify修正环、8步边界、截止时间、复用与并发隔离、API元数据。
- [x] 对旧实现执行python -m unittest discover -s tests -p test_agent_graph.py -v，预期缺少graph或framework导致失败。

## 3 实现
- [x] 添加langgraph>=1.2.6,<1.3依赖及AgentState TypedDict；把旧循环分为decide/tools/verify/finish真实节点。
- [x] 保留异常脱敏、证据编号、动作历史、结果格式及8次模型调用；recursion_limit按节点数留余量。
- [x] 新测试与已有agent测试通过后，执行全部回归、Node及离线执行器。

## 4 联调与交付
- [x] 用本地脚本模型响应配合真实工具验证HTTP路线、引用和session history；保存脱敏结果和由实际图导出的Mermaid结构。
- [x] 更新README及docs/AGENT_LANGGRAPH.md，写清框架版本、运行方式、节点职责、兼容边界、实际测试结果和模型联调范围。
- [x] 审查改前后差异、超时及隔离，再进行最终验证；只交付核验通过的内容。
