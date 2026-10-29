# LangGraph校园办事流程迁移设计

用户已确认接入LangGraph，并保留现有页面、工具、接口、会话、超时和执行轨迹。项目无Git仓库，直接修改原目录，改前代码备份至report_work/langgraph_migration_backup。

## 范围与方案

采用LangGraph StateGraph实际编排，而非包装一个仍然运行旧循环的节点。四个节点分别负责decide（模型决策与预算检查）、tools（白名单执行与观察）、verify（方案核验与修正反馈）、finish（安全结果组装）。条件边支持工具后再决策、无效输出重试、核验失败重试，以及澄清、异常、预算停止。

沿用JsonPlanner、CampusTools、动作Pydantic契约、证据检查、AgentStore和/api/agent/chat。普通RAG不改，页面不改。run(question, history)保持原调用方式和返回字段，新增agent.framework、framework_version、graph_nodes用于识别框架与节点执行路径。

## 边界与隔离

每次调用创建独立状态，模型和工具仍由bounded_call限制等待时间及在途数量。8次限制只统计模型决策，LangGraph节点调度次数单独设置更大的recursion_limit。最终一次工具或无效动作完成后必须进入finish，不能消耗第9次模型调用。没有checkpointer，不以框架内存替代现有服务端会话；历史来源和清空版本控制保持原样。不启用外部跟踪服务。

## 验收

先证明新增框架测试在旧实现失败，再迁移实现。验证实际CompiledStateGraph、节点流、修正环、拒绝路径、8次决策边界、短超时、串行复用与并发隔离及HTTP兼容。运行全部Python、Node和14项离线执行器；通过本地脚本模型HTTP服务联调真实知识/地点/路线工具。该联调验证协议和接线，不作为真实模型准确率。记录依赖版本、日志和框架结构图。

## 不包含

不修复既有安全/性能模拟评测脚本，不修改学校资料，不改写旧截图为新证据，不自动调用付费模型。不在缺少真实模型配置时虚构在线成绩。
