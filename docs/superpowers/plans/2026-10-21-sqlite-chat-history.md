# SQLite 对话历史与审计日志持久化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 Python 原生 `sqlite3` 为系统构建轻量级单文件持久化数据库（`data/qinchuan_rag.db`），自动记录用户提问、检索内核、回答出处、模型提供方和端到端延迟，并提供查询与清理接口。

**Architecture:** 
- 数据层：使用 Python 原生 `sqlite3` 创建 `data/qinchuan_rag.db`，建立 `chat_history` 表并启用 WAL 模式；
- 模块封装：在 `core/db_manager.py` 中封装连接管理、表初始化、问答日志写入、分页查询与历史清理函数；
- 服务集成：在 `web/app.py` 中启动时自动初始化数据库，在 `/api/chat` 完成回答后自动入库，并暴露 `GET /api/history` 与 `DELETE /api/history` RESTful 接口；
- 自动化测试：新增 `tests/test_db_manager.py` 进行独立单元测试，并回归现有 104 项测试与前端用例。

**Tech Stack:** Python 3 原生 `sqlite3`、FastAPI、Uvicorn、Unittest。

---

### Task 1: 编写 SQLite 数据库管理模块及单元测试

**Files:**
- Create: `last/qinchuan_rag/core/db_manager.py`
- Create: `last/qinchuan_rag/tests/test_db_manager.py`

- [x] **Step 1: 编写失败的数据库单元测试**
在 `last/qinchuan_rag/tests/test_db_manager.py` 中编写对数据库创建、记录写入、读取、删除等功能的测试。

- [x] **Step 2: 运行测试验证失败（模块尚未实现）**
运行 `python -m unittest tests/test_db_manager.py`，确认测试按预期失败（ImportError）。

- [x] **Step 3: 编写 `core/db_manager.py` 完整实现**
实现 `get_db_connection`、`init_db`、`log_chat_turn`、`get_recent_history`、`clear_chat_history`。

- [x] **Step 4: 运行测试验证全部通过**
运行 `python -m unittest tests/test_db_manager.py`，确认所有测试通过。

---

### Task 2: 集成到 Web 服务与接口端点

**Files:**
- Modify: `last/qinchuan_rag/web/app.py`
- Test: `last/qinchuan_rag/tests/test_db_manager.py`

- [x] **Step 1: 在 `web/app.py` 启动流程中集成 `init_db()`**
系统初始化时自动建表并就绪。

- [x] **Step 2: 在 `/api/chat` 请求处理中自动记录对话日志**
当收到 `/api/chat` 请求并计算出问答结果后，记录原始问题、改写问题、检索模式、回答正文、实际提供方、耗时及引用出处入库。

- [x] **Step 3: 新增 `GET /api/history` 与 `DELETE /api/history` 路由**
支持拉取最近 50 条持久化历史与清空接口。

- [x] **Step 4: 运行自动化回归测试**
运行全体单元测试与前端用例，确保全部 100% 通过。

---

### Task 3: 启动服务与端到端验证

**Files:**
- Verify: `http://127.0.0.1:8000/api/history`
- Verify: `last/qinchuan_rag/data/qinchuan_rag.db`

- [x] **Step 1: 运行提问并检查数据库文件是否正常生成并写入记录**
发起问答请求，验证 `data/qinchuan_rag.db` 文件生成且数据字段完整。

- [x] **Step 2: 验证 `/api/history` 返回结构正确**
GET `/api/history` 确认能成功获取到刚提问的历史数据。
