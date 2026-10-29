const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/js/chat.js'), 'utf8');
function setup(stored = {}) {
    const elements = new Map();
    function element() { return {value:'', checked:false, disabled:false, dataset:{}, style:{}, innerText:'', textContent:'', innerHTML:'', attrs:{}, classList:{toggle(name,on){this[name]=on;},add(){},remove(){}},setAttribute(k,v){this.attrs[k]=v;},addEventListener(){},appendChild(){},querySelector(){return {textContent:''};},remove(){}}; }
    const tabs = ['hybrid','bge','tfidf'].map(mode => Object.assign(element(), {dataset:{mode}}));
    const calls = [], alerts=[];
    const storage = new Map(Object.entries(stored));
    const context = {document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},querySelectorAll(s){return s.includes('mode-tab')?tabs:[];},querySelector(){return null;},createElement:element},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)},window:{addEventListener(){},speechSynthesis:null},alert:m=>alerts.push(m),confirm:()=>true,console,AbortController,performance:{now:()=>1},setTimeout,Date,Math,fetch:async(url,options)=>{calls.push(JSON.parse(options.body));return {ok:true,json:async()=>({answer:'答复',citations:[],refused:false})};}};
    vm.createContext(context);vm.runInContext(source,context);
    vm.runInContext('appendAiResponse = (data) => { globalThis.lastRendered = data; }',context);
    return {context,elements,tabs,storage,calls,alerts,run:code=>vm.runInContext(code,context)};
}
test('all three modes update selected/aria state without fetching',()=>{
 const s=setup();for(const mode of ['tfidf','bge','hybrid']){s.run(`setMode('${mode}')`);for(const tab of s.tabs){assert.equal(tab.classList.active,tab.dataset.mode===mode);assert.equal(tab.attrs['aria-pressed'],String(tab.dataset.mode===mode));}}assert.equal(s.calls.length,0);
});

test('switching session invalidates inflight response and old local context',()=>{
 const s=setup();
 s.run("sessionHistory=[{context_question:'旧会话问题'}];lastSuccessfulRequest={question:'旧问题'};chatRequestController=new AbortController();globalThis.previousController=chatRequestController");
 s.run("switchToSession('session_new')");
 assert.equal(s.run('previousController.signal.aborted'),true);
 assert.equal(s.run('conversationTurns().length'),0);
 assert.equal(s.run('lastSuccessfulRequest'),null);
 assert.equal(s.run('currentChatSessionId'),'session_new');
});
test('legacy model migrates to Flash and preserves API key, thinking defaults off',()=>{
 const s=setup({deepseek_model:'deepseek-reasoner',deepseek_api_key:'keep-key'});s.run('openDeepSeekModal()');assert.equal(s.storage.get('deepseek_model'),'deepseek-flash');assert.equal(s.storage.get('deepseek_api_key'),'keep-key');assert.equal(s.elements.get('cfg-deepseek-thinking').checked,false);assert.match(s.elements.get('cfg-model-migration').textContent,/已迁移/);
});
test('save persists thinking and says connection unverified',()=>{
 const s=setup();s.run('openDeepSeekModal()');s.elements.get('cfg-deepseek-key').value='key';s.elements.get('cfg-deepseek-thinking').checked=true;s.run('saveDeepSeekConfig()');assert.equal(s.storage.get('deepseek_thinking'),'true');assert.match(s.alerts.at(-1),/未验证连接/);assert.equal(s.calls.length,0);
});
test('rerun preserves original prior context and replaces the last context turn',async()=>{
 const s=setup();s.run("sessionHistory = [{question:'图书馆',context_question:'图书馆'}]");s.context.document.getElementById('user-input').value='周末呢';await s.run('sendMsg()');s.run("setMode('tfidf')");await s.run('rerunLastQuestion()');assert.equal(s.calls.length,2);assert.equal(s.calls[1].mode,'tfidf');assert.deepEqual(s.calls[1].history,[{role:'user',content:'图书馆'}]);assert.equal(s.calls[1].thinking,false);assert.equal(s.run('sessionHistory.length'),2);assert.equal(s.context.lastRendered.request_mode,'tfidf');
});
test('mode changes are guarded while request is in flight',()=>{const s=setup();s.run('chatRequestController = {}; setMode("bge")');assert.equal(s.run('currentMode'),'hybrid');});
test('rerun is disabled before success and clearing removes snapshot',async()=>{
 const s=setup();s.run('syncRequestControls()');assert.equal(s.elements.get('rerun-last-btn').disabled,true);s.context.document.getElementById('user-input').value='图书馆';await s.run('sendMsg()');assert.equal(s.elements.get('rerun-last-btn').disabled,false);s.run('clearChatStream()');assert.equal(s.elements.get('rerun-last-btn').disabled,true);assert.equal(s.run('lastSuccessfulRequest'),null);
});
test('thinking true is sent and in-flight mode/config edits cannot change request',async()=>{
 const s=setup({deepseek_api_key:'key',deepseek_thinking:'true'});let release;s.context.fetch=async(url,options)=>{s.calls.push(JSON.parse(options.body));await new Promise(resolve=>{release=resolve;});return {ok:true,json:async()=>({answer:'资料不足',refused:true})};};s.context.document.getElementById('user-input').value='问题';const pending=s.run('sendMsg()');assert.equal(s.elements.get('rerun-last-btn').disabled,true);s.run("setMode('tfidf'); saveDeepSeekConfig()");release();await pending;assert.equal(s.calls[0].mode,'hybrid');assert.equal(s.calls[0].thinking,true);assert.equal(s.calls[0].model,'deepseek-flash');assert.equal(s.context.lastRendered.request_mode,'hybrid');assert.equal(s.elements.get('rerun-last-btn').disabled,false);
});
test('composite analysis escapes labels and displays per-item status',()=>{const s=setup();const html=s.run(`renderQueryAnalysis({query_analysis:{original_query:'a',rewritten_query:'a',subqueries:[{question:'<img>'}]},partial:true,sub_answers:[{label:'<script>',refused:true}]})`);assert.match(html,/部分/);assert.ok(!html.includes('<script>'));assert.match(html,/&lt;script&gt;/);});
test('safe backend generation failure is visible and saved separately from selection',async()=>{
 const s=setup({deepseek_api_key:'never-export-key'});s.context.fetch=async()=>({ok:true,json:async()=>({answer:'原句',llm_provider:'本地证据原句抽取',generation:{status:'failed',model:'deepseek-flash',thinking:false,error_code:'rate_limit',message:'请求频率过高，已回退本地原句。'}})});s.context.document.getElementById('user-input').value='问';await s.run('sendMsg()');assert.match(s.run('sessionHistory[0].generation_error'),/请求频率过高/);assert.equal(s.run('sessionHistory[0].selected_model'),'deepseek-flash');assert.equal(s.run('sessionHistory[0].actual_provider'),'本地证据原句抽取');assert.ok(!s.run('JSON.stringify(sessionHistory)').includes('never-export-key'));
 let rendered;s.context.document.getElementById('chat-stream').appendChild=row=>{rendered=row.innerHTML;};vm.runInContext(source.slice(source.indexOf('function appendAiResponse('),source.indexOf('function sendQuickQuery(')),s.context);s.run(`appendAiResponse({answer:'原句',generation:{status:'failed',message:'<失败>'},selected_model:'deepseek-flash',llm_provider:'本地证据原句抽取'},1)`);assert.match(rendered,/&lt;失败&gt;/);assert.match(rendered,/实际提供方：本地证据原句抽取/);assert.match(rendered,/所选生成：DeepSeek V4.1 Flash/);
});

test('inline markdown renders bare URLs, parenthesized URLs, and markdown links into clickable badges',()=>{
 const s=setup();
 const html1=s.run("renderMarkdownInline('学院官方主页：https://jkx.qcuwh.edu.cn（https://jkx.qcuwh.edu.cn） [1]', 'm1')");
 assert.match(html1, /<a href="https:\/\/jkx\.qcuwh\.edu\.cn"[^>]*class="ans-link"[^>]*>🔗 https:\/\/jkx\.qcuwh\.edu\.cn<\/a>/);
 const html2=s.run("renderMarkdownInline('学院首页（https://jkx.qcuwh.edu.cn/index.htm） [1]', 'm1')");
 assert.match(html2, /<a href="https:\/\/jkx\.qcuwh\.edu\.cn\/index\.htm"[^>]*class="ans-link"[^>]*>🔗 学院首页<\/a>/);
 const html3=s.run("renderMarkdownInline('[通知入口](https://www.qcuwh.edu.cn)', 'm1')");
 assert.match(html3, /<a href="https:\/\/www\.qcuwh\.edu\.cn"[^>]*class="ans-link"[^>]*>🔗 通知入口<\/a>/);
});

test('switching workspaces isolates drafts, sessions, context, citations and rerun state',()=>{
 const s=setup(); const stream=s.context.document.getElementById('chat-stream');
 s.context.window.CampusAgentUI={welcomeHtml:()=>'<p>办事欢迎</p>',clearSession(){},refreshWelcome(){}};
 stream.childNodes=['normal-message'];stream.replaceChildren=(...nodes)=>{stream.childNodes=nodes;};
 s.context.document.getElementById('user-input').value='问答草稿';
 s.run("sessionHistory=[{context_question:'普通问题'}];questionHistory=['普通问题'];allMessagesCitations={normal:[1]};lastSuccessfulRequest={question:'普通问题'};globalThis.normalSid=currentChatSessionId");
 s.run('switchChatWorkspace(true)');
 assert.notEqual(s.run('currentChatSessionId'),s.run('normalSid'));
 assert.equal(s.run('conversationTurns().length'),0);assert.equal(s.run('lastSuccessfulRequest'),null);
 assert.equal(s.context.document.getElementById('user-input').value,'');
 s.run("sessionHistory=[{context_question:'办事任务'}];allMessagesCitations={agent:[2]}");
 stream.childNodes=['agent-message'];s.context.document.getElementById('user-input').value='办事草稿';
 s.run('switchChatWorkspace(false)');
 assert.equal(s.run('currentChatSessionId'),s.run('normalSid'));
 assert.equal(s.run('conversationTurns()[0].content'),'普通问题');
 assert.deepEqual(stream.childNodes,['normal-message']);assert.equal(s.context.document.getElementById('user-input').value,'问答草稿');
 s.run('switchChatWorkspace(true)');assert.equal(s.run('conversationTurns()[0].content'),'办事任务');
 assert.deepEqual(stream.childNodes,['agent-message']);assert.equal(s.context.document.getElementById('user-input').value,'办事草稿');
 s.run('clearChatStream();switchChatWorkspace(false)');assert.equal(s.run('conversationTurns()[0].content'),'普通问题');
});

test('restoring an agent history session stays separate from ordinary QA',()=>{
 const s=setup();
 s.context.window.CampusAgentUI={welcomeHtml:()=>'',remember(){}};
 const stream=s.context.document.getElementById('chat-stream');stream.childNodes=[];stream.replaceChildren=()=>{};
 s.run("sessionHistory=[{context_question:'普通问题'}]");
 assert.equal(s.run("restoreAgentSession('saved',[])"),false);
 s.run('switchChatWorkspace(true)');
 s.context.savedRecords=[{question:'历史办事问题',created_at:'2026-10-23',result:{answer:'办事回复',citations:[],agent:{run_id:'r'}}}];
 assert.equal(s.run("restoreAgentSession('saved',savedRecords)"),true);
 assert.equal(s.run('currentChatSessionId'),'saved');assert.equal(s.run('conversationTurns()[0].content'),'历史办事问题');
 s.run('switchChatWorkspace(false)');assert.equal(s.run('conversationTurns()[0].content'),'普通问题');
});
