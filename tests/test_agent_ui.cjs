const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const uiPath=path.join(__dirname,'../web/static/js/agent.js');
test('agent UI module exists',()=>assert.ok(fs.existsSync(uiPath)));
test('trace escapes untrusted tool inputs and labels offline source',()=>{
    const ui=require(uiPath);
    const html=ui.renderTrace({run_id:'x',model_called:true,stop_reason:'completed',trace:[{
        step:1,tool:'search_knowledge',arguments:{query:'<img src=x onerror=alert(1)>'},status:'ok',summary:'<script>bad()</script>',elapsed_ms:3
    }]});
    assert.ok(html.includes('&lt;img'));
    assert.ok(!html.includes('<script>'));
    assert.ok(html.includes('执行轨迹'));
    assert.equal(ui.openQuality,undefined);
});
test('chat retains original endpoint and selects agent endpoint explicitly',()=>{
    const source=fs.readFileSync(path.join(__dirname,'../web/static/js/chat.js'),'utf8');
    assert.ok(source.includes('agentMode ? "/api/agent/chat" : "/api/chat"'));
    assert.ok(source.includes('renderTrace(data.agent)'));
});
test('welcome copy is short and mode-specific',()=>{
    const ui=require(uiPath);
    const html=ui.welcomeHtml(true);
    assert.ok(html.includes('你想办理什么事'));
    assert.ok(!html.includes('模型'));
    assert.ok(!html.includes('知识库'));
    assert.ok(!html.includes('不保证'));
    assert.ok(!html.includes('3,091'));
    assert.equal(ui.welcomeHtml(false,'原有普通问答欢迎内容'),'原有普通问答欢迎内容');
});
test('switching back restores each ordinary welcome verbatim',()=>{
    const ui=require(uiPath);
    for(const original of ['原有知识库介绍及功能说明','对话记录已清空。原有说明','已开启全新的独立对话窗口！原有说明']){
        const welcome={innerHTML:original,dataset:{}};
        global.document={getElementById:()=>null,querySelector:()=>welcome};
        try{
            ui.setActive(true);
            assert.ok(welcome.innerHTML.includes('你想办理什么事'));
            ui.setActive(false);
            assert.equal(welcome.innerHTML,original);
        }finally{delete global.document;}
    }
});
test('brand is shortened in static front-end files',()=>{
    for(const file of ['../web/templates/index.html','../web/static/js/chat.js','../web/static/campus3d/campus-landmarks.js']){
        const source=fs.readFileSync(path.join(__dirname,file),'utf8');
        // The display normalizer may retain the input name only as a matching pattern.
        assert.ok(!source.replace(/replaceAll\('武汉晴川学院', '晴川'\)/g,'').includes('武汉晴川学院'),file);
    }
});
test('algorithm selector is hidden only in agent mode without modifying retrieval selection',()=>{
    const ui=require(uiPath);
    const controls={hidden:false};
    global.document={getElementById:id=>id==='retrieval-controls'?controls:null,querySelector:()=>null};
    try{
        ui.setActive(true);assert.equal(controls.hidden,true);
        ui.setActive(false);assert.equal(controls.hidden,false);
    }finally{delete global.document;}
});

test('agent replies use task cards without ordinary retrieval stamps and escape source names',()=>{
 const ui=require(uiPath);
 const html=ui.renderReply({answer:'办理建议',agent:{stop_reason:'clarification',model_called:true,trace:[]},citations:[{index:1,title:'<script>bad</script>'}]},'msg-1',s=>s);
 assert.match(html,/agent-task-card/);assert.match(html,/需要补充信息/);assert.match(html,/参考依据/);
 assert.ok(!html.includes('本次检索'));assert.ok(!html.includes('<script>'));
});

test('agent history has its own session browser and no quality dashboard',()=>{
 const ui=require(uiPath);
 const html=ui.renderHistorySessions([{session_id:'a',title:'<img src=x>',turn_count:2,updated_at:'2026-10-23 01:00:00'}],'a');
 assert.match(html,/data-agent-session/);assert.match(html,/2/);assert.ok(!html.includes('<img'));
 const src=fs.readFileSync(uiPath,'utf8');
 assert.ok(!src.includes('/api/agent/quality'));assert.ok(!src.includes('智能体质量'));
 const template=fs.readFileSync(path.join(__dirname,'../web/templates/index.html'),'utf8');
 assert.ok(!template.includes('openQuality'));assert.ok(!template.includes('智能体质量'));
 assert.equal(typeof ui.openHistory,'function');
});
