/* Opt-in agent controls and escaped tool traces. The original chat renderer remains in charge. */
(function(root){
    'use strict';
    let active=false;
    const runs=new Map();
    const escape=value=>String(value??'').replaceAll('武汉晴川学院', '晴川').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const names={search_knowledge:'检索校园资料',lookup_place:'查询地标',plan_route:'计算示意路线',current_time:'查询当前时间'};
    const stops={completed:'已整理办理建议',clarification:'需要补充信息',no_evidence:'缺少可引用依据',not_configured:'尚未配置模型',
        timeout:'达到时间限制',step_limit:'达到步骤上限',repeated_action:'重复调用已停止',invalid_decision:'模型决策格式无效',model_error:'模型服务不可用',session_cleared:'会话已清空',plan_rejected:'方案需继续核实'};
    const states={ok:'成功',not_found:'未找到',ambiguous:'需确认',unknown_tool:'工具不允许',invalid_arguments:'参数无效',
        tool_error:'工具异常',tool_timeout:'工具超时',invalid_decision:'格式无效',busy:'暂忙',blocked:'已拦截','no-access':'无法接入道路',disconnected:'路网未连通',plan_rejected:'方案未通过检查'};
    function renderTrace(agent){
        if(!agent)return '';
        const rows=agent.trace||[];
        return `<details class="agent-trace"><summary>执行轨迹 · ${rows.length}步 · ${escape(stops[agent.stop_reason]||agent.stop_reason)}</summary>
        <p class="agent-trace-note">${agent.model_called?'模型选择工具，系统校验并执行；此处展示操作记录，不展示内部思维链。':'本次未调用模型。请在“大模型接入配置”中设置云端或本地模型。'}</p>
        ${rows.map(r=>`<div class="agent-step"><div><strong>${escape(r.step)}. ${escape(names[r.tool]||r.tool)}</strong><span>${escape(states[r.status]||r.status)} · ${escape(r.elapsed_ms)}ms</span></div><pre>${escape(JSON.stringify(r.arguments||{},null,2))}</pre><p>${escape(r.summary)}</p>${r.evidence_ids?.length?`<small>证据标识：${escape(r.evidence_ids.join('、'))}</small>`:''}</div>`).join('')}
        <div class="agent-trace-footer">运行编号：${escape(agent.run_id)} <button type="button" data-agent-download="${escape(agent.run_id)}">导出本次记录</button></div></details>`;
    }
    function remember(data){if(data.agent)runs.set(data.agent.run_id,data);}
    function renderReply(data,msgId,formatAnswer){
        const agent=data.agent;
        const citations=(data.citations||[]).filter(c=>Number.isInteger(c.index));
        const safeMsg=String(msgId).replace(/[^a-zA-Z0-9_-]/g,'');
        const route=data.navigation;
        const routeHtml=route?.from_id&&route?.to_id?`<button type="button" class="agent-route-action" data-agent-from="${escape(route.from_id)}" data-agent-to="${escape(route.to_id)}">查看示意路线：${escape(route.from_name||route.from_id)} → ${escape(route.to_name||route.to_id)}</button>`:'';
        return `<section class="agent-task-card"><div class="agent-task-heading"><strong>智能办事</strong><span>${escape(stops[agent.stop_reason]||'任务处理中')}</span></div>
            <div class="agent-task-answer">${formatAnswer(data.answer||'',msgId)}</div>${routeHtml}
            ${citations.length?`<details class="agent-sources"><summary>参考依据 · ${citations.length}项</summary>${citations.map(c=>`<button type="button" onclick="openCitationModal('${safeMsg}', ${c.index})">[${c.index}] ${escape(c.title||c.doc_name||c.source||'校园资料')}</button>`).join('')}</details>`:''}
            ${renderTrace(agent)}</section>`;
    }
    function download(runId){
        const data=runs.get(runId);if(!data)return;
        const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json;charset=utf-8'});
        const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`校园智能办事-${runId}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    function welcomeHtml(agentMode,normalHtml=''){
        if(!agentMode)return normalHtml;
        return `<div class="provider-tag">晴川校园助手</div><div class="lead-line">你想办理什么事？</div><p class="ans-body">告诉我事项和出发地点，我来帮你查询和安排。</p>`;
    }
    function refreshWelcome(){
        const welcome=document.querySelector('#chat-stream .agent-welcome');
        if(welcome){
            if(!Object.prototype.hasOwnProperty.call(welcome.dataset,'normalWelcome'))welcome.dataset.normalWelcome=welcome.innerHTML;
            welcome.innerHTML=welcomeHtml(active,welcome.dataset.normalWelcome);
        }
    }
    function setActive(value){
        if(typeof chatRequestController!=='undefined'&&chatRequestController)return;
        if(typeof switchChatWorkspace==='function')switchChatWorkspace(value);
        active=value;
        for(const [id,on] of [['agent-mode-normal',!active],['agent-mode-agent',active]]){
            const el=document.getElementById(id);if(el){el.classList.toggle('active',on);el.setAttribute('aria-pressed',String(on));}
        }
        const note=document.getElementById('agent-mode-note');
        if(note)note.textContent=active?'告诉我你要办的事，我来帮你查信息、安排路线。':'普通问答：使用现有检索、证据回答和地图联动。';
        const examples=document.getElementById('agent-examples');if(examples)examples.hidden=!active;
        const retrievalExplanation=document.getElementById('mode-explanation');if(retrievalExplanation)retrievalExplanation.hidden=active;
        for(const id of ['retrieval-controls','retrieval-label']){
            const el=document.getElementById(id);if(el)el.hidden=active;
        }
        const suggestions=document.querySelector('.suggestions');if(suggestions)suggestions.hidden=active;
        refreshWelcome();
    }
    async function clearSession(sid){
        runs.clear();
        try{await fetch('/api/agent/runs?session_id='+encodeURIComponent(sid),{method:'DELETE'});}catch(_){/* UI rotates session even if server is unavailable. */}
    }
    let historySessions=[], historySelected='', historyRecords=[], historyVersion=0;
    function currentSid(){return typeof currentChatSessionId==='string'?currentChatSessionId:'';}
    function renderHistorySessions(sessions,selected){
        if(!sessions.length)return '<p class="agent-empty">暂无已保存的办事会话。</p>';
        return sessions.map(s=>`<button type="button" class="agent-session-item ${s.session_id===selected?'selected':''}" data-agent-session="${escape(s.session_id)}" aria-pressed="${s.session_id===selected}"><strong>${escape(s.title)}</strong><small>${escape(s.turn_count)}轮对话 · ${escape(s.updated_at)} UTC${s.session_id===currentSid()?' · 当前会话':''}</small></button>`).join('');
    }
    function closeHistory(){
        historyVersion++;
        const modal=document.getElementById('agent-history-modal');if(modal)modal.hidden=true;
    }
    async function selectHistory(sid){
        const version=++historyVersion;
        historySelected=sid;historyRecords=[];
        document.getElementById('agent-history-sessions').innerHTML=renderHistorySessions(historySessions,sid);
        const target=document.getElementById('agent-history-turns');target.textContent='正在读取对话…';
        try{
            const response=await fetch('/api/agent/runs?session_id='+encodeURIComponent(sid)+'&limit=200');
            if(!response.ok)throw new Error();
            const records=(await response.json()).runs||[];
            if(version!==historyVersion)return;
            historyRecords=records;
            const item=historySessions.find(s=>s.session_id===sid);
            target.innerHTML=`<div class="agent-history-actions"><strong>${escape(item?.title||'办事对话')}</strong><div><button type="button" data-agent-continue="${escape(sid)}">继续此对话</button><button type="button" data-agent-delete="${escape(sid)}">删除此会话</button></div></div>
                ${item?.turn_count>200?'<p class="agent-empty">当前展示最近200轮对话。</p>':''}
                ${records.length?records.map(r=>`<article class="agent-history-turn"><small>${escape(r.created_at)} UTC</small><div class="agent-history-question"><b>我</b><p>${escape(r.question)}</p></div><div class="agent-history-answer"><b>办事助手</b><p>${escape(r.result.answer).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>')}</p></div></article>`).join(''):'<p class="agent-empty">此会话暂无已保存的对话。</p>'}`;
        }catch(_){if(version===historyVersion)target.textContent='读取失败，请刷新后重试。';}
    }
    async function openHistory(){
        let modal=document.getElementById('agent-history-modal');
        if(!modal){
            modal=document.createElement('div');modal.id='agent-history-modal';modal.className='agent-modal';
            modal.innerHTML='<div class="agent-modal-card agent-history-card" role="dialog" aria-modal="true" aria-label="智能办事历史"><div class="agent-modal-heading"><h2>智能办事历史</h2><div><button type="button" data-agent-history-refresh>刷新</button><button type="button" data-agent-history-close aria-label="关闭">✕</button></div></div><p class="agent-history-intro">最近100个办事会话，按最近使用时间排列。选择会话查看记录，也可以继续对话。</p><div class="agent-history-layout"><nav id="agent-history-sessions" aria-label="办事会话"></nav><div id="agent-history-turns"></div></div></div>';
            document.body.appendChild(modal);
            modal.addEventListener('click',e=>{if(e.target===modal)closeHistory();});
        }
        modal.hidden=false;
        const version=++historyVersion;
        const list=document.getElementById('agent-history-sessions'),detail=document.getElementById('agent-history-turns');
        list.textContent='正在读取会话…';detail.textContent='';
        try{
            const response=await fetch('/api/agent/sessions');if(!response.ok)throw new Error();
            const sessions=(await response.json()).sessions||[];if(version!==historyVersion)return;
            historySessions=sessions;
            const selected=sessions.find(s=>s.session_id===historySelected)||sessions.find(s=>s.session_id===currentSid())||sessions[0];
            if(selected)await selectHistory(selected.session_id);
            else{list.innerHTML=renderHistorySessions([], '');detail.innerHTML='<p class="agent-empty">保存的办事对话会显示在这里，普通问答记录请切换到普通问答查看。</p>';}
        }catch(_){if(version===historyVersion)list.textContent='读取失败，请确认服务已启动，再点击刷新。';}
    }
    async function deleteHistory(sid){
        if(typeof chatRequestController!=='undefined'&&chatRequestController){alert('请等当前回复结束后再删除会话。');return;}
        if(!confirm('确定删除这个办事会话及其全部记录吗？'))return;
        try{
            const response=await fetch('/api/agent/runs?session_id='+encodeURIComponent(sid),{method:'DELETE'});
            if(!response.ok)throw new Error();
            if(sid===currentSid()&&typeof startNewChatWindow==='function')startNewChatWindow(false);
            historySelected='';await openHistory();
        }catch(_){alert('删除失败，请稍后重试。');}
    }
    const api={isActive:()=>active,setActive,renderTrace,renderReply,remember,clearSession,openHistory,renderHistorySessions,download,welcomeHtml,refreshWelcome};
    root.CampusAgentUI=api;
    if(typeof module!=='undefined')module.exports=api;
    if(typeof document!=='undefined'){
        document.addEventListener('click',async e=>{
            const route=e.target.closest?.('[data-agent-from]');
            if(route&&typeof callMapRoute==='function')callMapRoute(route.dataset.agentFrom,route.dataset.agentTo);
            const button=e.target.closest?.('[data-agent-download]');if(button)download(button.dataset.agentDownload);
            if(e.target.closest?.('[data-agent-history-close]'))closeHistory();
            if(e.target.closest?.('[data-agent-history-refresh]'))await openHistory();
            const session=e.target.closest?.('[data-agent-session]');if(session)await selectHistory(session.dataset.agentSession);
            const remove=e.target.closest?.('[data-agent-delete]');if(remove)await deleteHistory(remove.dataset.agentDelete);
            const resume=e.target.closest?.('[data-agent-continue]');
            if(resume&&resume.dataset.agentContinue===historySelected&&typeof restoreAgentSession==='function'){
                if(restoreAgentSession(historySelected,historyRecords))closeHistory();
            }
        });
        document.addEventListener('keydown',e=>{if(e.key==='Escape')closeHistory();});

    }
})(typeof window!=='undefined'?window:globalThis);
