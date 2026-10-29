"""问题—证据精排与事实槽位校验；分数是启发式相关性而非概率。"""
import os
import re
import logging
from pathlib import Path
from functools import lru_cache
from core.query_understanding import analyze_query, fact_slots, GRADE_PATTERN, ROLE_GROUPS

INTENT_TERMS = {
    'time': ('时间', '开放', '闭馆', '截止', '提交', '周五', '周日', '每日', '每天', '停止', '受理', '期满'),
    'duration': ('借期', '期限', '天', '工作日', '小时', '时长', '分钟', '预约'),
    'amount': ('元', '金额', '收费', '赔偿', '滞还金', '资助', '预算'),
    'eligibility': ('条件', '资格', '及格', '挂科', '必须', '不得', '门槛', '要求', '成绩'),
    'location': ('楼', '层', '位于', '坐落', '旁', '地址', '风景区', '室'),
    'contact': ('电话', '联系', '传真', '号码'), 'website': ('http', '官网', '网站', '主页', '网址'),
    'major': ('专业', '开设', '本科', '工程', '技术', '智能'),
    'quota': ('限借', '册', '上限', '额度', '次数', '次'), 'procedure': ('申请', '提交', '材料', '审核', '办理', '申报')}
SOURCE_PREFERENCES = {'library': ('library', 'campus_landmarks'), 'scholarship': ('scholarship',),
    'course_selection': ('course_selection',), 'laboratory': ('laboratory',), 'student_status': ('student_status',),
    'campus_organizations': ('campus_organizations', 'school_overview', 'office_contacts'),
    'campus_landmarks': ('campus_landmarks', 'school_overview'),
    'school_overview': ('school_overview', 'campus_culture')}


def plain_text(text):
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    def _link_clean(m):
        label = m.group(1).strip()
        url = m.group(2).strip()
        if not label or label == url:
            return url
        return f"{label}（{url}）"
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link_clean, text)
    return re.sub(r'[*`#]', '', text).strip(' \t\r\n-')


def grams(text):
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text.lower())
    return {text[i:i+2] for i in range(len(text)-1)}


def lexical_overlap(query, text):
    q = grams(query)
    return len(q & grams(text)) / max(1, len(q))


def sentence_units(text):
    return [plain_text(s) for s in re.split(r'(?<=[。！？])|\n+', text) if len(plain_text(s)) >= 5]


def _specific_supported(query, text):
    specific = ('国家励志奖学金', '国家奖学金', '国家助学金', '晴川助学金', '馆长', '手机号',
        '翻新', '预算', '停车', '退款', '补考', '重修', '博士', '明年', '明天',
        '一等奖', '二等奖', '三等奖', '甲等', '乙等', '丙等', '电子阅览', '考研', '续借',
        'VR', '游戏中心', '地下三层', 'GPA', '初评', '终审', '第一轮', '第二轮', '第三轮')
    if any(term in query and term not in text for term in specific):
        return False
    if any(year.rstrip('年') not in text for year in re.findall(r'20\d{2}年?', query)):
        return False
    if '截止' in query and not re.search(r'截止|前提交|前受理|前.*报送', text):
        return False
    for trigger, required in ((('挂科', '不及格'), ('挂科', '不及格')), (('借多久', '借多少天', '借期'), ('借',)),
                              (('发放', '发奖', '发到', '到账', '打到'), ('发放', '划拨', '发奖', '到账')), (('公示',), ('公示',)),
                              (('借还',), ('借还',)), (('预约',), ('预约',)), (('学费',), ('学费',)),
                              (('加工费',), ('加工费',)), (('逾期',), ('逾期', '滞还'))):
        if any(w in query for w in trigger) and not any(w in text for w in required):
            return False
    if '周末' in query and not any(w in text for w in ('周末', '周日', '周六', '每日', '每天', '全天')):
        return False
    return not ('节假日' in query and '节假日' not in text)


def _slots_supported(slots, unit, contextual_subjects=()):
    """Bind constrained values to the same local fact, not a nearby total."""
    conditions = slots['conditions']
    grades = conditions.get('grade', [])
    if len(grades) > 1:
        return False  # The planner must validate these as independent questions.
    role = conditions.get('role')
    if role and not any(alias in unit for alias in ROLE_GROUPS[role]):
        if not (role == '本科生' and any(a in unit for a in ('本科', '本专科', '学生'))):
            return False
    if role and slots['attribute'] in ('quota', 'duration'):
        aliases = ROLE_GROUPS[role] + (('本科', '本专科', '学生') if role == '本科生' else ())
        quantity = r'\d+\s*(?:册|本|次)' if slots['attribute'] == 'quota' else r'\d+\s*(?:天|工作日|小时|分钟|月|年)'
        if not any(any(a in fact for a in aliases) and re.search(quantity, fact)
                   for fact in re.split(r'[，,；;]', unit)):
            return False
    if slots['attribute'] != 'amount':
        return True
    subjects = slots['subject']
    specific_subjects = [s for s in subjects if s not in ('奖学金', '助学金')]
    grade_aliases = {'甲等': '一等奖', '乙等': '二等奖', '丙等': '三等奖',
                     '一等': '一等奖', '二等': '二等奖', '三等': '三等奖'}
    offset = 0
    for fact in re.split(r'[，,；;]', unit):
        fact_offset = offset
        offset += len(fact) + 1
        if grades and re.search(r'总额|总计|共计|累计|合计|总金额', fact):
            continue
        for amount in re.finditer(r'\d+(?:\.\d+)?\s*(?:万?元|倍)', fact):
            # Check each currency value against the nearest preceding label.
            # Other values in a coordinated sentence do not qualify it.
            if grades:
                preceding = re.findall(GRADE_PATTERN, fact[:amount.start()])
                if not preceding or grade_aliases.get(preceding[-1], preceding[-1]) != grade_aliases.get(grades[0], grades[0]):
                    continue
            if specific_subjects:
                # A subject heading carries through descriptive commas until
                # another explicit subject replaces it.
                prior = unit[:fact_offset + amount.start()]
                prior_subjects = fact_slots(prior)['subject']
                if not prior_subjects:
                    competing = [s for s in fact_slots(unit)['subject'] if s not in subjects]
                    if competing or not any(s in contextual_subjects for s in specific_subjects):
                        continue
                    return True
                nearest = max(prior_subjects, key=prior.rfind)
                if nearest not in specific_subjects:
                    continue
            return True
    return False


def _property_relation_supported(query, intent, topic, unit):
    if intent == 'time' and (re.search(r'闭馆|关门|开馆|开放时间|开闭馆', query)
                             or topic in ('library', 'laboratory') and '几点' in query):
        clock = r'\d{1,2}[:：]\d{2}'
        if not re.search(clock, unit):
            return False
        time_range = clock + r'\s*[—–\-~～至到]+\s*' + clock
        relation = (r'(?:开放时间|开闭馆时间|闭馆时间|开馆时间)\s*[:：]?\s*' + clock
                    + '|' + clock + r'\s*(?:闭馆|关门|开馆|开放)')
        if not (re.search(relation, unit) or re.search(time_range, unit)
                and re.search(r'开放|闭馆|开馆|关门|营业', unit)):
            return False
    if intent == 'location':
        if re.search(r'食堂|餐饮中心', query) and not re.search(r'几层|多少层|几楼', query):
            if not re.search(r'(?:食堂|餐饮中心)[^，。；]{0,10}(?:位于|坐落|地处|地址|靠近|临近|毗邻|在[^，。；]{0,20}(?:旁|侧|区|栋|楼))', unit):
                return False
        if re.search(r'几层|多少层|几楼', query):
            return bool(re.search(r'\d+\s*(?:层|楼)|[一二三四五六七八九十]+\s*(?:层|楼)', unit))
        return bool(re.search(r'位于|在|坐落|地址\s*[:：]|地处|路|临[^。]{1,25}(?:门|路|湖|楼|栋|区)|功能导览|运动区|主看台|跑道|足球场|操场|场馆|体育馆', unit))
    return True


def is_topic_lookup(query):
    """A bare topic requests article coverage, rather than one specific fact."""
    return (2 <= len(query.strip()) <= 40
            and analyze_query(query)['intent'] == 'general'
            and not re.search(r'[？?，,；;]|什么|怎么|如何|多少|哪里|是否|哪|吗|呢|为何|为什么', query))


def select_evidence(query, chunks, max_sentences=3):
    analysis = analyze_query(query)
    query = analysis['rewritten_query']
    slots = analysis['slots']
    intent, topic, subjects = slots['attribute'], analysis['topic'], slots['subject']
    terms = INTENT_TERMS.get(intent, ())
    matches = []
    for index, chunk in enumerate(chunks):
        text = chunk.get('text', '')
        context = chunk.get('title', '') + '\n' + text + '\n' + chunk.get('context_text', '')
        anchored_subjects = {'library': ('图书馆',), 'laboratory': ('实验室', '机房')}.get(chunk.get('source'), ())
        if subjects and not any(s in context or s in anchored_subjects for s in subjects):
            continue
        # 召回后展开同节窗口，补齐断在块边界外的主语、限制条件和完整句子。
        body = chunk.get('context_text') or text
        body = re.split(r'核心新闻正文[^\n]*\n', body, maxsplit=1)[-1]
        for unit in sentence_units(body):
            # FAQ headings are questions, never factual answer evidence.
            if (unit == plain_text(chunk.get('title', ''))
                    or re.match(r'^>?\s*本知识库(?:收录|包含|涵盖)', unit)
                    or unit.rstrip().endswith(('？', '?'))):
                continue
            school_nature = re.search(r'(?:什么|哪[种类]).{0,8}(?:学校|大学)|(?:学校|学院).{0,6}(?:性质|公办|民办)|(?:公办|民办).{0,6}(?:学校|学院)', query)
            if school_nature and not re.search(r'(?:学院|学校|大学)(?:是|为|前身是|以)|(?:转设|设置)为', unit):
                continue
            if school_nature and not re.search(r'普通本科(?:高校|院校|教育)|全日制.{0,8}本科|(?:公办|民办).{0,8}(?:普通|本科|高校|学校)|独立设置.{0,12}本科高校|独立学院', unit):
                continue
            if not _property_relation_supported(query, intent, topic, unit):
                continue
            contextual_subjects = fact_slots(chunk.get('title', ''))['subject']
            if chunk.get('source') == 'library':
                contextual_subjects = list(contextual_subjects) + ['图书馆']
            if not _slots_supported(slots, unit, contextual_subjects):
                continue
            if not _specific_supported(query, unit) or terms and not any(t in unit for t in terms):
                continue
            if intent == 'contact' and not re.search(r'\d[\d -]{6,}', unit):
                continue
            if intent == 'contact' and subjects and not any(s in unit for s in subjects):
                if not (chunk.get('source') == 'library' and subjects == ['图书馆']):
                    continue
            if intent == 'website' and 'http' not in unit:
                continue
            if intent in ('amount', 'duration', 'quota') and not re.search(r'\d|[一二三四五六七八九十百]', unit):
                continue
            if intent == 'amount' and not re.search(r'\d+(?:\.\d+)?\s*(?:万?元|倍)', unit):
                continue
            if intent == 'quota':
                is_people_count = not any(w in query for w in ('借', '本', '册', '借书', '借阅')) and any(w in query for w in ('人', '多少个', '多少位', '多少名', '几位', '几名', '几人', '多少人', '多少老师', '多少教师', '人数', '教职工人数', '教师人数', '多少学生'))
                if is_people_count:
                    if not re.search(r'\d+\s*(?:人|名|位|余人|多人)|(?:专任教师|教师|教职工|教职员工|学生|编制)\s*(?:共计?|约|达)?\s*\d+', unit):
                        continue
                else:
                    count_unit = '次' if '几次' in query else '册'
                    if not re.search(r'\d+\s*' + count_unit, unit):
                        continue
                    if '借' in query and not re.search(r'(?:限借|借阅|可借|借书|借)[^。；]*\d+\s*' + count_unit, unit):
                        continue
                    if '教职工' in query and not any(w in unit for w in ('教职工', '教职员工')):
                        continue
                    if '本科生' in query and not any(w in unit for w in ('本科', '本专科', '学生')):
                        continue
                    if any(role in query and role not in unit for role in ('研究生', '校外人员', '校友', '访客')):
                        continue
            if intent == 'major' and not re.search(r'(?:开设|下设|设置|设有)[^。]{0,100}(?:专业|工程|技术|人工智能)|专业[：:]', unit):
                continue
            if intent == 'duration' and not re.search(r'\d+\s*(?:个\s*)?(?:天|工作日|小时|分钟|年|月)', unit):
                continue
            if intent == 'duration' and '借' in query and '续借' not in query and '续借' in unit and '借阅期限' not in unit:
                continue
            if intent == 'duration' and '借' in query and not re.search(r'借期|借阅期限|借阅期|借[^。；]*\d+\s*天', unit):
                continue
            if intent == 'time' and not re.search(r'\d[:：]|第\s*\d|周[一二三四五六日天]|每日|每天|学期|秋季|春季|期满|公告.*为准|通告.*执行', unit):
                continue
            overlap = lexical_overlap(query, unit)
            if not topic and overlap < .22 or not subjects and overlap < .12:
                continue
            if intent == 'general' and overlap < .25:
                continue
            score = overlap + .22 * bool(terms) + .12 * bool(subjects)
            if chunk.get('source') in SOURCE_PREFERENCES.get(topic, ()):
                score += .2
            if intent == 'location' and chunk.get('source') == 'campus_landmarks':
                score += .6
            if intent == 'contact' and chunk.get('source') == 'office_contacts':
                score += .5
            if intent == 'major' and chunk.get('source') == 'campus_organizations':
                score += .6
                if any(subject in chunk.get('title', '') for subject in subjects):
                    score += .2
            if any(s in unit for s in subjects):
                score += .2
            if intent == 'time':
                if any(k in query for k in ('截止', '哪一周', '第几周', '提交')):
                    score += .3 * any(k in unit for k in ('截止', '提交', '第', '受理'))
                if any(k in query for k in ('闭馆', '关门', '几点', '周末')):
                    score += .25 * any(k in unit for k in ('闭馆', '开放时间', '开闭馆', '全天开放'))
            if '普通图书' in query and '普通图书' in unit:
                score += .3
            matches.append({'chunk_index': index, 'text': unit, 'score': round(score, 4)})
    # A topical reference document is authoritative for stable service/policy
    # facts. News remains eligible when explicitly requested or no such fact exists.
    policy_query = intent != 'general' and not re.search(r'新闻|报道|最近|近期|最新|视察|调研|举办|举行', query)
    if policy_query and any(chunks[m['chunk_index']].get('source') == topic for m in matches):
        matches = [m for m in matches if chunks[m['chunk_index']].get('source') == topic]
    matches.sort(key=lambda item: item['score'], reverse=True)
    if is_topic_lookup(query):
        # One best fact per distinct article before filling remaining slots.
        first, rest, articles = [], [], set()
        for match in matches:
            chunk = chunks[match['chunk_index']]
            key = chunk.get('url') or (chunk.get('source'), chunk.get('section_id', chunk.get('title')))
            if key in articles:
                rest.append(match)
            else:
                articles.add(key)
                first.append(match)
        matches = first + rest
    result, seen = [], set()
    for match in matches:
        if result and match['score'] < result[0]['score'] - .18:
            continue
        key = re.sub(r'\s+', '', match['text'])
        if key not in seen:
            seen.add(key)
            result.append(match)
        if len(result) >= max_sentences:
            break
    return result


class LocalCrossEncoder:
    """只加载显式配置的本地单 logit 精排模型，不自动下载。"""
    def __init__(self, model_path):
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        if not Path(model_path).is_dir():
            raise ValueError('RAG_RERANKER_PATH 必须是本地模型目录')
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)
        self.model.eval()

    def score(self, query, texts):
        result = []
        with self.torch.inference_mode():
            for start in range(0, len(texts), 8):
                batch = texts[start:start+8]
                inputs = self.tokenizer([query] * len(batch), batch, padding=True, truncation=True, max_length=512, return_tensors='pt')
                logits = self.model(**inputs).logits
                if logits.shape[-1] != 1:
                    raise ValueError('交叉编码模型必须输出单个相关性 logit')
                result.extend(logits.flatten().tolist())
        return result


@lru_cache(maxsize=1)
def _local_reranker(path):
    try:
        return LocalCrossEncoder(path)
    except Exception as exc:
        logging.warning('本地交叉编码精排不可用，采用规则精排：%s', exc)
        return None


def rerank_candidates(query, candidates, top_k=None):
    analysis = analyze_query(query)
    path = os.getenv('RAG_RERANKER_PATH', '').strip()
    model = _local_reranker(path) if path else None
    neural, scored = None, []
    if model and candidates:
        try:
            neural = model.score(query, [c['text'] for c, _, _ in candidates])
        except Exception as exc:
            logging.warning('精排推理失败，采用规则精排：%s', exc)
    for i, (chunk, rrf, details) in enumerate(candidates):
        evidence = select_evidence(query, [chunk], 1)
        relevance = evidence[0]['score'] if evidence else lexical_overlap(query, chunk.get('text', '')) * .3
        score = relevance + (float(neural[i]) * .05 if neural is not None else 0) + float(rrf) * .5
        info = dict(details, rerank_score=round(score, 5), evidence_score=relevance,
            reranker='local_cross_encoder' if neural is not None else 'rule_evidence', intent=analysis['intent'])
        scored.append((chunk, rrf, info))
    scored.sort(key=lambda row: row[2]['rerank_score'], reverse=True)
    result, counts = [], {}
    for row in scored:
        key = row[0].get('section_id', row[0].get('global_id'))
        if counts.get(key, 0) < 2:
            counts[key] = counts.get(key, 0) + 1
            result.append(row)
    return result[:top_k] if top_k is not None else result
