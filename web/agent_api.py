"""Opt-in agent routes; no changes to the ordinary RAG query contract."""
import threading
from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, field_validator
from web.schemas import ChatRequest
from core.agent.planner import JsonPlanner
from core.agent.runtime import AgentRuntime, redact
from core.agent.tools import CampusTools
from core.agent.store import AgentStore


class AgentRequest(ChatRequest):
    session_id: str = Field(min_length=1,max_length=96,pattern=r'^[A-Za-z0-9_-]+$')

    @field_validator('question')
    @classmethod
    def nonempty(cls,value):
        if not value.strip():raise ValueError('问题不能为空')
        return value.strip()


def default_planner(req):
    p=JsonPlanner(api_key=req.deepseek_key,model=req.model,api_url=req.api_url,use_ollama=req.use_ollama,
                  ollama_url=req.ollama_url,ollama_model=req.ollama_model)
    return p if p.configured else None


def create_agent_router(engine_provider,store=None,planner_factory=default_planner):
    store=store or AgentStore()
    router=APIRouter(prefix='/api/agent',tags=['校园办事智能体'])
    gate=threading.Lock();active=set()

    @router.post('/chat')
    def agent_chat(req:AgentRequest):
        sid=req.session_id
        with gate:
            if sid in active:raise HTTPException(409,'当前会话仍有任务执行中，请稍后重试。')
            if len(active)>=4:raise HTTPException(429,'智能办事暂忙，请稍后重试。')
            active.add(sid)
        try:
            epoch=store.version(sid)
            # Request history deliberately ignored: it may belong to another UI session.
            prior=store.history(sid,limit=8)
            history=[]
            for row in prior:
                history.extend([{'role':'user','content':row['question'][:1000]},
                                {'role':'assistant','content':row['result']['answer'][:1600]}])
            try: planner=planner_factory(req)
            except ValueError as exc:raise HTTPException(400,'模型地址配置无效，请使用不含凭证或查询参数的HTTP地址。') from exc
            tools=CampusTools(engine_provider(),mode=req.mode)
            result=AgentRuntime(planner,tools.registry(),require_plan=True).run(redact(req.question),history=history)
            result['agent']['session_id']=sid
            result['agent']['model']=getattr(planner,'model',None)
            if result['agent']['model_called']:
                saved=store.save(sid,req.question,result,epoch)
                result['agent']['saved']=saved
                if not saved:
                    result['agent']['stop_reason']='session_cleared'
                    result['answer']='会话已被清空，本次在途结果未写入历史。'
                    result.update(citations=[],evidence=[],navigation=None,target_landmark=None)
            return result
        finally:
            with gate:active.discard(sid)

    @router.get('/runs')
    def runs(session_id:str=Query(min_length=1,max_length=96,pattern=r'^[A-Za-z0-9_-]+$'),
             limit:int=Query(default=30,ge=1,le=200)):
        return {'runs':store.history(session_id,limit=limit)}

    @router.get('/sessions')
    def sessions():
        return {'sessions':store.sessions()}

    @router.delete('/runs')
    def clear_runs(session_id:str=Query(min_length=1,max_length=96,pattern=r'^[A-Za-z0-9_-]+$')):
        return {'deleted_count':store.clear(session_id)}

    @router.get('/quality')
    def quality():
        import json
        from pathlib import Path
        p=Path(__file__).resolve().parents[1]/'eval/agent_offline_results.json'
        return json.loads(p.read_text('utf-8')) if p.exists() else {'kind':'offline_contract','real_model_evaluation':False,'cases':[],'description':'尚未运行离线检查。'}

    @router.post('/quality/run')
    def run_quality():
        from eval.agent_evaluate import offline_report
        return offline_report()

    return router
