"""Offline executor checks and explicit live evaluation; results never conflated."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.agent.runtime import AgentRuntime


def offline_report():
    tool=lambda args,timeout:{'status':'ok','facts':[{'text':'示例资料：工作日21:30停止借还。','source':'fixture','title':'离线示例'}]}
    call={'action':'tool','tool':'search_knowledge','arguments':{'query':'图书馆借还时间'}}
    scenarios=[
        ('tool_observation_finish','工具调用与证据引用',[call,{'action':'finish','evidence_ids':['e1']}],'completed'),
        ('missing_evidence','未知证据拒绝',[{'action':'finish','evidence_ids':['e999']}],'no_evidence'),
        ('clarification','条件不全时澄清',[{'action':'clarify','question':'请问从哪里出发？'}],'clarification'),
        ('unknown_tool','未知工具与循环停止',[{'action':'tool','tool':'delete_files','arguments':{}}]*2,'repeated_action'),
        ('invalid_parameters','参数校验',[{'action':'tool','tool':'search_knowledge','arguments':{}},{'action':'finish','evidence_ids':[]}],'no_evidence'),
        ('invalid_json','无效模型输出停止',['invalid','invalid'],'invalid_decision'),
        ('repeated_tool','重复查询停止',[call,call],'repeated_action'),
        ('step_budget','步骤耗尽',[call],'step_limit'),
        ('injection_output','不接受自由编造答案',[{'action':'finish','evidence_ids':[],'answer':'凭空电话号码123456'}]*2,'invalid_decision'),
        ('tool_failure','工具异常可恢复',[call,{'action':'clarify','question':'工具暂不可用，请补充具体事项。'}],'clarification'),
        ('timeout','模型超时停止',[],'timeout'),
        ('unconfigured','无模型配置明确提示',[],'not_configured'),
        ('action_plan','生成有引用的办理建议',[call,{'action':'finish','evidence_ids':['e1'],
            'plan':[{'instruction':'建议先去图书馆办理还书。','evidence_ids':['e1']}]}],'completed'),
        ('invalid_plan','拒绝无依据时间的方案',[call]+[{'action':'finish','evidence_ids':['e1'],
            'plan':[{'instruction':'建议20:00去图书馆还书。','evidence_ids':['e1']}]}]*2,'plan_rejected'),
    ]
    cases=[]
    for sid,label,actions,expected in scenarios:
        actions=list(actions)
        def planner(messages,remaining):
            if sid=='timeout':raise TimeoutError()
            return actions.pop(0)
        def broken(args,timeout): raise RuntimeError('secret never returned')
        runtime=AgentRuntime(None if sid=='unconfigured' else planner,
            {'search_knowledge':broken if sid=='tool_failure' else tool},max_steps=1 if sid=='step_budget' else 8)
        result=runtime.run('离线契约验证，不代表真实用户任务')
        passed=result['agent']['stop_reason']==expected
        if sid=='tool_observation_finish':passed=passed and '[1]' in result['answer']
        if sid=='invalid_parameters':passed=passed and result['agent']['trace'][0]['status']=='invalid_arguments'
        if sid=='tool_failure':passed=passed and result['agent']['trace'][0]['status']=='tool_error'
        cases.append({'id':sid,'name':label,'passed':passed,'expected':expected,
                      'observed':result['agent']['stop_reason'],'trace':result['agent']['trace']})
    return {'kind':'offline_contract','real_model_evaluation':False,'created_at':datetime.now(timezone.utc).isoformat(),
            'description':'脚本决策源与示例工具验证执行器边界；不是实际模型的任务完成率。',
            'total':len(cases),'passed':sum(c['passed'] for c in cases),'cases':cases}


def live_report(model=None,api_url=None):
    from core.agent.planner import JsonPlanner
    planner=JsonPlanner(model=model,api_url=api_url)
    if not planner.configured:raise SystemExit('真实评测需要DEEPSEEK_API_KEY；未调用模型，未生成真实评测结果。')
    from core.document_loader import load_and_chunk_documents
    from core.tfidf_retriever import TfidfRetriever
    from core.bge_retriever import BgeSemanticRetriever
    from core.hybrid_retriever import HybridRetriever
    from core.rag_engine import QingchuanRagEngine
    from core.agent.tools import CampusTools
    chunks=load_and_chunk_documents(ROOT/'data/docs')
    tfidf=TfidfRetriever(chunks);bge=BgeSemanticRetriever(chunks)
    tools=CampusTools(QingchuanRagEngine(tfidf,bge,HybridRetriever(tfidf,bge)))
    dataset=json.loads((ROOT/'eval/agent_dataset.json').read_text('utf-8'))
    cases=[]
    for item in dataset:
        result=AgentRuntime(planner,tools.registry(),require_plan=True).run(item['question'])
        used={row['tool'] for row in result['agent']['trace']}
        linked=all(e['citation_index'] in {c['index'] for c in result['citations']} for e in result['evidence'])
        cases.append({'id':item['id'],'question':item['question'],'requires_human_review':True,
            'required_tools_observed':set(item['required_tools']).issubset(used),
            'evidence_links_valid':linked,'result':result})
    return {'kind':'live_model','real_model_evaluation':True,'model':planner.model,
            'created_at':datetime.now(timezone.utc).isoformat(),'cases':cases,
            'description':'真实模型执行记录。工具与引用检查是代理指标，答案条件、事实及任务完成仍需人工复核。'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',help='显式调用真实模型，可能产生费用')
    parser.add_argument('--model');parser.add_argument('--api-url')
    args=parser.parse_args()
    report=live_report(args.model,args.api_url) if args.live else offline_report()
    target=ROOT/'eval'/('agent_live_results.json' if args.live else 'agent_offline_results.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'结果已保存：{target.name}；类型：{report["kind"]}')
    if not args.live:
        print(f'离线执行器检查：{report["passed"]}/{report["total"]}；未测量真实模型准确率。')
        if report['passed']!=report['total']:raise SystemExit(1)

if __name__=='__main__':main()
