"""Only read-only tools. Knowledge results come from linked evidence, not free prose."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
import json
import os
import shutil
import subprocess
import threading

ROOT=Path(__file__).resolve().parents[2]
_pool=ThreadPoolExecutor(max_workers=2, thread_name_prefix='campus-agent-knowledge')
_slots=threading.BoundedSemaphore(2)


def route_command(*args, timeout=8):
    node=os.environ.get('CAMPUS_NODE') or shutil.which('node')
    if not node: raise RuntimeError('Node runtime not available')
    try:
        result=subprocess.run([node,str(ROOT/'scripts/agent_route.cjs'),*args],
                              capture_output=True,encoding='utf-8',timeout=min(timeout,8),
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True)
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired as exc: raise TimeoutError() from exc


@lru_cache(maxsize=1)
def map_places(): return route_command('--places')['places']


class CampusTools:
    def __init__(self, engine, mode='hybrid'):
        self.engine,self.mode=engine,mode

    def registry(self):
        return {name:getattr(self,name) for name in ('search_knowledge','lookup_place','plan_route','current_time')}

    def search_knowledge(self, args, timeout):
        if not _slots.acquire(blocking=False):
            return {'status':'busy','message':'知识检索暂忙，可稍后查询或说明未完成。'}
        try:
            future=_pool.submit(self.engine.query,args['query'],mode=self.mode,top_k=4,history=[],allow_generation=False)
        except Exception:
            _slots.release();raise
        future.add_done_callback(lambda _: _slots.release())
        try: result=future.result(timeout=max(.1, min(timeout,25)))
        except FutureTimeout as exc: raise TimeoutError() from exc
        if result.get('security_flag'):
            return {'status':'blocked','message':'查询包含不支持的指令，知识工具拒绝执行。'}
        citations={c['index']:c for c in result.get('citations',[])}
        facts=[]
        for e in result.get('evidence',[])[:6]:
            c=citations.get(e.get('citation_index'))
            if not c or not e.get('text'):continue
            facts.append({'text':e['text'],'source':c['source'],'title':c.get('title') or c.get('doc_name',''),
                          'url':c.get('url',''),'full_text':c.get('full_text') or e['text'],
                          'section_id':c.get('section_id','')})
        return {'status':'ok' if facts else 'not_found', 'facts':facts,
                'message':f'找到{len(facts)}条原文依据。资料有效期仍需结合原始公告核实。' if facts else '本地资料未找到可直接作答的证据，不可补写事实。'}

    def lookup_place(self, args, timeout):
        from core.school_constants import LANDMARK_ALIASES
        query=args['name'].strip()
        places=map_places()
        exact=[p for p in places if query in (p['id'],p['name']) or query in LANDMARK_ALIASES.get(p['id'],[])]
        matches=exact or [p for p in places if query in p['name']]
        if not matches:return {'status':'not_found','message':'地图中没有明确对应地点，请先查询部门资料或补充地标。','places':[]}
        if len(matches)>1:return {'status':'ambiguous','places':matches[:8],'message':'名称存在多个匹配，需要确认具体地点。'}
        p=matches[0]
        return {'status':'ok','places':matches,'facts':[{'text':f'校园示意图地点：{p["name"]}，地标ID：{p["id"]}。',
                'source':'campus_map','title':'校园示意图地标','target_landmark':{'id':p['id'],'name':p['name'],'trigger':p['name']}}]}

    def plan_route(self, args, timeout):
        result=route_command(args['from_id'],args['to_id'],timeout=timeout)
        if result['status']=='ok':
            result['facts']=[{'text':f'示意路线：{result["from_name"]} → {result["to_name"]}。依据项目保存的默认道路图计算；不代表实测距离、通行条件或实时路况。浏览器自定义路网可能不同。',
                'source':'campus_map','title':'保存的默认校园示意路网',
                'navigation':{'from_id':result['from_id'],'to_id':result['to_id']}}]
            result['message']='示意路网计算完成，实际通行以现场标识为准。'
        else: result.setdefault('message',{'same-place':'起终点相同。','no-access':'该地标缺少可用道路接入。','disconnected':'现有路网尚未连通，不能虚构路线。','no-roads':'没有保存的路网。'}.get(result['status'],'地点未找到。'))
        return result

    def current_time(self,args,timeout):
        value=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
        return {'status':'ok','now':value,'timezone':'Asia/Shanghai',
                'facts':[{'text':f'当前上海时区时间：{value}。该时间不代表学校业务开放状态。','source':'system_clock','title':'系统时钟'}]}
