# 校园办事智能体第一版实施计划

**Goal:** 保留普通问答，增加真实模型工具循环、证据回答、轨迹与可复现质量评测。
**Architecture:** 独立 core/agent 包；受控工具复用RAG和地图；FastAPI新路由；原聊天界面切换模式。
**Tech Stack:** Python、requests、Pydantic、SQLite、原生JS，复用Node道路算法。当前目录非Git仓库，原文件已备份到工作区report_work/agent_v1_backup，原地开发。

## 执行状态

第一版实现与验证完成。以下任务均已执行；真实模型评测因当前缺少凭证未执行，详情见 ../../AGENT_V1_VALIDATION.md。没有将离线或本地HTTP替身结果标为真实模型能力。

## 1 执行器与证据
- [x] tests/test_campus_agent.py：先验证调用—观察—结束、缺失引用、未知工具、重复动作、超时、参数错误、提示注入和无配置。
- [x] core/agent/runtime.py：注入planner/tools，以8次模型决策和90秒预算限制循环；最终文本只从已返回证据选取。
- [x] core/agent/planner.py：兼容云端chat/completions与Ollama，严格JSON动作契约，不展示思维链，不记录凭证。
- [x] 执行 `python -m unittest discover -s tests -p test_campus_agent.py -v`，确认先失败再通过。

## 2 工具与路由
- [x] core/agent/tools.py：知识查询禁用生成；地点使用地图实际ID；时间使用上海时区；路线调用scripts/agent_route.cjs。
- [x] scripts/agent_route.cjs：读取现有布局，按相同坐标比例和障碍约束调用campus-routing.js；不输出测绘距离。
- [x] 验证未知地点、不连通状态和正常路线，不以模型生成内容充当工具结果。

## 3 会话与API
- [x] core/agent/store.py：隔离保存run/session/question/result；清空以版本号防止在途请求写回已清空会话。
- [x] web/agent_api.py：新建/api/agent/chat、/api/agent/runs、/api/agent/quality；不暴露故障注入入口。
- [x] web/schemas.py复用生成配置；web/app.py注册路由并将原清空接口联动agent store。
- [x] tests/test_agent_api.py：用依赖注入验证请求约束、跨会话不读、清空、轨迹脱敏和无模型状态。

## 4 界面与评测
- [x] 新增agent.js/agent.css，原chat.js仅接入执行模式、返回轨迹和导出；index.html新增模式与质量入口。
- [x] eval/agent_evaluate.py提供离线执行器场景与显式真实模型评测，报告明确区分。
- [x] Node UI测试与浏览器检查：普通问答→智能办事→无模型提示→恢复普通模式；工具轨迹转义；桌面与移动布局。
- [x] 执行完整Python/Node回归；真实模型未配置时明确记录未完成实网联调，不声称真实模型任务准确率。

## 5 交付
- [x] README与docs/AGENT_V1.md写明运行方式、四类工具、可观测边界、模型配置与测试记录。
- [x] 检查原报告未改，备份齐全，原问答功能回归通过；更新本计划和验证记录。
