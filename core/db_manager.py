# -*- coding: utf-8 -*-
"""
晴川 RAG 智能问答系统 SQLite 持久化数据库管理模块
负责记录问答交互日志、多轮对话轨迹、检索模式与耗时审计
零第三方依赖，单文件保存在 data/qinchuan_rag.db
"""

from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "qinchuan_rag.db"


@contextmanager
def get_db_connection(db_path: Optional[Path | str] = None) -> Iterator[sqlite3.Connection]:
    """获取 SQLite 数据库连接上下文管理器，自动提交/关闭，启用 WAL 模式与字典行映射"""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式以支持高并发读写，保持低延迟
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Optional[Path | str] = None) -> None:
    """初始化数据库表与索引结构"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_query TEXT NOT NULL,
                rewritten_query TEXT,
                mode TEXT NOT NULL,
                answer TEXT NOT NULL,
                llm_provider TEXT,
                latency_ms REAL,
                refused INTEGER DEFAULT 0,
                citations_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_history(created_at);")
        conn.commit()


def log_chat_turn(
    user_query: str,
    rewritten_query: Optional[str] = None,
    mode: str = "hybrid",
    answer: str = "",
    llm_provider: Optional[str] = None,
    latency_ms: float = 0.0,
    refused: bool = False,
    citations: Optional[List[Dict[str, Any]]] = None,
    session_id: str = "default",
    db_path: Optional[Path | str] = None
) -> int:
    """写入一条问答交互日志，返回新增记录的自增 ID"""
    citations_json = json.dumps(citations or [], ensure_ascii=False)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_history (
                session_id, user_query, rewritten_query, mode, answer,
                llm_provider, latency_ms, refused, citations_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            str(session_id or "default"),
            str(user_query or ""),
            str(rewritten_query or user_query or ""),
            str(mode or "hybrid"),
            str(answer or ""),
            str(llm_provider or "本地事实证据抽取"),
            float(latency_ms or 0.0),
            1 if refused else 0,
            citations_json
        ))
        conn.commit()
        return cursor.lastrowid or 0


def get_recent_history(
    limit: int = 50,
    session_id: Optional[str] = None,
    db_path: Optional[Path | str] = None
) -> List[Dict[str, Any]]:
    """查询最近的问答历史记录列表（按时间倒序），并包含每条消息在其所属会话窗口内的轮次序号 turn_index"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute("""
                SELECT *, ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY id ASC) AS turn_index
                FROM chat_history
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?;
            """, (session_id, max(1, min(limit, 200))))
        else:
            cursor.execute("""
                WITH ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY id ASC) AS turn_index
                    FROM chat_history
                )
                SELECT * FROM ranked
                ORDER BY id DESC LIMIT ?;
            """, (max(1, min(limit, 200)),))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def clear_chat_history(
    session_id: Optional[str] = None,
    db_path: Optional[Path | str] = None
) -> int:
    """清空问答历史记录，可指定特定 session_id，重置自增 ID 序列并返回删除记录数"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute("DELETE FROM chat_history WHERE session_id = ?;", (session_id,))
            deleted = cursor.rowcount
            cursor.execute("SELECT COUNT(*) FROM chat_history;")
            if cursor.fetchone()[0] == 0:
                try:
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'chat_history';")
                except Exception:
                    pass
        else:
            cursor.execute("DELETE FROM chat_history;")
            deleted = cursor.rowcount
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'chat_history';")
            except Exception:
                pass
        conn.commit()
        return deleted
