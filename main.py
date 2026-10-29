# -*- coding: utf-8 -*-
"""
晴川 RAG 智能问答系统 - 统一控制台入口
支持命令行交互 (CLI)、Web 可视化服务启动、自动化评测与官网新闻爬取
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_cli():
    from core.document_loader import load_and_chunk_documents
    from core.tfidf_retriever import TfidfRetriever
    from core.bge_retriever import BgeSemanticRetriever
    from core.hybrid_retriever import HybridRetriever
    from core.rag_engine import QingchuanRagEngine

    print("=" * 65)
    print("晴川 校园 RAG 智能问答系统 (命令行交互模式)")
    print("=" * 65)
    docs_dir = PROJECT_ROOT / "data" / "docs"
    print(f"[*] 正在加载知识库: {docs_dir}")
    chunks = load_and_chunk_documents(docs_dir)
    print("[*] 正在构建 TF-IDF 倒排索引基线...")
    tfidf = TfidfRetriever(chunks)
    print("[*] 正在加载 BGE 稠密向量索引核心...")
    bge = BgeSemanticRetriever(chunks)
    hybrid = HybridRetriever(tfidf, bge)
    engine = QingchuanRagEngine(tfidf, bge, hybrid)

    print("\n[OK] 系统就绪！输入你的问题（输入 'exit' 或 'quit' 退出）：")
    history = []
    while True:
        try:
            q = input("\n[晴川学生咨询] > ").strip()
            if not q:
                continue
            if q.lower() in ["exit", "quit", "q"]:
                print("感谢使用，再见！")
                break
            if q.lower() in ('clear', '/clear'):
                history.clear()
                print('对话上下文已清空。')
                continue

            res = engine.query(q, mode="hybrid", top_k=3, history=history[-12:])
            if not res.get('refused') and not res.get('clarification'):
                history.append({'role': 'user', 'content': res['query_analysis']['rewritten_query'][:1000]})
            print("\n" + "-" * 50)
            print(f"[晴川问答助手]：\n{res['answer']}")
            if res.get("target_landmark"):
                print(f"[3D 地图关联]：已锁定地标 -> {res['target_landmark']['trigger']}")
            if res.get("citations"):
                print("[参考依据]：")
                for c in res["citations"]:
                    print(f"   [{c['index']}] 《{c['source']} · {c['title']}》")
            print("-" * 50)
        except (KeyboardInterrupt, EOFError):
            print("\n退出程序。")
            break


def run_web(host: str = "127.0.0.1", port: int = 8000):
    print("\n" + "=" * 65)
    print("  晴川 校园办事智能体与 RAG 系统 (Web 服务)")
    print("=" * 65)
    print("[1/4] 正在加载 Python 深度学习运行时与核心依赖...")
    print("  - [1a] 正在载入 PyTorch 运算引擎与底层动态库...")
    try:
        import torch
    except ImportError:
        pass
    print("  - [1b] 正在载入 Transformers 预训练语言模型库...")
    try:
        import transformers
    except ImportError:
        pass
    print("  - [1c] 正在载入 LangGraph 状态图与 Web 核心模块...")
    import uvicorn
    from web.app import app
    print(f"\n[4/4] 服务初始化完成！请在浏览器中打开: http://{host}:{port}")
    print("=" * 65 + "\n")
    uvicorn.run(app, host=host, port=port)


def run_eval():
    from eval.evaluate import run_benchmark
    run_benchmark()


def run_crawl():
    from crawler.full_crawler import QingchuanFullCrawler
    crawler = QingchuanFullCrawler(timeout=10, max_workers=6)
    crawler.crawl_all(max_pages=4, download_images=True)


def main():
    parser = argparse.ArgumentParser(description="晴川 RAG 智能问答系统")
    parser.add_argument("--web", action="store_true", help="启动分屏 Web 可视化服务 (默认)")
    parser.add_argument("--cli", action="store_true", help="进入终端命令行交互问答模式")
    parser.add_argument("--eval", action="store_true", help="运行自动化基准评测 (TF-IDF vs BGE vs Hybrid)")
    parser.add_argument('--eval-answers', action='store_true', help='运行参考事实、引用与拒答评测')
    parser.add_argument("--crawl", action="store_true", help="执行官网实时新闻爬虫同步")
    parser.add_argument("--port", type=int, default=8000, help="Web 服务端口 (默认 8000)")

    args = parser.parse_args()

    if args.cli:
        run_cli()
    elif args.eval:
        run_eval()
    elif args.eval_answers:
        from eval.answer_evaluate import run_answer_benchmark
        reports = run_answer_benchmark()
        for mode, report in reports.items():
            print(f"{mode}: {report['passed_count']}/{report['total_cases']} cases passed")
    elif args.crawl:
        run_crawl()
    else:
        run_web(port=args.port)


if __name__ == "__main__":
    main()
