// -*- coding: utf-8 -*-

let currentMode = "hybrid";

let allMessagesCitations = {};

let questionHistory = [];

let historyIndex = -1;

let sessionHistory = [];
function getOrCreateSessionId(storageKey = 'qcu_chat_session_id') {
    try {
        if (typeof sessionStorage !== 'undefined') {
            let sid = sessionStorage.getItem(storageKey);
            if (!sid) {
                sid = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6);
                sessionStorage.setItem(storageKey, sid);
            }
            return sid;
        }
    } catch(e) {}
    return 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6);
}
let currentChatSessionId = getOrCreateSessionId();
let historyFilterMode = 'all';
let cachedHistoryRecords = [];

let chatRequestController = null;

let conversationEpoch = 0;

let lastSuccessfulRequest = null;

// Each mode owns its conversation, DOM nodes and draft. Only the map/config are shared.
let currentWorkspaceMode = 'normal';
const chatWorkspaces = new Map();
function chatSessionStorageKey() {
    return currentWorkspaceMode === 'agent' ? 'qcu_agent_session_id' : 'qcu_chat_session_id';
}
function switchChatWorkspace(agentMode) {
    const next = agentMode ? 'agent' : 'normal';
    if (next === currentWorkspaceMode || chatRequestController) return;
    const stream = document.getElementById('chat-stream');
    const input = document.getElementById('user-input');
    chatWorkspaces.set(currentWorkspaceMode, {
        nodes:Array.from(stream.childNodes || []), scrollTop:stream.scrollTop,
        sessionHistory, questionHistory, historyIndex, allMessagesCitations,
        lastSuccessfulRequest, sid:currentChatSessionId, draft:input.value,
        selectedHistorySessionId, cachedHistoryRecords
    });
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    conversationEpoch++;
    currentWorkspaceMode = next;
    const saved = chatWorkspaces.get(next);
    sessionHistory = saved?.sessionHistory || [];
    questionHistory = saved?.questionHistory || [];
    historyIndex = saved?.historyIndex ?? -1;
    allMessagesCitations = saved?.allMessagesCitations || {};
    lastSuccessfulRequest = saved?.lastSuccessfulRequest || null;
    currentChatSessionId = saved?.sid || getOrCreateSessionId(chatSessionStorageKey());
    selectedHistorySessionId = saved?.selectedHistorySessionId || null;
    cachedHistoryRecords = saved?.cachedHistoryRecords || [];
    input.value = saved?.draft || '';
    if (!input.dataset.normalPlaceholder) input.dataset.normalPlaceholder = input.placeholder || '';
    input.placeholder = agentMode ? '告诉我你要办的事，例如：从南大门出发，先还书再咨询选课' : input.dataset.normalPlaceholder;
    if (saved) stream.replaceChildren(...saved.nodes);
    else {
        stream.innerHTML = `<div class="msg-row ai"><div class="avatar ai">晴</div><div class="bubble agent-welcome">${window.CampusAgentUI.welcomeHtml(true)}</div></div>`;
    }
    stream.scrollTop = saved?.scrollTop || 0;
    syncRequestControls();
}

let modelMigrationNotice = '';

const MODE_NAMES = {hybrid: '混合检索与精排', bge: 'BGE 稠密语义', tfidf: 'TF-IDF 统计词频'};

const MODE_DETAILS = {

    hybrid: '结合关键词精确匹配与 BGE 语义向量召回，经加权 RRF 融合后按事实证据与槽位精排。兼顾专名定位与口语泛化，综合命中率最高。',

    bge: '基于 BAAI/bge-small-zh-v1.5 预训练语义模型，将问句与切块映射至 512 维向量空间计算余弦相似度。擅长捕捉口语表述与同义置换（如“挂科”对齐“不及格”）。',

    tfidf: '传统 NLP 统计词频基线，基于字符 1–2 gram 词频与逆文档频率计算相似度。擅长精准匹配专有名词、机构全称与具体编码，但无法理解近义词与语义关联。'

};



function generationConfig() {

    const stored = localStorage.getItem('deepseek_model');

    if (stored && ['deepseek-chat', 'deepseek-reasoner', 'deepseek-v4-flash', 'deepseek-v4.1-flash'].includes(stored)) {

        localStorage.setItem('deepseek_model', 'deepseek-flash');

        modelMigrationNotice = '旧模型配置已迁移至 DeepSeek V4.1 Flash（deepseek-flash），原 API Key 已保留；未验证连接。';

    }

    const model = localStorage.getItem('deepseek_model') || 'deepseek-flash';

    return {

        model: model,

        thinking: localStorage.getItem('deepseek_thinking') === 'true',

        cloudUrl: localStorage.getItem('cloud_api_url') || 'https://api.deepseek.com',

        useOllama: localStorage.getItem('use_ollama') === 'true',

        ollamaUrl: localStorage.getItem('ollama_url') || 'http://localhost:11434',

        ollamaModel: localStorage.getItem('ollama_model') || 'deepseek-r1:latest'

    };

}



function syncRequestControls() {

    const busy = Boolean(chatRequestController);

    document.querySelectorAll('.mode-tab, .send-btn, #cfg-deepseek-key, #cfg-deepseek-model, #cfg-deepseek-thinking, .config-save-btn, .config-clear-btn').forEach(el => { el.disabled = busy; });

    const rerun = document.getElementById('rerun-last-btn');

    if (rerun) { rerun.disabled = busy || !lastSuccessfulRequest; rerun.hidden = currentWorkspaceMode === 'agent'; }

}



function generationNotice(data) {

    const generation = data.generation;

    if (generation && generation.status !== 'success' && generation.status !== 'not_configured' && generation.message) return generation.message;

    return data.generation_error || data.generation_fallback_reason || '';

}



function escapeText(value) {

    return displaySchoolName(value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

}

function displaySchoolName(value) {
    return String(value ?? '').replaceAll('武汉晴川学院', '晴川');
}



function conversationTurns() {

    return sessionHistory.filter(item => item.context_question)

        .slice(-12).map(item => ({role: 'user', content: item.context_question.slice(0, 1000)}));

}



function renderQueryAnalysis(data) {

    const analysis = data.query_analysis;

    if (!analysis) return '';

    const intents = {time: '时间查询', contact: '联系方式', website: '网站入口', eligibility: '申请条件', amount: '金额费用', duration: '期限时长', quota: '数量额度', location: '位置查询', major: '专业查询', procedure: '办理流程', general: '一般咨询'};

    const state = data.answer_assessment === 'model_reading' ? 'AI 已阅读原文并逐项作答' : data.partial ? '部分问题已找到依据' : data.clarification ? '需要补充主题' : data.refused ? '缺少明确依据' : data.evidence_status === 'supported' ? '已找到原文依据' : '校园导航';

    const rewritten = analysis.rewritten_query !== analysis.original_query

        ? `<p>本次理解：${escapeText(analysis.rewritten_query)}</p>` : '';

    const changes = (analysis.normalizations || []).map(item => `${item.from} → ${item.to}`).join('；');

    const evidence = (data.evidence || []).map(item => `<li>${escapeText(item.text)} <span class="cite-pill">[${item.citation_index}]</span></li>`).join('');

    const suggestions = (analysis.suggestions || []).length ? `<p>你是否想问：${escapeText(analysis.suggestions.join('、'))}？</p>` : '';

    const subqueries = (analysis.subqueries || []).map(item => `<li>${escapeText(typeof item === 'string' ? item : item.question || item.label)}</li>`).join('');

    const subanswers = (data.sub_answers || []).map(item => `<li>${escapeText(item.label || item.question)}：${data.answer_assessment === 'model_reading' ? '已交由 AI 阅读原文作答' : item.clarification ? '需要澄清' : item.refused ? '本地规则未匹配到明确依据' : '已找到依据'}</li>`).join('');

    return `<details class="query-analysis"><summary>${escapeText(intents[analysis.intent] || '一般咨询')} · ${state}</summary>${rewritten}${changes ? `<p>用词归一化：${escapeText(changes)}</p>` : ''}${suggestions}${subqueries ? `<p>拆分查询：</p><ol>${subqueries}</ol>` : ''}${subanswers ? `<p>逐项状态：</p><ul>${subanswers}</ul>` : ''}${evidence ? `<p>本次采用的原文依据：</p><ul>${evidence}</ul>` : ''}</details>`;

}



function openCitationModal(msgId, citeIndex) {

    let item = null;

    if (msgId && allMessagesCitations[msgId]) {

        item = allMessagesCitations[msgId].find(c => c.index === citeIndex);

    }

    if (!item) {

        const keys = Object.keys(allMessagesCitations);

        if (keys.length > 0) {

            const lastKey = keys[keys.length - 1];

            item = allMessagesCitations[lastKey].find(c => c.index === citeIndex);

        }

    }

    if (!item) return;



    document.getElementById("cite-modal-title").innerHTML = `📜 知识溯源文献详情 · 依据 [${item.index}]`;

    document.getElementById("cite-modal-doc").innerText = displaySchoolName(item.doc_name || item.source);

    document.getElementById("cite-modal-article").innerText = displaySchoolName(item.title || "晴川规章制度与官方文献记录");



    const urlRow = document.getElementById("cite-modal-url-row");

    const linkBtn = document.getElementById("cite-modal-link");

    const footerLink = document.getElementById("cite-modal-footer-link");



    if (item.url && item.url.startsWith("http")) {

        urlRow.style.display = "flex";

        linkBtn.href = item.url;

        linkBtn.innerHTML = `<span>访问晴川官方原文页面 (${item.url.slice(0, 42)}...)</span> ↗`;

        footerLink.href = item.url;

        footerLink.style.display = "inline-flex";

    } else {
        urlRow.style.display = "none";
        footerLink.style.display = "none";
    }

    // 渲染实拍抓取附图画廊
    const galleryBox = document.getElementById("cite-modal-gallery-box");
    const galleryGrid = document.getElementById("cite-modal-gallery-grid");
    let imgs = Array.isArray(item.images) ? [...item.images] : [];
    if (imgs.length === 0 && item.full_text) {
        const matches = [...item.full_text.matchAll(/!\[([^\]]*)\]\(((\/images\/[^\s\)\"]+)|(https?:\/\/[^\s\)\"]+))\)/g)];
        for (const m of matches) {
            imgs.push({ alt: m[1] || '官方文献配图', url: m[2] });
        }
    }

    if (galleryBox && galleryGrid) {
        if (imgs.length > 0) {
            galleryBox.style.display = "block";
            galleryGrid.innerHTML = imgs.map((img, i) => `
                <div class="citation-img-card">
                    <a href="${img.url}" target="_blank" rel="noopener noreferrer" title="点击在新窗口查看原图">
                        <img src="${img.url}" alt="${escapeText(img.alt || '官方文献配图')}" loading="lazy" />
                        <span class="citation-img-zoom">🔍 点击放大</span>
                    </a>
                    ${img.alt ? `<div class="citation-img-caption" title="${escapeText(img.alt)}">${escapeText(img.alt)}</div>` : ''}
                </div>
            `).join('');
        } else {
            galleryBox.style.display = "none";
            galleryGrid.innerHTML = "";
        }
    }

    const fullTextEl = document.getElementById("cite-modal-fulltext");
    if (fullTextEl) {
        fullTextEl.innerHTML = renderCitationFullText(item.full_text || item.preview || '');
    }

    document.getElementById("citation-modal").classList.add("show");
}

function renderCitationFullText(text) {
    if (!text) return '';
    let safe = escapeText(text);
    // 将 Markdown 图片转换为安全的 figure 与 img
    safe = safe.replace(/!\[([^\]]*)\]\(((\/images\/[^\s\)\"]+)|(https?:\/\/[^\s\)\"]+))\)/g, (match, alt, url) => {
        return `<figure class="cite-inline-figure">
            <a href="${url}" target="_blank" rel="noopener noreferrer" title="点击在新窗口查看高清大图">
                <img src="${url}" alt="${alt}" loading="lazy" />
            </a>
            ${alt ? `<figcaption>${alt}</figcaption>` : ''}
        </figure>`;
    });
    // 加粗语法转换
    safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // 段落排版
    const paras = safe.split(/\n{2,}/);
    return paras.map(p => `<p class="cite-p">${p.replace(/\n/g, '<br/>')}</p>`).join('');
}



function closeCitationModal() {

    document.getElementById("citation-modal").classList.remove("show");

}



// 读取本地 DeepSeek 配置

function updateModelPill() {

    const key = localStorage.getItem("deepseek_api_key");

    generationConfig();

    const pill = document.getElementById("model-pill");

    if (!pill) return;

    if (key) {

        pill.innerText = "🤖 已选 DeepSeek V4.1 Flash · 未验证连接";

        pill.style.background = "#eef7ff";

        pill.style.color = "#0d6efd";

        pill.style.borderColor = "#b8daff";

    } else {

        pill.innerText = "✨ 晴川本地引擎";

        pill.style.background = "#eaf3ef";

        pill.style.color = "#1e5a44";

        pill.style.borderColor = "#c6e0d4";

    }

}

updateModelPill();



function setMode(mode) {

    if (chatRequestController || !Object.hasOwn(MODE_NAMES, mode)) return;

    currentMode = mode;

    document.querySelectorAll(".mode-tab").forEach(tab => {

        const selected = tab.dataset.mode === mode;

        tab.classList.toggle("active", selected);

        tab.setAttribute('aria-pressed', String(selected));

    });

    const explanation = document.getElementById('mode-explanation');

    if (explanation) explanation.textContent = `${MODE_DETAILS[mode]}（只对新提问有效）`;

}



// 亮点三：分屏比例预设切换 (6:4 / 5:5 / 4:6)

function setLayoutRatio(ratio, btn) {

    const container = document.querySelector(".main-container");

    if (!container) return;

    container.classList.remove("ratio-6-4", "ratio-5-5", "ratio-4-6", "ratio-7-3", "ratio-3-7", "map-fullscreen");

    container.classList.add("ratio-" + ratio);

    document.querySelectorAll(".layout-btn").forEach(b => b.classList.remove("active"));

    if (btn) btn.classList.add("active");

    const fsBtn = document.getElementById("map-fullscreen-btn");

    if (fsBtn) { fsBtn.innerHTML = "⛶ 全屏沙盘"; fsBtn.classList.remove("active"); }



    const frame = document.getElementById("map-frame");

    if (frame && frame.contentWindow) {

        setTimeout(() => {

            frame.contentWindow.dispatchEvent(new Event('resize'));

        }, 150);

    }

}



// 3D 地图标注直达（支持黄色光圈高亮联动）

function flyTo(landmarkId, el) {
    const ID_FALLBACKS = { 'admin': 'admin_1', 'canteen': 'canteen_main', 'gate': 'south_gate', 'dorm': 'dorm_1' };
    const realId = ID_FALLBACKS[landmarkId] || landmarkId;
    const frame = document.getElementById("map-frame");

    if (frame && frame.contentWindow) {

        try {

            if (frame.contentWindow.CampusScene && frame.contentWindow.CampusScene.select) {

                frame.contentWindow.CampusScene.select(realId);

            }

            if (frame.contentWindow.select) {

                frame.contentWindow.select(realId);

            }

        } catch(e) {

            console.log("3D Map select call failed:", e);

        }

    }

    // 高亮被点击的黄色光圈按钮

    document.querySelectorAll(".landmark-chip").forEach(c => c.classList.remove("active"));

    if (el) {

        el.classList.add("active");

    } else {

        const match = Array.from(document.querySelectorAll(".landmark-chip")).find(c => c.getAttribute("onclick") && c.getAttribute("onclick").includes(landmarkId));

        if (match) match.classList.add("active");

    }

}



// 3D 地图全屏沙盘切换

function toggleMapFullscreen() {

    const container = document.querySelector(".main-container");

    const btn = document.getElementById("map-fullscreen-btn");

    if (!container) return;

    const isFs = container.classList.toggle("map-fullscreen");

    if (btn) {

        btn.innerHTML = isFs ? "🗗 还原分屏" : "⛶ 全屏沙盘";

        btn.classList.toggle("active", isFs);

    }

    const frame = document.getElementById("map-frame");

    if (frame && frame.contentWindow) {

        setTimeout(() => {

            frame.contentWindow.dispatchEvent(new Event('resize'));

        }, 150);

    }

}



function callMapRoute(fromId, toId) {

    const frame = document.getElementById("map-frame");

    if (frame && frame.contentWindow) {

        try {

            if (frame.contentWindow.RoutePlanner && frame.contentWindow.RoutePlanner.planRoute) {

                frame.contentWindow.RoutePlanner.planRoute(fromId, toId);

            }

        } catch(e) {

            console.log("3D Map route call failed:", e);

        }

    }

}



function sendQuick(text) {

    document.getElementById("user-input").value = text;

    sendMsg();

}



async function rerunLastQuestion() {

    if (chatRequestController || !lastSuccessfulRequest) return;

    return sendMsg(lastSuccessfulRequest);

}



async function sendMsg(retryRequest = null) {

    const input = document.getElementById("user-input");

    const retry = retryRequest && typeof retryRequest.question === 'string' ? retryRequest : null;

    const q = retry ? retry.question : input.value.trim();

    if (!q || chatRequestController) return;

    if (q.length > 1000) {

        alert('问题请控制在1000字以内。');

        return;

    }

    const requestEpoch = conversationEpoch;

    const requestMode = currentMode;
    const agentMode = Boolean(window.CampusAgentUI && window.CampusAgentUI.isActive());

    const requestHistory = JSON.parse(JSON.stringify(retry ? retry.history : conversationTurns()));

    const config = generationConfig();

    const controller = new AbortController();

    chatRequestController = controller;

    syncRequestControls();



    input.value = "";

    appendMessage("user", q);



    // 显示加载状态

    const loadingRow = appendMessage("ai", agentMode ? "智能办事正在查证资料并选择工具，请稍候…" : "正在检索晴川知识库并规划导航路径...");



    const deepseekKey = localStorage.getItem("deepseek_api_key") || null;

    const deepseekModel = config.model;



    const startT = performance.now();



    try {

        const res = await fetch(agentMode ? "/api/agent/chat" : "/api/chat", {

            method: "POST",

            headers: { "Content-Type": "application/json" },

            signal: controller.signal,

            body: JSON.stringify({ 

                question: q, 

                mode: requestMode,

                top_k: 3,

                use_ollama: config.useOllama,

                deepseek_key: deepseekKey,

                model: deepseekModel,

                api_url: config.cloudUrl,

                ollama_url: config.ollamaUrl,

                ollama_model: config.ollamaModel,

                thinking: config.thinking,
                session_id: currentChatSessionId,

                history: requestHistory

            })

        });

        const data = await res.json();

        if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求参数或服务异常');

        if (requestEpoch !== conversationEpoch) return;
        if (window.CampusAgentUI) window.CampusAgentUI.remember(data);

        const latencyMs = Math.round(performance.now() - startT);



        // 亮点四：记录会话明细以便导出测试实测记录

        const record = {

            question: q,

            answer: data.answer || '',

            context_question: data.security_flag ? null : (data.query_analysis?.rewritten_query || q),

            latency: latencyMs,

            citations: data.citations || [],

            mode: requestMode,
            agent: data.agent || null,

            rewritten_query: data.query_analysis?.rewritten_query || q,

            selected_model: config.useOllama ? `本地 Ollama (${config.ollamaModel})` : (deepseekKey ? deepseekModel : '本地原句抽取'),

            actual_provider: data.llm_provider || '本地原句抽取',

            generation_error: generationNotice(data),

            time: new Date().toLocaleTimeString('zh-CN')

        };

        if (retry && Number.isInteger(retry.sessionIndex) && sessionHistory[retry.sessionIndex]) sessionHistory[retry.sessionIndex] = record;

        else sessionHistory.push(record);

        lastSuccessfulRequest = {question: q, history: requestHistory, sessionIndex: retry ? retry.sessionIndex : sessionHistory.length - 1};



        // 亮点五：记录输入历史以便上下方向键调用

        questionHistory.push(q);

        historyIndex = questionHistory.length;



        // 更新 AI 气泡

        loadingRow.remove();

        appendAiResponse({...data, request_mode: requestMode, selected_model: record.selected_model}, latencyMs);



        // 3D 地图联动导航或地标飞行

        if (data.navigation && data.navigation.from_id && data.navigation.to_id) {

            callMapRoute(data.navigation.from_id, data.navigation.to_id);

        } else if (data.target_landmark && data.target_landmark.id) {

            flyTo(data.target_landmark.id);

        }

    } catch(e) {

        if (e.name !== 'AbortError' && requestEpoch === conversationEpoch) {

            loadingRow.querySelector('.bubble').textContent = '请求失败：' + (e.message || '请检查后端服务');

        }

    } finally {

        if (chatRequestController === controller) chatRequestController = null;

        syncRequestControls();

    }

}



function appendMessage(role, text) {

    const stream = document.getElementById("chat-stream");

    const row = document.createElement("div");

    row.className = `msg-row ${role}`;

    row.innerHTML = `

        <div class="avatar ${role}">${role === 'ai' ? '晴' : '我'}</div>

        <div class="bubble">${escapeText(text).replace(/\n/g, '<br>')}</div>

    `;

    stream.appendChild(row);

    stream.scrollTop = stream.scrollHeight;

    return row;

}



function renderMarkdownInline(str, msgId) {
    if (!str) return '';
    let res = escapeText(str);

    // 1. 去除同一行中重复出现的括号 URL：如 https://a.b.c (https://a.b.c) 或 https://a.b.c（https://a.b.c）
    res = res.replace(/(https?:\/\/[^\s\(\)（）]+)\s*[（\(]\1[）\)]/g, '$1');

    // 2. 转换标准 Markdown 链接：[名称](https://...)
    // 使用临时占位符避免后续 URL 正则重复嵌套处理
    const linkMap = [];
    res = res.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, (match, label, url) => {
        const placeholder = `__LINK_PLACEHOLDER_${linkMap.length}__`;
        linkMap.push(`<a href="${url}" target="_blank" rel="noopener noreferrer" class="ans-link">🔗 ${label}</a>`);
        return placeholder;
    });

    // 3. 转换带有中文/英文括号的特定链接：例如 学院首页（https://...）或 学院首页(https://...)
    res = res.replace(/([\u4e00-\u9fa5A-Za-z0-9_·-]+)\s*[（\(](https?:\/\/[^\s\(\)（）]+)[）\)]/g, (match, label, url) => {
        const placeholder = `__LINK_PLACEHOLDER_${linkMap.length}__`;
        linkMap.push(`<a href="${url}" target="_blank" rel="noopener noreferrer" class="ans-link" title="${url}">🔗 ${label}</a>`);
        return placeholder;
    });

    // 4. 转换剩余的任何裸 URL 或独立括号中的 URL（如：https://... 或 （https://...））
    res = res.replace(/(https?:\/\/[^\s<>"'()（）]+)/g, (match, url) => {
        const placeholder = `__LINK_PLACEHOLDER_${linkMap.length}__`;
        linkMap.push(`<a href="${url}" target="_blank" rel="noopener noreferrer" class="ans-link">🔗 ${url}</a>`);
        return placeholder;
    });

    // 5. 还原所有超链接占位符
    linkMap.forEach((tag, idx) => {
        res = res.replace(`__LINK_PLACEHOLDER_${idx}__`, tag);
    });

    // 6. 格式化：加粗、斜体、行内代码
    res = res.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    res = res.replace(/\*(.*?)\*/g, '<em>$1</em>');
    res = res.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // 7. 溯源引用编号 [1], [2]
    res = res.replace(/\[(\d+)\]/g, (m, p1) => {
        const arg = msgId ? `'${msgId}'` : 'null';
        return `<span class="cite-pill clickable" onclick="openCitationModal(${arg}, ${p1})" title="点击查看依据 [${p1}] 全文与官网原文">[${p1}]</span>`;
    });

    return res;
}

function renderBlockLines(blockText, msgId) {

    const lines = blockText.split('\n').filter(l => l.trim().length > 0);

    let html = '';

    let inList = false;

    let listTag = 'ul';

    

    for (let line of lines) {

        let trimmed = line.trim();

        const isNumList = /^\d+\.\s+/.test(trimmed);

        const isBulletList = /^[•\-\*]\s+/.test(trimmed);

        

        if (isNumList || isBulletList) {

            const currentTag = isNumList ? 'ol' : 'ul';

            if (!inList) {

                listTag = currentTag;

                html += `<${listTag} class="ans-list">`;

                inList = true;

            } else if (listTag !== currentTag) {

                html += `</${listTag}><${currentTag} class="ans-list">`;

                listTag = currentTag;

            }

            const cleanContent = trimmed.replace(/^(\d+\.|[•\-\*])\s+/, '');

            html += `<li>${renderMarkdownInline(cleanContent, msgId)}</li>`;

        } else {

            if (inList) {

                html += `</${listTag}>`;

                inList = false;

            }

            if (trimmed.startsWith('根据《')) {

                html += `<div class="lead-line">🏛️ ${renderMarkdownInline(trimmed, msgId)}</div>`;

            } else if (trimmed.startsWith('📌')) {

                html += `<div class="source-stamp">${renderMarkdownInline(trimmed, msgId)}</div>`;

            } else {

                html += `<p class="ans-paragraph">${renderMarkdownInline(trimmed, msgId)}</p>`;

            }

        }

    }

    if (inList) {

        html += `</${listTag}>`;

    }

    return html;

}



function formatNaturalAnswer(text, msgId) {

    if (!text) return '';

    

    const hasCore = text.includes('🎯【核心解答】') || text.includes('🎯 核心解答') || text.includes('【核心解答】');

    

    if (hasCore) {

        let corePart = '';

        let refPart = '';

        let stampPart = '';

        let currentSection = 'core';

        const rawLines = text.split('\n');

        

        for (let rawLine of rawLines) {

            let line = rawLine.trim();

            if (!line) continue;

            

            if (line.includes('🎯【核心解答】') || line.includes('🎯 核心解答') || line.includes('【核心解答】')) {

                currentSection = 'core';

                continue;

            } else if (line === '---') {

                continue;

            } else if (line.includes('📖【官方依据与详细参考】') || line.includes('📖 官方依据') || line.includes('【官方依据与详细参考】')) {

                currentSection = 'ref';

                continue;

            } else if (line.startsWith('📌') || line.includes('【官方依据】：')) {

                stampPart += line + '\n';

                continue;

            }

            

            if (currentSection === 'core') {

                corePart += line + '\n';

            } else {

                refPart += line + '\n';

            }

        }

        

        let html = '';

        if (corePart.trim()) {

            html += `

                <div class="core-answer-card">

                    <div class="core-answer-title">

                        <span>🎯</span>

                        <span>核心解答：</span>

                    </div>

                    <div class="core-answer-body">

                        ${renderBlockLines(corePart, msgId)}

                    </div>

                </div>

            `;

        }

        if (refPart.trim()) {

            html += `<div class="answer-divider"></div>`;

            html += `

                <div class="ref-section">

                    <div class="ref-title">

                        <span>📖</span>

                        <span>官方依据与详细参考：</span>

                    </div>

                    <div class="ref-body">

                        ${renderBlockLines(refPart, msgId)}

                    </div>

                </div>

            `;

        }

        if (stampPart.trim()) {

            html += `<div class="source-stamp">${renderMarkdownInline(stampPart.trim(), msgId)}</div>`;

        }

        return html;

    }

    

    return `<div class="ans-body">${renderBlockLines(text, msgId)}</div>`;

}



// 语音朗读控制 (TTS Web Speech API)

function speakAnswer(btn) {

    if (!('speechSynthesis' in window)) {

        alert("当前浏览器不支持原生语音合成 API");

        return;

    }

    if (window.speechSynthesis.speaking) {

        window.speechSynthesis.cancel();

        document.querySelectorAll('.btn-speak').forEach(b => {

            b.innerHTML = '🔊 朗读';

            b.classList.remove('speaking');

        });

        return;

    }

    const bubble = btn.closest('.bubble');

    const rawText = bubble ? (bubble.getAttribute('data-raw-answer') || bubble.innerText) : '';

    const speechText = decodeURIComponent(rawText)

        .replace(/\[\d+\]/g, '')

        .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')

        .replace(/https?:\/\/[^\s]+/g, '')

        .replace(/[*#`_~]/g, '')

        .replace(/[🎯📖📌🏛️💡🔗⚡]/g, '')

        .replace(/核心解答[:：]/g, '核心解答。')

        .replace(/官方依据与详细参考[:：]/g, '官方依据。')

        .trim();



    if (!speechText) return;



    const utter = new SpeechSynthesisUtterance(speechText);

    utter.lang = 'zh-CN';

    utter.rate = 1.05;

    utter.pitch = 1.0;



    btn.innerHTML = '⏹️ 停止';

    btn.classList.add('speaking');



    utter.onend = () => {

        btn.innerHTML = '🔊 朗读';

        btn.classList.remove('speaking');

    };

    utter.onerror = () => {

        btn.innerHTML = '🔊 朗读';

        btn.classList.remove('speaking');

    };



    window.speechSynthesis.cancel();

    window.speechSynthesis.speak(utter);

}



// 一键复制回答内容

function copyAnswer(btn) {

    const bubble = btn.closest('.bubble');

    const rawText = bubble ? (bubble.getAttribute('data-raw-answer') || bubble.innerText) : '';

    if (!rawText) return;

    const cleanText = decodeURIComponent(rawText);

    navigator.clipboard.writeText(cleanText).then(() => {

        const orig = btn.innerHTML;

        btn.innerHTML = '✓ 已复制';

        btn.style.color = '#10b981';

        btn.style.borderColor = '#10b981';

        setTimeout(() => {

            btn.innerHTML = orig;

            btn.style.color = '';

            btn.style.borderColor = '';

        }, 1800);

    }).catch(() => {

        alert("复制失败，请手动选取文本复制");

    });

}



// 亮点二：麦克风语音识别输入 (STT Web Speech API)

let speechRecognizer = null;

let isRecognizing = false;



function toggleVoiceInput() {

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {

        alert("当前浏览器暂未开启语音识别 API，建议使用 Chrome 或 Edge 浏览器并允许麦克风权限！");

        return;

    }

    const micBtn = document.getElementById("mic-btn");

    const input = document.getElementById("user-input");



    if (isRecognizing && speechRecognizer) {

        speechRecognizer.stop();

        return;

    }



    try {

        speechRecognizer = new SpeechRecognition();

        speechRecognizer.lang = 'zh-CN';

        speechRecognizer.continuous = false;

        speechRecognizer.interimResults = true;



        speechRecognizer.onstart = () => {

            isRecognizing = true;

            if (micBtn) {

                micBtn.classList.add("recording");

                micBtn.title = "正在倾听普通话，请说话...再次点击停止";

            }

            if (input) input.placeholder = "正在倾听普通话提问，请直接说话...";

        };



        speechRecognizer.onresult = (event) => {

            let transcript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {

                transcript += event.results[i][0].transcript;

            }

            if (transcript && input) {

                input.value = transcript;

            }

        };



        speechRecognizer.onerror = (event) => {

            console.warn("Speech recognition error:", event.error);

            if (speechRecognizer) speechRecognizer.stop();

        };



        speechRecognizer.onend = () => {

            isRecognizing = false;

            if (micBtn) {

                micBtn.classList.remove("recording");

                micBtn.title = "点击开启普通话语音识别输入";

            }

            if (input) input.placeholder = "输入晴川政策、地标、电话或路线（如：南大门去图书馆怎么走）...";

        };



        speechRecognizer.start();

    } catch(e) {

        console.error("Speech recognition error:", e);

    }

}



// 亮点四：一键导出完整测试问答记录为 Markdown (供报告撰写使用)

function exportChatMarkdown() {

    if (sessionHistory.length === 0) {

        alert("当前对话流中尚无问答记录可供导出。请先输入几个问题进行问答交互。");

        return;

    }

    const now = new Date().toLocaleString('zh-CN');

    let md = `# 晴川校园 RAG 智能问答系统 · 实测问答全景记录\n\n`;

    md += `> **实测时间**：${now}  \n`;

    md += `> **测试学生**：宋维维（学号：20230404014）  \n`;

    md += `> **所属专业**：计算机学院 2023级人工智能专业  \n`;

    md += `> **课程项目**：《自然语言处理综合实践》（课程代码：041013815）  \n`;

    md += `> **测试轮次统计**：共计完成 ${sessionHistory.length} 轮真实校园规章与路线导航交互  \n\n`;

    md += `---\n\n## 问答实测详细记录表\n\n`;



    sessionHistory.forEach((item, idx) => {

        md += `### 第 ${idx + 1} 轮问答：${item.question}\n\n`;

        md += `- **提问时间**：\`${item.time}\`\n`;

        md += `- **检索方式**：${item.mode || '未记录'}\n- **理解后的问题**：${item.rewritten_query || item.question}\n- **所选生成模型**：${item.selected_model || '未记录'}\n- **实际提供方**：${item.actual_provider || '未记录'}\n`;

        if (item.generation_error) md += `- **回退原因**：${item.generation_error}\n`;

        md += `- **端到端响应耗时**：\`${item.latency || 12} ms\`\n`;

        md += `- **AI 助手生成答复**：\n\n${item.answer}\n\n`;
        if (item.agent) md += `- **智能办事停止原因**：${item.agent.stop_reason}\n\n\`\`\`json\n${JSON.stringify(item.agent.trace, null, 2)}\n\`\`\`\n\n`;

        if (item.citations && item.citations.length > 0) {

            md += `- **溯源支撑依据与官方链接**：\n`;

            item.citations.forEach(c => {

                md += `  * [${c.index}] 《${c.doc_name}》- ${c.title} (官网直达: ${c.url || '晴川制度文献'})\n`;

            });

            md += `\n`;

        }

        md += `---\n\n`;

    });



    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });

    const a = document.createElement("a");

    a.href = URL.createObjectURL(blob);

    a.download = `晴川RAG系统实测问答记录_${Date.now()}.md`;

    a.click();

    URL.revokeObjectURL(a.href);

}



// 一键清空对话流

function clearChatStream() {

    if (!confirm("确定要清空当前的聊天记录吗？")) return;
    if (window.CampusAgentUI) {
        if (currentWorkspaceMode === 'agent') window.CampusAgentUI.clearSession(currentChatSessionId);
        currentChatSessionId = 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
        try { sessionStorage.setItem(chatSessionStorageKey(), currentChatSessionId); } catch (_) {}
    }

    if (window.speechSynthesis) window.speechSynthesis.cancel();

    conversationEpoch++;

    if (chatRequestController) chatRequestController.abort();

    chatRequestController = null;

    sessionHistory = [];

    questionHistory = [];

    historyIndex = -1;

    allMessagesCitations = {};

    lastSuccessfulRequest = null;

    syncRequestControls();

    const stream = document.getElementById("chat-stream");

    stream.innerHTML = `

        <div class="msg-row ai">

            <div class="avatar ai">晴</div>

            <div class="bubble agent-welcome">

                <div class="provider-tag">✨ 晴川校园 RAG 智能问答系统</div>

                <div class="lead-line">同学你好！我是晴川校园智能问答助手。</div>

                <p class="ans-body">

                    对话记录已清空。您可以随时向我咨询晴川校园规章、专业设置、近期校闻、信息公开，或输入校园路线规划！

                </p>

            </div>

        </div>

    `;

    if (window.CampusAgentUI) window.CampusAgentUI.refreshWelcome();

}



function appendAiResponse(data, latencyMs = null) {

    const stream = document.getElementById("chat-stream");

    const row = document.createElement("div");

    row.className = "msg-row ai";



    const msgId = 'msg-' + Date.now() + '-' + Math.floor(Math.random() * 10000);

    allMessagesCitations[msgId] = data.citations || [];

    // Agent results have their own task renderer; ordinary QA remains below unchanged.
    if (data.agent && window.CampusAgentUI) {
        row.classList.add('agent-reply');
        row.innerHTML = `<div class="avatar ai">晴</div><div class="bubble" data-raw-answer="${encodeURIComponent(data.answer || '')}">
            <div class="bubble-header-row"><div class="provider-tag">晴川办事助手</div><div class="bubble-action-group">
            <button class="bubble-btn btn-speak" onclick="speakAnswer(this)">🔊 朗读</button>
            <button class="bubble-btn btn-copy" onclick="copyAnswer(this)">📋 复制</button></div></div>
            ${window.CampusAgentUI.renderReply(data, msgId, formatNaturalAnswer)}</div>`;
        stream.appendChild(row);
        stream.scrollTop = stream.scrollHeight;
        return;
    }


    // 模型标签与操作栏

    const latencyTag = latencyMs ? ` · ⚡ ${latencyMs}ms` : '';

    const providerHeaderHtml = `

        <div class="bubble-header-row">

            <div class="provider-tag">✨ 实际提供方：${escapeText(data.llm_provider || (MODE_NAMES[data.request_mode] ? MODE_NAMES[data.request_mode] + ' · 原句证据抽取' : '本地原句抽取'))}${latencyTag}</div>

            <div class="bubble-action-group">

                <button class="bubble-btn btn-speak" onclick="speakAnswer(this)" title="以普通话朗读答复内容">🔊 朗读</button>

                <button class="bubble-btn btn-copy" onclick="copyAnswer(this)" title="复制完整答复内容至剪贴板">📋 复制</button>

            </div>

        </div>

        <div class="request-stamp">本次检索：${escapeText(MODE_NAMES[data.request_mode] || data.request_mode || '未记录')} · 所选生成：${escapeText(data.selected_model === 'deepseek-flash' ? 'DeepSeek V4.1 Flash（deepseek-flash）' : data.selected_model || '本地原句抽取')}</div>

        ${generationNotice(data) ? `<p class="generation-notice">生成状态：${escapeText(generationNotice(data))}</p>` : ''}
        ${data.generation && Number.isInteger(data.generation.reading_count) ? `<p class="generation-notice">本次生成请求附带 ${data.generation.reading_count} 篇原文阅读资料</p>` : ''}

    `;



    // 1. NLP 命名实体识别 (NER) 标签

    let nerHtml = "";

    if (data.entities && data.entities.length > 0) {

        nerHtml = `

            <div class="ner-container">

                <div class="ner-header">🏷️ NLP 实体识别：</div>

                ${data.entities.map(e => `

                    <span class="ner-badge ${e.type}" title="${e.label}">

                        <span>${e.icon || '🏷️'}</span>

                        <span>${e.text}</span>

                        <span class="ner-type-tag">${e.label}</span>

                    </span>

                `).join('')}

            </div>

        `;

    }



    // 导航/地标横幅

    let landmarkHtml = "";

    if (data.navigation && data.navigation.from_id && data.navigation.to_id) {

        landmarkHtml = `

            <div class="fly-badge" style="background: #ffe5e5; color: #e52b38; border: 1px solid #ffccd0;" onclick="callMapRoute('${data.navigation.from_id}', '${data.navigation.to_id}')">

                🚩 3D 地图已绘制【红色导航轨迹】：${data.navigation.from_name} ➔ ${data.navigation.to_name} (点击重绘)

            </div>

        `;

    } else if (data.target_landmark) {

        landmarkHtml = `

            <div class="fly-badge" onclick="flyTo('${data.target_landmark.id}')">

                📍 3D 地图已锁定目标建筑并高亮黄色光圈：${data.target_landmark.trigger} (点击重定位)

            </div>

        `;

    }



    // 配图画廊

    let imagesHtml = "";

    if (data.images && data.images.length > 0) {

        imagesHtml = `

            <div class="chat-images-gallery">

                <div class="gallery-title">📷 官网现场配图 (${data.images.length} 张)：</div>

                <div class="gallery-grid">

                    ${data.images.map(img => `

                        <div class="img-card" onclick="window.open('${img}', '_blank')">

                            <img src="${img}" alt="现场实拍" loading="lazy" />

                            <div class="img-hint">🔍 点击查看原图</div>

                        </div>

                    `).join('')}

                </div>

            </div>

        `;

    }



    // 溯源依据

    let chunksHtml = "";

    if (data.citations && data.citations.length > 0) {

        chunksHtml = `

            <details class="rag-details">

                <summary>🔍 展开知识溯源与比对 (${data.citations.length} 篇阅读文献 · 💡 支持点击查看原文与完整文献)</summary>

                ${data.citations.map(c => `

                    <div class="chunk-box" onclick="openCitationModal('${msgId}', ${c.index})">

                        <div class="chunk-box-header">

                            <span class="chunk-box-title" title="${c.title || c.doc_name}"><strong>[${c.index}] 《${c.doc_name || c.source}》</strong>${c.title ? ' - ' + c.title : ''}</span>

                            <div class="chunk-box-actions">

                                ${c.url ? `<a href="${c.url}" target="_blank" rel="noopener noreferrer" class="chunk-link-btn" onclick="event.stopPropagation()">🔗 打开官网原文</a>` : ''}

                                <span class="chunk-view-btn">🔍 全文溯源</span>

                            </div>

                        </div>

                        <div class="chunk-box-body">${c.preview}</div>

                        <div class="chunk-box-hint">

                            <span>🏛️ ${c.used_for_answer === false ? "阅读参考" : "答案引用"}${c.published_at ? ` · 发布于 ${escapeText(c.published_at)}` : ""}</span>

                            <span>👆 点击卡片展开查看完整上下文与官方原文 ↗</span>

                        </div>

                    </div>

                `).join('')}

            </details>

        `;

    }



    // 2. 检索算法消融对比 (Ablation Benchmark)

    let ablationHtml = "";

    if (data.ablation) {

        const ab = data.ablation;

        const maxTime = Math.max(ab.tfidf.time_ms || 1, ab.bge.time_ms || 1, ab.hybrid.time_ms || 1, 100);

        const wTfidf = Math.max(12, Math.min(100, Math.round((ab.tfidf.time_ms / maxTime) * 100)));

        const wBge = Math.max(12, Math.min(100, Math.round((ab.bge.time_ms / maxTime) * 100)));

        const wHybrid = Math.max(12, Math.min(100, Math.round((ab.hybrid.time_ms / maxTime) * 100)));



        ablationHtml = `

            <details class="ablation-details">

                <summary>

                    <span>🔬 检索算法消融实测对比 (Ablation Benchmark: 统计 vs 语义 vs 混合)</span>

                    <span style="font-size: 11px; opacity: 0.85;">▼ 展开可视化柱状与耗时</span>

                </summary>

                <div class="ablation-content">

                    <div class="ablation-visual-summary">

                        <div class="ablation-bars-label">⏱️ 本题三模实测检索耗时对比（毫秒级比对）：</div>

                        <div class="ab-latency-row">

                            <span class="ab-latency-name">① TF-IDF 统计</span>

                            <div class="ab-bar-track"><div class="ab-bar-fill tfidf" style="width: ${wTfidf}%"></div></div>

                            <span class="ab-latency-val">${ab.tfidf.time_ms} ms</span>

                        </div>

                        <div class="ab-latency-row">

                            <span class="ab-latency-name">② BGE 稠密语义</span>

                            <div class="ab-bar-track"><div class="ab-bar-fill bge" style="width: ${wBge}%"></div></div>

                            <span class="ab-latency-val">${ab.bge.time_ms} ms</span>

                        </div>

                        <div class="ab-latency-row">

                            <span class="ab-latency-name">③ RRF 混合融合</span>

                            <div class="ab-bar-track"><div class="ab-bar-fill hybrid" style="width: ${wHybrid}%"></div></div>

                            <span class="ab-latency-val">${ab.hybrid.time_ms} ms</span>

                        </div>

                    </div>



                    <div class="ablation-grid">

                        <div class="ablation-card tfidf">

                            <div class="ab-card-header">

                                <span>① 传统统计检索 (TF-IDF)</span>

                                <span class="ab-time-pill">⚡ ${ab.tfidf.time_ms} ms</span>

                            </div>

                            <div class="ab-mech">${ab.tfidf.mechanism}</div>

                            ${ab.tfidf.top_chunks.map(c => `

                                <div class="ab-chunk-item">

                                    <span class="ab-chunk-score" title="TF-IDF余弦相似度">#${c.score}</span>

                                    <div class="ab-chunk-title">[${c.rank}] ${c.title}</div>

                                </div>

                            `).join('')}

                        </div>

                        <div class="ablation-card bge">

                            <div class="ab-card-header">

                                <span>② 密集语义向量 (BGE)</span>

                                <span class="ab-time-pill" style="background: #e8f5e9; color: #2e7d32;">⚡ ${ab.bge.time_ms} ms</span>

                            </div>

                            <div class="ab-mech">${ab.bge.mechanism}</div>

                            ${ab.bge.top_chunks.map(c => `

                                <div class="ab-chunk-item">

                                    <span class="ab-chunk-score" style="color: #2e7d32;" title="512维向量余弦相似度">Sim: ${c.score}</span>

                                    <div class="ab-chunk-title">[${c.rank}] ${c.title}</div>

                                </div>

                            `).join('')}

                        </div>

                        <div class="ablation-card hybrid">

                            <div class="ab-card-header">

                                <span>③ 倒数排名融合 (RRF)</span>

                                <span class="ab-time-pill" style="background: #e0f2fe; color: #0284c7;">⚡ ${ab.hybrid.time_ms} ms</span>

                            </div>

                            <div class="ab-mech">${ab.hybrid.mechanism}</div>

                            ${ab.hybrid.top_chunks.map(c => `

                                <div class="ab-chunk-item">

                                    <span class="ab-chunk-score" style="color: #0284c7;" title="倒数排名综合融合权重">RRF: ${c.score}</span>

                                    <div class="ab-chunk-title">[${c.rank}] ${c.title}</div>

                                </div>

                            `).join('')}

                        </div>

                    </div>



                    <div class="ablation-conclusion-banner">

                        💡 <strong>算法对比实验分析</strong>：BGE 神经网络通过 512 维向量高准确度把握自然语言语意；而 RRF(k=60) 融合算法则有效结合关键词字面刚性匹配与泛化语义，兼顾检准率与抗扰动能力，排序置信度最稳健！

                    </div>

                </div>

            </details>

        `;

    }



    // 3. 智能相关追问推荐 (Query Suggestion)

    let relatedHtml = "";

    if (data.related_questions && data.related_questions.length > 0) {

        relatedHtml = `

            <div class="related-box">

                <div class="related-title">💡 猜你想问（点击一键追问）：</div>

                <div class="related-list">

                    ${data.related_questions.map(rq => `

                        <button class="related-pill" onclick="sendQuickQuery('${rq.replace(/'/g, "\\'")}')">

                            🔍 ${rq}

                        </button>

                    `).join('')}

                </div>

            </div>

        `;

    }



    let modelComparisonHtml = "";
    const rawModel = data.raw_model_answer || (data.generation && data.generation.raw_model_answer);
    if (rawModel) {
        modelComparisonHtml = `
            <div class="model-fallback-compare-card">
                <div class="compare-header">
                    <span class="compare-badge ai-unverified">🤖 大模型原始生成（未通过证据严格核验）</span>
                    <span class="compare-tip">防幻觉安全回退</span>
                </div>
                <div class="compare-raw-content">${formatNaturalAnswer(rawModel, msgId + '_unverified')}</div>
                <div class="compare-divider">
                    <span>🛡️ 下方为系统为您自动兜底的【本地知识库核验通过答案与原文依据】（对照参考）：</span>
                </div>
            </div>
        `;
    }

    const formattedAnswer = formatNaturalAnswer(data.answer, msgId);



    row.innerHTML = `

        <div class="avatar ai">晴</div>

        <div class="bubble" data-raw-answer="${encodeURIComponent(data.answer || '')}">

            ${providerHeaderHtml}

            ${renderQueryAnalysis(data)}

            ${nerHtml}

            ${modelComparisonHtml}

            ${formattedAnswer}
            ${window.CampusAgentUI ? window.CampusAgentUI.renderTrace(data.agent) : ''}

            ${landmarkHtml}

            ${imagesHtml}

            ${chunksHtml}

            ${ablationHtml}

            ${relatedHtml}

        </div>

    `;

    stream.appendChild(row);

    stream.scrollTop = stream.scrollHeight;

}



function sendQuickQuery(q) {

    const input = document.getElementById("user-input");

    input.value = q;

    sendMsg();

}

window.doAsk = sendMsg;



// 亮点一：监听 3D 校园沙盘发来的“向 AI 咨询此建筑”消息

window.addEventListener("message", (e) => {

    if (e.data && e.data.type === 'ask_building' && e.data.name) {

        const query = `请介绍一下${e.data.name}及相关使用与开放规定`;

        const input = document.getElementById("user-input");

        if (input) {

            input.value = query;

            sendMsg();

        }

    }

});



// 亮点五：输入框键盘历史记忆 (↑ / ↓ 方向键调出历史提问)

function initInputHistory() {

    const input = document.getElementById("user-input");

    if (!input) return;

    input.addEventListener("keydown", (e) => {

        if (e.key === "ArrowUp") {

            if (questionHistory.length > 0 && historyIndex > 0) {

                historyIndex--;

                input.value = questionHistory[historyIndex];

                setTimeout(() => input.setSelectionRange(input.value.length, input.value.length), 0);

                e.preventDefault();

            }

        } else if (e.key === "ArrowDown") {

            if (historyIndex < questionHistory.length - 1) {

                historyIndex++;

                input.value = questionHistory[historyIndex];

                e.preventDefault();

            } else if (historyIndex === questionHistory.length - 1) {

                historyIndex = questionHistory.length;

                input.value = "";

                e.preventDefault();

            }

        }

    });

}



function updateModelPill() {

    const pill = document.getElementById("model-pill");

    if (!pill) return;

    const cfg = generationConfig();

    const key = localStorage.getItem("deepseek_api_key");

    if (cfg.useOllama) {

        pill.innerHTML = `🖥️ 本地 Ollama (${escapeText(cfg.ollamaModel)})`;

        pill.classList.add("active");

    } else if (key) {

        pill.innerHTML = `✨ 云端大模型 (${escapeText(cfg.model)})`;

        pill.classList.add("active");

    } else {

        pill.innerHTML = "✨ 晴川本地引擎";

        pill.classList.remove("active");

    }

}



// 大模型配置模态框逻辑 (云端 API + 本地 Ollama)

function openDeepSeekModal() {

    const config = generationConfig();

    const keyEl = document.getElementById("cfg-deepseek-key");

    if (keyEl) keyEl.value = localStorage.getItem("deepseek_api_key") || "";

    const cloudUrlEl = document.getElementById("cfg-cloud-url");

    if (cloudUrlEl) cloudUrlEl.value = localStorage.getItem("cloud_api_url") || "https://api.deepseek.com";

    const modelEl = document.getElementById("cfg-deepseek-model");

    if (modelEl) modelEl.value = config.model;

    const thinkingEl = document.getElementById('cfg-deepseek-thinking');

    if (thinkingEl) thinkingEl.checked = config.thinking;

    const useOllamaEl = document.getElementById('cfg-use-ollama');

    if (useOllamaEl) useOllamaEl.checked = config.useOllama;

    const ollamaUrlEl = document.getElementById('cfg-ollama-url');

    if (ollamaUrlEl) ollamaUrlEl.value = config.ollamaUrl;

    const ollamaModelEl = document.getElementById('cfg-ollama-model');

    if (ollamaModelEl) ollamaModelEl.value = config.ollamaModel;

    const migEl = document.getElementById('cfg-model-migration');

    if (migEl) migEl.textContent = modelMigrationNotice;

    syncRequestControls();

    const modal = document.getElementById("deepseek-modal");

    if (modal) modal.classList.add("show");

}

function closeDeepSeekModal() {

    const modal = document.getElementById("deepseek-modal");

    if (modal) modal.classList.remove("show");

}

function saveDeepSeekConfig() {

    if (chatRequestController) return;

    const key = document.getElementById("cfg-deepseek-key") ? document.getElementById("cfg-deepseek-key").value.trim() : "";

    const cloudUrl = document.getElementById("cfg-cloud-url") ? document.getElementById("cfg-cloud-url").value.trim() : "";

    const modelInput = document.getElementById("cfg-deepseek-model");

    const model = (modelInput && modelInput.value.trim()) ? modelInput.value.trim() : 'deepseek-flash';

    const thinking = document.getElementById('cfg-deepseek-thinking') ? document.getElementById('cfg-deepseek-thinking').checked : false;

    const useOllama = document.getElementById('cfg-use-ollama') ? document.getElementById('cfg-use-ollama').checked : false;

    const ollamaUrl = document.getElementById('cfg-ollama-url') ? document.getElementById('cfg-ollama-url').value.trim() : "";

    const ollamaModel = document.getElementById('cfg-ollama-model') ? document.getElementById('cfg-ollama-model').value.trim() : "";



    localStorage.setItem('deepseek_model', model);

    localStorage.setItem('deepseek_thinking', String(thinking));

    if (cloudUrl) localStorage.setItem('cloud_api_url', cloudUrl);

    else localStorage.removeItem('cloud_api_url');

    localStorage.setItem('use_ollama', String(useOllama));

    if (ollamaUrl) localStorage.setItem('ollama_url', ollamaUrl);

    else localStorage.removeItem('ollama_url');

    if (ollamaModel) localStorage.setItem('ollama_model', ollamaModel);

    else localStorage.removeItem('ollama_model');



    if (key) {

        localStorage.setItem("deepseek_api_key", key);

        alert(`已保存，下一次问答使用；未验证连接。所选模型：${model}。`);

    } else if (useOllama) {

        localStorage.removeItem("deepseek_api_key");

        alert(`已保存，下一次问答优先使用本地 Ollama 模型：${ollamaModel || 'deepseek-r1:latest'}；未验证连接。`);

    } else {

        localStorage.removeItem("deepseek_api_key");

        alert('已保存，下一次问答使用本地原句抽取；未验证连接。');

    }

    updateModelPill();

    closeDeepSeekModal();

}

function clearDeepSeekConfig() {

    if (chatRequestController) return;

    localStorage.removeItem("deepseek_api_key");

    localStorage.removeItem("deepseek_model");

    localStorage.removeItem('deepseek_thinking');

    localStorage.removeItem('cloud_api_url');

    localStorage.removeItem('use_ollama');

    localStorage.removeItem('ollama_url');

    localStorage.removeItem('ollama_model');

    const keyEl = document.getElementById("cfg-deepseek-key");

    if (keyEl) keyEl.value = "";

    updateModelPill();

    alert("已清空 API Key 与模型配置，系统恢复为内置纯净离线抽取引擎。");

    closeDeepSeekModal();

}



// 知识库概况模态框逻辑

function openKbStatsModal() {

    document.getElementById("stats-modal").classList.add("show");

}

function closeKbStatsModal() {

    document.getElementById("stats-modal").classList.remove("show");

}



// 评测报表模态框与可视化卡片渲染

let lastBenchmarkData = [];

async function renderAnswerBenchmark() {

    const target = document.getElementById('answer-benchmark-summary');

    if (!target) return;

    try {

        const response = await fetch('/api/answer_benchmark');

        const result = await response.json();

        if (!response.ok || result.status !== 'ok') {

            target.textContent = '尚无可用的答案评测结果，请先运行答案质量评测。';

            return;

        }

        const percentage = (value, count) => count ? `${(Number(value) * 100).toFixed(1)}%` : '—';

        const rows = Object.entries(result.data).map(([mode, report]) => `<tr><td>${escapeText(mode)}</td><td>${report.passed_count}/${report.total_cases}</td><td>${percentage(report.expected_answer_accuracy, report.answerable_count)}</td><td>${percentage(report.unknown_refusal_accuracy, report.unknown_count)}</td><td>${percentage(report.clarification_accuracy, report.clarification_count)}</td></tr>`).join('');

        target.innerHTML = `<strong>答案级参考事实与证据检查</strong><div style="overflow-x:auto"><table class="benchmark-table"><thead><tr><th>模式</th><th>通过题数</th><th>可回答题通过率</th><th>未知题拒答</th><th>歧义澄清</th></tr></thead><tbody>${rows}</tbody></table></div><p>下方为检索级指标；两类指标含义不同。样例集检查不代表真实问题准确率，自动检查也不等同于完整语义核验。</p>`;

    } catch (error) {

        target.textContent = '答案评测结果暂时无法读取。';

    }

}



async function openBenchmarkModal() {

    document.getElementById("modal-mask").classList.add("show");

    await renderAnswerBenchmark();

    try {

        const res = await fetch("/api/benchmark");

        const json = await res.json();

        if (json.status === "ok" && json.data.length > 0) {

            lastBenchmarkData = json.data;



            // 1. 渲染可视化柱状卡片对比图

            const visContainer = document.getElementById("benchmark-visual-container");

            if (visContainer) {

                const colors = {

                    "TF-IDF": { bg: "#fef3c7", border: "#f59e0b", bar: "#f59e0b", badge: "传统基线" },

                    "BGE": { bg: "#dcfce7", border: "#10b981", bar: "#10b981", badge: "神经网络" },

                    "Hybrid": { bg: "#e0f2fe", border: "#3b82f6", bar: "#3b82f6", badge: "混合精排" }

                };

                visContainer.innerHTML = json.data.map(r => {

                    let key = "Hybrid";

                    if (r.model_name.includes("TF-IDF")) key = "TF-IDF";

                    else if (r.model_name.includes("BGE")) key = "BGE";

                    const c = colors[key];

                    return `

                        <div class="bench-vis-card" style="border-top: 3px solid ${c.border};">

                            <div class="bench-vis-title">

                                <span>${r.model_name.split('(')[0]}</span>

                                <span class="bench-vis-badge" style="background: ${c.bg}; color: ${c.border}; font-weight: bold;">${c.badge}</span>

                            </div>

                            <div class="bench-metric-row">

                                <div class="bench-metric-header">

                                    <span>Hit@1 知识库命中率</span>

                                    <strong>${r.hit_at_1}%</strong>

                                </div>

                                <div class="bench-metric-bar-bg"><div class="bench-metric-bar-val" style="width: ${r.hit_at_1}%; background: ${c.bar};"></div></div>

                            </div>

                            <div class="bench-metric-row">

                                <div class="bench-metric-header">

                                    <span>MRR (倒数排名)</span>

                                    <strong>${r.mrr}</strong>

                                </div>

                                <div class="bench-metric-bar-bg"><div class="bench-metric-bar-val" style="width: ${Math.round(r.mrr * 100)}%; background: ${c.bar};"></div></div>

                            </div>

                            <div class="bench-metric-row">

                                <div class="bench-metric-header">

                                    <span>NDCG@3 (质量增益)</span>

                                    <strong>${r.ndcg_at_3 ?? '-'}</strong>

                                </div>

                                <div class="bench-metric-bar-bg"><div class="bench-metric-bar-val" style="width: ${Math.round((r.ndcg_at_3 ?? 0) * 100)}%; background: ${c.bar};"></div></div>

                            </div>

                            <div style="margin-top: 6px; font-size: 10.5px; color: var(--text-muted); display: flex; justify-content: space-between;">

                                <span>延迟: <strong>${r.avg_latency_ms} ms</strong></span>

                                <span>Hit@5: <strong>${r.hit_at_5}%</strong></span>

                            </div>

                        </div>

                    `;

                }).join('');

            }



            // 2. 渲染完整数据表格 (含 NDCG)

            const tbody = document.getElementById("benchmark-tbody");

            tbody.innerHTML = json.data.map(r => `

                <tr>

                    <td><strong>${r.model_name}</strong></td>

                    <td style="color: #1e5a44; font-weight: bold;">${r.hit_at_1}%</td>

                    <td>${r.hit_at_3}%</td>

                    <td>${r.hit_at_5}%</td>

                    <td><strong>${r.mrr}</strong></td>

                    <td style="color: #0284c7; font-weight: 600;">${r.ndcg_at_3 !== undefined ? r.ndcg_at_3 : '-'}</td>

                    <td style="color: #0284c7; font-weight: 600;">${r.ndcg_at_5 !== undefined ? r.ndcg_at_5 : '-'}</td>

                    <td>${r.avg_latency_ms} ms</td>

                </tr>

            `).join('');

        }

    } catch(e) {

        console.error(e);

    }

}



function closeBenchmarkModal() {

    document.getElementById("modal-mask").classList.remove("show");

}



// 一键复制 Markdown 评测表格（方便写报告）

function copyBenchmarkMarkdown() {

    if (!lastBenchmarkData || lastBenchmarkData.length === 0) {

        alert("评测数据尚未就绪");

        return;

    }

    let lines = [

        "| 检索模型架构 | Hit@1 (%) | Hit@3 (%) | Hit@5 (%) | MRR | NDCG@3 | NDCG@5 | 平均延迟(ms) |",

        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"

    ];

    for (const r of lastBenchmarkData) {

        lines.push(`| **${r.model_name}** | ${r.hit_at_1}% | ${r.hit_at_3}% | ${r.hit_at_5}% | ${r.mrr} | ${r.ndcg_at_3 || '-'} | ${r.ndcg_at_5 || '-'} | ${r.avg_latency_ms} ms |`);

    }

    const md = lines.join("\n");

    navigator.clipboard.writeText(md).then(() => {

        alert("✓ 评测对比 Markdown 表格已复制到剪贴板，可直接粘贴至测试报告或 PPT 中！");

    }).catch(() => {

        alert("请手动复制表格内容");

    });

}



// 动态加载知识库切块统计并刷新右上角按钮

async function fetchKbStats() {

    try {

        const res = await fetch("/api/kb_stats");

        const data = await res.json();

        if (data && data.stats && data.stats.total_chunks) {

            const btn = document.getElementById("kb-stats-btn");

            if (btn) {

                btn.innerHTML = `📚 知识库概况 (${data.stats.total_chunks.toLocaleString()}块)`;

            }

        }

    } catch(e) {

        console.error("fetchKbStats error:", e);

    }

}



window.addEventListener("DOMContentLoaded", () => {

    setMode(currentMode);

    syncRequestControls();

    fetchKbStats();

    initInputHistory();

});



// 增量同步新闻

async function syncNews() {

    if (!confirm("确定要增量同步晴川官网四大专栏最新图文动态吗？")) return;

    const loadingRow = appendMessage("ai", "正在连接晴川官网增量同步最新动态与配图...");

    try {

        const res = await fetch("/api/sync_news", { method: "POST" });

        const json = await res.json();

        loadingRow.remove();

        alert(json.message);

        fetchKbStats();

        location.reload();

    } catch(e) {

        loadingRow.remove();

        alert("同步失败，请检查网络连接");

    }

}





async function testCloudApi() {

    const keyInput = document.getElementById('cfg-deepseek-key');

    const key = keyInput ? keyInput.value.trim() : '';

    const cloudUrlInput = document.getElementById('cfg-cloud-url');

    const cloudUrl = cloudUrlInput ? cloudUrlInput.value.trim() : 'https://api.deepseek.com';

    const model = (document.getElementById('cfg-deepseek-model')?.value || 'deepseek-flash').trim();

    const statusEl = document.getElementById('test-cloud-status') || document.getElementById('test-key-status');

    const btn = document.getElementById('test-cloud-btn') || document.getElementById('test-key-btn');

    if (!key) {

        if (statusEl) {

            statusEl.textContent = '❌ 请先输入 API Key 再进行测试';

            statusEl.style.color = '#e53e3e';

        }

        return;

    }

    if (statusEl) {

        statusEl.textContent = '⏳ 正在向云端 API 端点验证连接...';

        statusEl.style.color = '#3182ce';

    }

    if (btn) btn.disabled = true;

    try {

        const resp = await fetch('/api/test_deepseek', {

            method: 'POST',

            headers: {'Content-Type': 'application/json'},

            body: JSON.stringify({api_key: key, model: model, api_url: cloudUrl})

        });

        const data = await resp.json();

        if (statusEl) {

            if (data.ok) {

                statusEl.textContent = '✅ ' + (data.message || '连接成功！API Key 有效');

                statusEl.style.color = '#38a169';

            } else {

                statusEl.textContent = '❌ ' + (data.message || '连接失败');

                statusEl.style.color = '#e53e3e';

            }

        }

    } catch (err) {

        if (statusEl) {

            statusEl.textContent = '❌ 请求异常: ' + (err.message || '无法连接测试端点');

            statusEl.style.color = '#e53e3e';

        }

    } finally {

        if (btn) btn.disabled = false;

    }

}

const testDeepSeekKey = testCloudApi;



async function testOllama() {

    const urlInput = document.getElementById('cfg-ollama-url');

    const ollamaUrl = urlInput ? urlInput.value.trim() : 'http://localhost:11434';

    const modelInput = document.getElementById('cfg-ollama-model');

    const model = (modelInput?.value || 'deepseek-r1:latest').trim();

    const statusEl = document.getElementById('test-ollama-status');

    const btn = document.getElementById('test-ollama-btn');



    if (statusEl) {

        statusEl.textContent = '⏳ 正在探测本地 Ollama 服务与模型...';

        statusEl.style.color = '#3182ce';

    }

    if (btn) btn.disabled = true;

    try {

        const resp = await fetch('/api/test_ollama', {

            method: 'POST',

            headers: {'Content-Type': 'application/json'},

            body: JSON.stringify({ollama_url: ollamaUrl, model: model})

        });

        const data = await resp.json();

        if (statusEl) {

            if (data.ok) {

                statusEl.textContent = '✅ ' + (data.message || '本地 Ollama 连接正常！');

                statusEl.style.color = '#38a169';

            } else {

                statusEl.textContent = '⚠️ ' + (data.message || '连接失败');

                statusEl.style.color = '#d97706';

            }

        }

    } catch (err) {

        if (statusEl) {

            statusEl.textContent = '❌ 探测异常: ' + (err.message || '无法连接');

            statusEl.style.color = '#e53e3e';

        }

    } finally {

        if (btn) btn.disabled = false;

    }

}



// ----------------------------------------------------

// SQLite 数据库历史问答与审计管理

// ----------------------------------------------------

function openHistoryModal() {
    if (currentWorkspaceMode === 'agent' && window.CampusAgentUI) {
        window.CampusAgentUI.openHistory();
        return;
    }

    const modal = document.getElementById("history-modal");

    if (modal) modal.classList.add("show");

    refreshHistoryList();

}



function closeHistoryModal() {

    const modal = document.getElementById("history-modal");

    if (modal) modal.classList.remove("show");

}



let selectedHistorySessionId = null;

function startNewChatWindow(fromModal = false) {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (chatRequestController) chatRequestController.abort();
    chatRequestController = null;
    conversationEpoch++;
    sessionHistory = [];
    questionHistory = [];
    historyIndex = -1;
    allMessagesCitations = {};
    lastSuccessfulRequest = null;
    syncRequestControls();

    // 生成全新独立的会话 ID
    currentChatSessionId = "session_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 6);
    try {
        if (typeof sessionStorage !== 'undefined') {
            sessionStorage.setItem(chatSessionStorageKey(), currentChatSessionId);
        }
    } catch(e) {}

    const stream = document.getElementById("chat-stream");
    if (stream) {
        stream.innerHTML = `
            <div class="msg-row ai">
                <div class="avatar ai">晴</div>
                <div class="bubble agent-welcome">
                    <p>✨ <strong>已开启全新的独立对话窗口！</strong></p>
                    <p style="margin-top: 4px; font-size: 12px; color: var(--text-muted);">会话标识：<code>${escapeText(currentChatSessionId)}</code>（具备完全独立的多轮上下文与记忆）</p>
                    <p style="margin-top: 8px; font-size: 13.5px;">您可以开始全新的校园咨询，例如：</p>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px;">
                        <span class="quick-pill" onclick="sendQuickQuery('晴川董事长是谁？')">🔍 晴川董事长是谁？</span>
                        <span class="quick-pill" onclick="sendQuickQuery('图书馆几点开门？')">🔍 图书馆几点开门？</span>
                        <span class="quick-pill" onclick="sendQuickQuery('操场在哪？')">🔍 操场在哪？</span>
                    </div>
                </div>
            </div>
        `;
    }

    if (window.CampusAgentUI) window.CampusAgentUI.refreshWelcome();
    if (fromModal) {
        selectedHistorySessionId = currentChatSessionId;
        refreshHistoryList();
    }
}

function selectHistorySession(sessionId) {
    selectedHistorySessionId = sessionId;
    renderTwoColumnHistory();
}

function restoreAgentSession(sessionId, records) {
    if (currentWorkspaceMode !== 'agent') return false;
    if (chatRequestController) { alert('请等当前回复结束后再切换会话。'); return false; }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    conversationEpoch++;
    currentChatSessionId = sessionId;
    try { sessionStorage.setItem(chatSessionStorageKey(), sessionId); } catch (_) {}
    allMessagesCitations = {};
    lastSuccessfulRequest = null;
    questionHistory = records.map(r => r.question);
    historyIndex = questionHistory.length;
    sessionHistory = records.map(r => ({question:r.question, context_question:r.question,
        answer:r.result.answer, citations:r.result.citations || [], agent:r.result.agent,
        mode:'hybrid', actual_provider:r.result.llm_provider, time:r.created_at}));
    const stream = document.getElementById('chat-stream');
    stream.replaceChildren();
    document.getElementById('user-input').value = '';
    records.forEach(r => {
        appendMessage('user', r.question);
        window.CampusAgentUI.remember(r.result);
        appendAiResponse(r.result);
    });
    if (!records.length) appendMessage('ai','已切换办事会话，请告诉我你要办的事。');
    syncRequestControls();
    return true;
}

function switchToSession(sessionId) {
    if (chatRequestController) chatRequestController.abort();
    chatRequestController = null;
    conversationEpoch++;
    lastSuccessfulRequest = null;
    questionHistory = [];
    historyIndex = -1;
    allMessagesCitations = {};
    const records = cachedHistoryRecords.filter(r => (r.session_id || 'web_session') === sessionId).sort((a,b) => a.id-b.id);
    sessionHistory = records.map(r => {
        let citations = [];
        try { citations = JSON.parse(r.citations_json || '[]'); } catch (_) {}
        return {question:r.user_query, context_question:r.rewritten_query || r.user_query, answer:r.answer,
            mode:r.mode, citations, actual_provider:r.llm_provider, latency:r.latency_ms, time:r.created_at};
    });
    const stream = document.getElementById('chat-stream');
    if (stream) {
        stream.innerHTML = '';
        for (const record of sessionHistory) {
            appendMessage('user', record.question);
            appendAiResponse({answer:record.answer,citations:record.citations,llm_provider:record.actual_provider,request_mode:record.mode},record.latency);
        }
        if (!sessionHistory.length) appendMessage('ai','已切换会话，可以继续校园咨询。');
    }
    currentChatSessionId = sessionId;
    syncRequestControls();
    try {
        if (typeof sessionStorage !== 'undefined') {
            sessionStorage.setItem(chatSessionStorageKey(), currentChatSessionId);
        }
    } catch(e) {}
    alert("已将主界面切换至该会话窗口！您可以在主界面输入框继续进行此窗口的多轮问答。");
    closeHistoryModal();
}

async function deleteSessionHistory(sessionId) {
    if (!confirm(`确定要删除此会话窗口 (${sessionId}) 的所有历史记录吗？`)) return;
    try {
        const res = await fetch(`/api/history?session_id=${encodeURIComponent(sessionId)}`, { method: "DELETE" });
        const json = await res.json();
        if (selectedHistorySessionId === sessionId) {
            selectedHistorySessionId = null;
        }
        refreshHistoryList();
    } catch(err) {
        alert("删除失败: " + err.message);
    }
}

function renderTwoColumnHistory() {
    const sessionsCol = document.getElementById("history-sessions-col");
    const turnsCol = document.getElementById("history-turns-col");
    const countEl = document.getElementById("history-total-count");
    if (!sessionsCol || !turnsCol) return;

    const records = cachedHistoryRecords || [];

    // Group records by session_id
    const sessionsMap = new Map();
    // Sort records chronologically (id ASC) so turns are sequential
    const sortedRecords = [...records].sort((a, b) => a.id - b.id);
    for (let r of sortedRecords) {
        const sid = r.session_id || 'web_session';
        if (!sessionsMap.has(sid)) {
            sessionsMap.set(sid, {
                sessionId: sid,
                firstQuestion: r.user_query,
                latestTime: r.created_at || '',
                turns: []
            });
        }
        const s = sessionsMap.get(sid);
        s.turns.push(r);
        s.latestTime = r.created_at || s.latestTime;
    }

    const sessions = Array.from(sessionsMap.values());
    // Sort sessions so most recent is first
    sessions.sort((a, b) => {
        const tA = a.turns[a.turns.length - 1]?.id || 0;
        const tB = b.turns[b.turns.length - 1]?.id || 0;
        return tB - tA;
    });

    if (countEl) {
        countEl.innerText = `本地 SQLite 数据库共记录 ${records.length} 条问答 (${sessions.length} 个独立对话窗口)`;
    }

    // Determine currently selected session
    if (!selectedHistorySessionId || !sessionsMap.has(selectedHistorySessionId)) {
        if (sessionsMap.has(currentChatSessionId)) {
            selectedHistorySessionId = currentChatSessionId;
        } else if (sessions.length > 0) {
            selectedHistorySessionId = sessions[0].sessionId;
        } else {
            selectedHistorySessionId = currentChatSessionId;
        }
    }

    // 1. Render Left Column (Sessions)
    let leftHtml = `
        <div class="session-col-header">
            <span>🗂️ 对话窗口 (${sessions.length})</span>
            <button class="btn-new-session-mini" onclick="startNewChatWindow(true)" title="新建一个完全独立的会话窗口">➕ 新建窗口</button>
        </div>
    `;

    if (sessions.length === 0) {
        leftHtml += `
            <div class="session-item-card active current">
                <div class="session-item-title">💬 新对话窗口</div>
                <div class="session-item-meta">0 轮问答 · 当前活跃</div>
                <span class="session-active-pill">🟢 当前活跃窗口</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); padding: 16px 8px; text-align: center;">
                暂无历史记录，在主界面输入框提问即可建立多轮对话轨迹。
            </div>
        `;
    } else {
        if (!sessionsMap.has(currentChatSessionId)) {
            leftHtml += `
                <div class="session-item-card ${selectedHistorySessionId === currentChatSessionId ? 'active' : ''} current" onclick="selectHistorySession('${currentChatSessionId}')">
                    <div class="session-item-title">💬 新建窗口 (等待首次提问...)</div>
                    <div class="session-item-meta">0 轮问答 · 刚刚创建</div>
                    <span class="session-active-pill">🟢 当前活跃窗口</span>
                </div>
            `;
        }
        for (let s of sessions) {
            const isCurrent = s.sessionId === currentChatSessionId;
            const isSelected = s.sessionId === selectedHistorySessionId;
            const timeBrief = s.latestTime ? s.latestTime.slice(5, 16) : '';
            const titleSnippet = s.firstQuestion.length > 16 ? s.firstQuestion.slice(0, 16) + '...' : s.firstQuestion;
            leftHtml += `
                <div class="session-item-card ${isSelected ? 'active' : ''} ${isCurrent ? 'current' : ''}" onclick="selectHistorySession('${s.sessionId}')">
                    <div class="session-item-title" title="${escapeText(s.firstQuestion)}">
                        💬 ${escapeText(titleSnippet)}
                    </div>
                    <div class="session-item-meta">
                        <span>共 ${s.turns.length} 轮问答</span>
                        <span>${escapeText(timeBrief)}</span>
                    </div>
                    ${isCurrent ? '<span class="session-active-pill">🟢 当前活跃窗口</span>' : '<span class="session-history-pill">📜 历史窗口</span>'}
                </div>
            `;
        }
    }
    sessionsCol.innerHTML = leftHtml;

    // 2. Render Right Column (Turns of selected session)
    const selectedSession = sessionsMap.get(selectedHistorySessionId);
    if (!selectedSession || selectedSession.turns.length === 0) {
        turnsCol.innerHTML = `
            <div class="turns-col-header">
                <div>
                    <div class="turns-col-title">💬 新建对话窗口</div>
                    <div class="turns-col-sub">Session ID: <code>${escapeText(selectedHistorySessionId)}</code> · 尚未提问</div>
                </div>
            </div>
            <div style="text-align: center; color: var(--text-muted); padding: 50px 20px;">
                <p style="font-size: 15px; font-weight: 600; color: #475569;">该窗口暂无问答记录</p>
                <p style="font-size: 13px; margin-top: 6px;">关闭本弹窗后，在主界面输入框发送消息，即可在此窗口内记录连续的多轮问答！</p>
            </div>
        `;
        return;
    }

    let rightHtml = `
        <div class="turns-col-header">
            <div class="turns-col-title-group">
                <div class="turns-col-title">💬 窗口话题：${escapeText(selectedSession.firstQuestion)}</div>
                <div class="turns-col-sub">Session ID: <code>${escapeText(selectedSession.sessionId)}</code> · 共 ${selectedSession.turns.length} 轮连续问答</div>
            </div>
            <div class="turns-col-actions" style="display: flex; align-items: center; gap: 8px;">
                ${selectedSession.sessionId !== currentChatSessionId ? `<button class="btn-switch-window" onclick="switchToSession('${selectedSession.sessionId}')">🔄 切换至此窗口</button>` : '<span class="session-active-pill">🟢 当前活跃中</span>'}
                <button class="btn-delete-session" onclick="deleteSessionHistory('${selectedSession.sessionId}')">🗑️ 删除此窗口</button>
            </div>
        </div>
    `;

    for (let idx = 0; idx < selectedSession.turns.length; idx++) {
        const item = selectedSession.turns[idx];
        const turnNum = item.turn_index || (idx + 1);
        const modeName = MODE_NAMES[item.mode] || item.mode;
        const rewrittenHtml = item.rewritten_query && item.rewritten_query !== item.user_query
            ? `<div style="font-size: 12px; color: #0284c7; background: #f0f9ff; padding: 4px 8px; border-radius: 4px; margin-bottom: 6px;">🔗 上下文指代消解与意图重写：<strong>${escapeText(item.rewritten_query)}</strong></div>` : '';
        const refusedBadge = item.refused ? '<span class="db-pill refused">已规范拒答</span>' : '';
        const safeQuery = escapeText(item.user_query).replace(/'/g, "\\'");

        rightHtml += `
            <div class="turn-detail-card">
                <div class="turn-header-row">
                    <span class="turn-index-pill">第 ${turnNum} 轮问答</span>
                    <span class="turn-id-tag">#${turnNum}</span>
                    <span class="db-pill mode">${escapeText(modeName)}</span>
                    <span class="db-pill latency">${item.latency_ms}ms</span>
                    ${refusedBadge}
                    <span class="db-pill global-id" title="SQLite 数据库自增主键：全库累计第 ${item.id} 条记录">全局记录 #${item.id}</span>
                    <span class="turn-time">${escapeText(item.created_at || '')}</span>
                </div>
                <div class="turn-query-row">
                    <span class="turn-q-icon">❓</span>
                    <strong class="turn-q-text">${escapeText(item.user_query)}</strong>
                </div>
                ${rewrittenHtml}
                <div class="turn-ans-box">${escapeText(item.answer)}</div>
                <div class="turn-footer-row">
                    <span class="db-pill provider">实际提供方: ${escapeText(item.llm_provider || '本地原句抽取')}</span>
                    <button class="btn-restore-turn" onclick="restoreDbQuestion('${safeQuery}')">🔍 填入输入框</button>
                </div>
            </div>
        `;
    }
    turnsCol.innerHTML = rightHtml;
}

async function refreshHistoryList() {
    const sessionsCol = document.getElementById("history-sessions-col");
    const turnsCol = document.getElementById("history-turns-col");
    if (!sessionsCol || !turnsCol) return;
    sessionsCol.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 30px;">正在加载窗口列表...</div>';
    turnsCol.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 30px;">正在读取问答消息...</div>';
    try {
        const res = await fetch("/api/history?limit=150");
        const json = await res.json();
        cachedHistoryRecords = json.history || [];
        renderTwoColumnHistory();
    } catch(err) {
        sessionsCol.innerHTML = `<div style="color: #e53e3e; padding: 20px;">读取失败: ${escapeText(err.message)}</div>`;
        turnsCol.innerHTML = '';
    }
}

async function clearDbHistory() {

    if (!confirm("确定要清空本地 SQLite 数据库中的全部历史记录吗？此操作不可逆。")) return;

    try {

        const res = await fetch("/api/history", { method: "DELETE" });

        const json = await res.json();

        alert(`已成功清空 SQLite 数据库，共清除 ${json.deleted_count || 0} 条记录！`);

        refreshHistoryList();

    } catch (e) {

        alert("清空失败：" + (e.message || "请检查后端服务"));

    }

}



function restoreDbQuestion(q) {

    const input = document.getElementById("user-input");

    if (input) {

        input.value = q;

        input.focus();

    }

    closeHistoryModal();

}

