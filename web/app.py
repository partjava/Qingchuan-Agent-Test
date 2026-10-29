# -*- coding: utf-8 -*-

"""

晴川 RAG 智能问答与 3D 校园地图系统 Web 服务 (FastAPI)

提供统一 RESTful API 与分屏交互 Web UI

支持 DeepSeek V4.1 Flash 官方 API、本地证据抽取与校园知识库

"""



import os

import sys

import json

from pathlib import Path

from typing import Optional

from fastapi import FastAPI, HTTPException

from fastapi.staticfiles import StaticFiles

from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel



# 确保核心模块在路径中

CURRENT_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = CURRENT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))



from core.document_loader import load_and_chunk_documents

from core.tfidf_retriever import TfidfRetriever

from core.bge_retriever import BgeSemanticRetriever

from core.hybrid_retriever import HybridRetriever

from core.rag_engine import QingchuanRagEngine

from crawler.full_crawler import QingchuanFullCrawler

import time

from web.schemas import ChatRequest

from core.db_manager import init_db, log_chat_turn, get_recent_history, clear_chat_history
from core.agent.store import AgentStore
from web.agent_api import create_agent_router



app = FastAPI(

    title="晴川 RAG 智能问答系统",

    description="结合 3D 校园沙盘、多维校本知识库、TF-IDF与BGE双引擎检索及自主智能体的智能体测试比赛系统",

    version="2.0.0"

)



# 允许跨域

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)



# 禁用静态文件强缓存，保证前端与地图脚本改动即时生效

@app.middleware("http")

async def add_no_cache_headers(request, call_next):

    response = await call_next(request)

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    response.headers["Pragma"] = "no-cache"

    response.headers["Expires"] = "0"

    return response



# 静态资源挂载 (包含 3D 校园地图与配图)

STATIC_DIR = CURRENT_DIR / "static"

IMAGES_DIR = PROJECT_ROOT / "data" / "images"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)



app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")



@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(STATIC_DIR / 'favicon.svg', media_type='image/svg+xml')


# 全局模型与检索器单例
print("[2/4] 正在加载并切分校本规章知识库 (data/docs)...")
init_db()
DOCS_DIR = PROJECT_ROOT / "data" / "docs"
chunks = load_and_chunk_documents(DOCS_DIR)
print(f"[*] 知识库加载完成，共切分 {len(chunks)} 个语义文本块！")

print("[3/4] 正在初始化检索引擎与 LangGraph 状态图架构...")
print("  - [3a] 正在拟合 TF-IDF 稀疏特征矩阵...")
tfidf_retriever = TfidfRetriever(chunks)
print("  - [3b] 正在装配 BGE 向量模型与校验向量缓存...")
bge_retriever = BgeSemanticRetriever(chunks)
hybrid_retriever = HybridRetriever(tfidf_retriever, bge_retriever)
rag_engine = QingchuanRagEngine(tfidf_retriever, bge_retriever, hybrid_retriever)

print("  - [3c] 正在初始化 LangGraph 状态机与只读工具沙箱路由...")
agent_store = AgentStore()
app.include_router(create_agent_router(lambda: rag_engine, store=agent_store))
print("[OK] 全链路组件加载就绪！")





@app.get("/", response_class=HTMLResponse)

def index():

    template_path = CURRENT_DIR / "templates" / "index.html"

    content = template_path.read_text(encoding="utf-8")
    content = content.replace("{{KB_TOTAL_CHUNKS}}", f"{len(chunks):,}")
    return HTMLResponse(content=content)





@app.post("/api/chat")

def chat(req: ChatRequest):

    if not req.question or not req.question.strip():

        raise HTTPException(status_code=400, detail="问题不能为空")

    

    start_t = time.perf_counter()

    try:

        res = rag_engine.query(

            user_question=req.question.strip(),

            mode=req.mode,

            top_k=req.top_k,

            use_ollama=req.use_ollama,

            deepseek_key=req.deepseek_key,

            model=req.model,

            history=[turn.model_dump() for turn in req.history],

            thinking=req.thinking,

            api_url=req.api_url,

            ollama_url=req.ollama_url,

            ollama_model=req.ollama_model

        )

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    

    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 1)

    try:

        log_chat_turn(

            user_query=req.question.strip(),

            rewritten_query=res.get("query_analysis", {}).get("rewritten_query"),

            mode=req.mode,

            answer=res.get("answer", ""),

            llm_provider=res.get("llm_provider", ""),

            latency_ms=elapsed_ms,

            refused=bool(res.get("refused", False)),

            citations=res.get("citations", []),

            session_id=(req.session_id or "web_session").strip()

        )

    except Exception as log_err:

        print(f"[SQLite] 日志记录异常: {log_err}")

    

    return JSONResponse(content=res)





@app.get("/api/history")

def get_history(limit: int = 50, session_id: Optional[str] = None):

    """从 SQLite 数据库获取最近问答历史与审计日志"""

    records = get_recent_history(limit=limit, session_id=session_id)

    return JSONResponse(content={"total": len(records), "history": records})





@app.delete("/api/history")

def clear_history(session_id: Optional[str] = None):

    """清空 SQLite 数据库中的问答历史"""

    deleted = clear_chat_history(session_id=session_id)
    agent_store.clear(session_id)

    return JSONResponse(content={"status": "success", "deleted_count": deleted})





@app.get("/api/kb_stats")

def get_kb_stats():

    """获取本地知识库统计指标"""

    raw_dir = PROJECT_ROOT / "data" / "raw_crawled"

    stats = {

        "total_chunks": len(chunks),

        "docs_dir": str(DOCS_DIR),

        "channels": {}

    }

    

    # 统计四大频道

    for ch, name in [("xxyw", "学校要闻"), ("tzgg", "通知公告"), ("jyjx", "教育教学"), ("mtgz", "媒体关注")]:

        jpath = raw_dir / f"{ch}.json"

        ch_img_dir = IMAGES_DIR / ch

        art_count = 0

        if jpath.exists():

            try:

                with open(jpath, "r", encoding="utf-8") as f:

                    art_count = len(json.load(f))

            except Exception:

                pass

        img_count = len(list(ch_img_dir.glob("*.*"))) if ch_img_dir.exists() else 0

        stats["channels"][ch] = {

            "name": name,

            "articles": art_count,

            "images": img_count

        }



    # 办公电话统计

    cpath = raw_dir / "office_contacts.json"

    contact_count = 0

    if cpath.exists():

        try:

            with open(cpath, "r", encoding="utf-8") as f:

                contact_count = len(json.load(f))

        except Exception:

            pass

    stats["channels"]["office_contacts"] = {

        "name": "各单位办公电话黄页",

        "departments": contact_count

    }



    return JSONResponse(content={"status": "ok", "stats": stats})





@app.get("/api/benchmark")

def get_benchmark():

    eval_json = PROJECT_ROOT / "eval" / "eval_results.json"

    if eval_json.exists():

        with open(eval_json, "r", encoding="utf-8") as f:

            data = json.load(f)

        return JSONResponse(content={"status": "ok", "data": data})

    return JSONResponse(content={"status": "empty", "data": []})





@app.post("/api/sync_news")

def sync_news():

    """触发全量增量爬虫并在线热重载知识库"""

    global chunks, tfidf_retriever, bge_retriever, hybrid_retriever, rag_engine

    try:

        crawler = QingchuanFullCrawler(timeout=10, max_workers=6)

        summary = crawler.crawl_all(max_pages=2, download_images=True)

        

        # 重新热载入与建库

        chunks = load_and_chunk_documents(DOCS_DIR)

        tfidf_retriever = TfidfRetriever(chunks)

        bge_retriever = BgeSemanticRetriever(chunks)

        hybrid_retriever = HybridRetriever(tfidf_retriever, bge_retriever)

        rag_engine = QingchuanRagEngine(tfidf_retriever, bge_retriever, hybrid_retriever)

        

        return JSONResponse(content={

            "status": "ok", 

            "message": f"成功同步官方资讯并重新索引！知识库扩充至 {len(chunks)} 个语义块。",

            "summary": summary

        })

    except Exception as e:

        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})





@app.get('/api/answer_benchmark')

def get_answer_benchmark():

    """只读取已完成的答案评测，不在网页请求中启动模型评测。"""

    report_path = PROJECT_ROOT / 'eval' / 'answer_eval_results.json'

    if not report_path.exists():

        return {'status': 'empty', 'data': {}}

    try:

        reports = json.loads(report_path.read_text(encoding='utf-8'))

    except (OSError, ValueError):

        return {'status': 'unavailable', 'data': {}}

    fields = ('total_cases', 'passed_count', 'answerable_count', 'unknown_count', 'clarification_count',

              'expected_answer_accuracy', 'unknown_refusal_accuracy', 'clarification_accuracy')

    return {'status': 'ok', 'data': {mode: {key: report.get(key) for key in fields}

                                    for mode, report in reports.items()}}





if __name__ == "__main__":

    import uvicorn

    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=False)





class TestKeyRequest(BaseModel):

    api_key: str

    model: Optional[str] = "deepseek-flash"

    api_url: Optional[str] = "https://api.deepseek.com"





@app.post("/api/test_deepseek")

def test_deepseek(req: TestKeyRequest):

    """验证用户填写的云端 API (DeepSeek 或兼容 OpenAI 协议端点) 连通性与模型响应"""

    key = req.api_key.strip()

    if not key:

        return JSONResponse(content={"ok": False, "message": "API Key 不能为空"}, status_code=400)



    endpoint = (req.api_url or "https://api.deepseek.com").strip()

    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):

        endpoint = "https://" + endpoint

    if not endpoint.endswith("/chat/completions"):

        endpoint = endpoint.rstrip("/") + "/chat/completions"



    model_name = (req.model or "deepseek-flash").strip()

    import requests

    start_t = time.perf_counter()

    try:

        resp = requests.post(

            endpoint,

            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},

            json={

                "model": model_name,

                "messages": [{"role": "user", "content": "hi"}],

                "max_tokens": 5,

                "stream": False

            },

            timeout=10

        )

        latency = round((time.perf_counter() - start_t) * 1000)

        if resp.status_code == 200:

            return JSONResponse(content={"ok": True, "message": f"连接成功！端点响应正常，耗时 {latency}ms。"})

        elif resp.status_code == 401:

            return JSONResponse(content={"ok": False, "message": "认证失败：API Key 无效或过期 (HTTP 401)"})

        elif resp.status_code == 402:

            return JSONResponse(content={"ok": False, "message": "账户余额不足，请充值后使用 (HTTP 402)"})

        elif resp.status_code == 404:

            return JSONResponse(content={"ok": False, "message": f"端点或模型不存在 (HTTP 404，模型: {model_name})"})

        elif resp.status_code == 429:

            return JSONResponse(content={"ok": False, "message": "请求频率超限，请稍后重试 (HTTP 429)"})

        else:

            return JSONResponse(content={"ok": False, "message": f"API 端点返回状态码: {resp.status_code}"})

    except requests.Timeout:

        return JSONResponse(content={"ok": False, "message": "请求超时（10秒），请检查网络连接或 API URL 是否可达"})

    except requests.RequestException as e:

        return JSONResponse(content={"ok": False, "message": f"网络通信失败: {str(e)[:80]}"})





class TestOllamaRequest(BaseModel):

    ollama_url: Optional[str] = "http://localhost:11434"

    model: Optional[str] = "deepseek-r1:latest"





@app.post("/api/test_ollama")

def test_ollama(req: TestOllamaRequest):

    """测试本地 Ollama 服务连通性与模型可用性"""

    base_url = (req.ollama_url or "http://localhost:11434").strip()

    if not base_url.startswith("http://") and not base_url.startswith("https://"):

        base_url = "http://" + base_url

    base_url = base_url.rstrip("/")



    import requests

    start_t = time.perf_counter()

    try:

        tags_resp = requests.get(f"{base_url}/api/tags", timeout=5)

        if tags_resp.status_code != 200:

            return JSONResponse(content={"ok": False, "message": f"Ollama 服务返回状态码 {tags_resp.status_code}，服务异常"})



        tags_data = tags_resp.json()

        models = [m.get("name") for m in tags_data.get("models", []) if m.get("name")]



        target_model = (req.model or "deepseek-r1:latest").strip()

        found = any(target_model in m or m.startswith(target_model.split(':')[0]) for m in models)

        latency = round((time.perf_counter() - start_t) * 1000)



        if found:

            return JSONResponse(content={

                "ok": True,

                "message": f"连接成功！Ollama 服务正常（耗时 {latency}ms），已检测到模型【{target_model}】。",

                "models": models

            })

        else:

            models_str = ", ".join(models[:5]) if models else "暂无模型"

            return JSONResponse(content={

                "ok": False,

                "message": f"Ollama 正在运行，但未找到模型【{target_model}】。本地已安装模型: [{models_str}]。请在命令行运行 `ollama pull {target_model}`。",

                "models": models

            })

    except requests.ConnectionError:

        return JSONResponse(content={"ok": False, "message": f"无法连接到本地 Ollama ({base_url})。请确认 Ollama 已启动（运行 ollama serve）。"})

    except requests.Timeout:

        return JSONResponse(content={"ok": False, "message": "连接 Ollama 超时（5秒），请检查服务状态"})

    except Exception as e:

        return JSONResponse(content={"ok": False, "message": f"连接异常: {str(e)[:80]}"})

