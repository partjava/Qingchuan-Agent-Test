"""可解释的校园问句归一化、意图识别和省略问句改写，无网络依赖。"""
import re
from difflib import get_close_matches
from core.ner_extractor import CAMPUS_LOCATIONS, CAMPUS_ORGANIZATIONS
from core.school_constants import NAV_PLACES, NAV_PLACE_NAMES

ALIASES = {'计院': '计算机学院', '机电院': '机械与电气工程学院', '网院': '北斗学院',
    '图书管': '图书馆', '图书舘': '图书馆', '奖学斤': '奖学金', '教物处': '教务处',
    '学工处': '学生工作处', '招生办': '招生办公室', '借几本': '借多少册', '挂过科': '挂科',
    '开门': '开放',
    '操场': '田径运动场', '足球场': '田径运动场', '体育场': '田径运动场', '田径场': '田径运动场',
    '运动场': '田径运动场', '体育馆': '室内综合体育馆'}
TOPICS = {
    'library': ('图书馆', '借书', '借阅', '借期', '图书', '续借', '还书'),
    'scholarship': ('奖学金', '助学金', '评奖', '评优', '挂科'),
    'course_selection': ('选课', '退课', '退改选'), 'laboratory': ('实验室', '机房', 'GPU'),
    'student_status': ('学籍', '毕业预审', '毕业资格', '转专业'),
    'campus_organizations': ('学院', '教务处', '学生工作处', '招生办公室', '财务处'),
    'campus_landmarks': ('田径运动场', '操场', '足球场', '田径场', '体育场', '运动场', '体育馆', '室内综合体育馆', '大礼堂', '食堂', '宿舍', '正大门', '南大门', '情缘湖'),
    'school_overview': ('校训', '校长', '学校精神', '学校地址', '风景区')}
SUBJECTS = ('国家励志奖学金', '国家奖学金', '国家助学金', '晴川奖学金', '综合奖学金',
    '晴川助学金', '奖学金', '助学金', '图书馆', '实验室', '机房', '退改选', '选课',
    '毕业预审', '转专业', '计算机学院', '教务处', '学生工作处', '招生办公室', '财务处',
    '田径运动场', '田径场', '操场', '足球场', '体育场', '运动场', '室内综合体育馆', '体育馆')
SUBJECTS = tuple(dict.fromkeys(SUBJECTS + tuple(CAMPUS_LOCATIONS) + tuple(CAMPUS_ORGANIZATIONS)))
INTENTS = (
    ('contact', ('电话', '联系方式', '号码', '怎么联系', '传真')),
    ('website', ('官网', '网址', '网站', '主页', '入口', '链接')),
    ('eligibility', ('挂科', '不及格', '条件', '资格', '能申请', '可以申请', '要求', '门槛', 'GPA', '绩点')),
    ('amount', ('多少钱', '金额', '多少元', '费用', '收费', '赔偿', '滞还金', '预算')),
    ('duration', ('多少天', '几天', '借期', '借多久', '多久', '时长', '多长时间')),
    ('quota', ('几本', '多少本', '多少册', '借书上限', '借阅上限', '额度', '几次', '多少个', '多少位', '多少名', '几位', '几名', '几人', '多少人', '多少老师', '多少教师', '人数', '教职工人数', '教师人数', '多少学生')),
    ('time', ('几点', '什么时候', '何时', '时间', '截止', '第几周', '哪一周', '周末', '节假日', '闭馆', '关门', '开放')),
    ('location', ('在哪', '哪里', '位置', '几层', '多少层', '几楼', '地点', '旁边', '位于')),
    ('major', ('哪些专业', '什么专业', '有哪些专业', '开设', '本科专业')),
    ('procedure', ('怎么申请', '如何申请', '流程', '步骤', '材料', '怎么办')))


def normalize(text):
    changes = []
    pattern = '|'.join(re.escape(k) for k in sorted(ALIASES, key=len, reverse=True))
    def replace(match):
        before = match.group()
        after = ALIASES[before]
        changes.append({'from': before, 'to': after})
        return after
    normalized = re.sub(pattern, replace, text.strip())
    if '借' in normalized:
        for alias in ('老师', '教师'):
            if alias in normalized:
                normalized = normalized.replace(alias, '教职工')
                changes.append({'from': alias, 'to': '教职工'})
    gate_sub = re.sub(r'(?<![南北东西正])(?:校门口|校门|大门)', '正大门', normalized)
    if gate_sub != normalized:
        changes.append({'from': '校门', 'to': '正大门'})
        normalized = gate_sub
    return normalized, changes


def subjects_in(text):
    found = []
    for subject in sorted(SUBJECTS, key=len, reverse=True):
        if subject in text and not any(subject in item for item in found):
            found.append(subject)
    return found


def detect_topic(text):
    topic = next((topic for topic, words in TOPICS.items() if any(w in text for w in words)), '')
    return topic or ('campus_landmarks' if any(place in text for place in CAMPUS_LOCATIONS) else '')


def detect_intent(text):
    return next((intent for intent, words in INTENTS if any(w in text for w in words)), 'general')


GRADE_PATTERN = r'一等奖|二等奖|三等奖|甲等|乙等|丙等|一等(?!奖)|二等(?!奖)|三等(?!奖)'
ROLE_GROUPS = {'教职工': ('教职工', '教职员工', '老师', '教师'),
    '本科生': ('本科生', '本专科生'), '研究生': ('研究生',),
    '校外人员': ('校外人员',), '校友': ('校友',), '访客': ('访客',)}
EVENTS = ('初评', '终审', '公示', '发放', '到账', '申请', '截止', '续借', '预约')


def fact_slots(text, subjects=None, intent=None):
    conditions = {}
    grades = list(dict.fromkeys(re.findall(GRADE_PATTERN, text)))
    if grades:
        conditions['grade'] = grades
    role = next((role for role, aliases in ROLE_GROUPS.items() if any(a in text for a in aliases)), '')
    if role:
        conditions['role'] = role
    events = [event for event in EVENTS if event in text]
    if events:
        conditions['event'] = events
    return {'subject': subjects if subjects is not None else subjects_in(text),
            'attribute': intent or detect_intent(text), 'conditions': conditions}


def extract_navigation_route(text: str):
    """从问句或历史回复中解析出导航起终点信息"""
    if not text:
        return None
    # 1. 检测历史助手回答中的导航标志：🚩 晴川校园步行导航：从【正大门】前往【一食堂】
    m_nav = re.search(r'晴川校园步行导航：从【(.*?)】前往【(.*?)】', text)
    if m_nav:
        from_raw, to_raw = m_nav.group(1).strip(), m_nav.group(2).strip()
    else:
        cleaned = re.sub(r'[？?！!。，,\s]+$', '', text.strip())
        cleaned = re.sub(r'^(请问|请教一下|我想知道|麻烦问下)[，,\s]*', '', cleaned)
        m = re.search(r'(?:从|由)(.*?)(?:怎么|如何|怎样|大概)?(?:去|到|走|往)(.*?)(?:怎么走|如何走|路线|怎么去|有多远|多远|要花多长时间|要多长时间|要多久|步行多久|走多久|几分钟|大概多长时间)?$', cleaned)
        if not m:
            m = re.search(r'^(.*?)(?:怎么|如何|大概)?(?:去|到|走|往)(.*?)(?:怎么走|如何走|路线|怎么去|有多远|多远|要花多长时间|要多长时间|要多久|步行多久|走多久|几分钟|大概多长时间)?$', cleaned)
        if not m:
            return None
        from_raw, to_raw = m.group(1).strip(), m.group(2).strip()

    from_id, to_id = None, None
    for pid, aliases in NAV_PLACES.items():
        for a in aliases:
            if a in from_raw:
                from_id = pid
                break
        if from_id:
            break

    for pid, aliases in NAV_PLACES.items():
        for a in aliases:
            if a in to_raw:
                to_id = pid
                break
        if to_id:
            break

    if from_id and to_id and from_id != to_id:
        return {
            'from_id': from_id,
            'from_name': NAV_PLACE_NAMES.get(from_id, from_raw),
            'to_id': to_id,
            'to_name': NAV_PLACE_NAMES.get(to_id, to_raw)
        }
    return None


def analyze_query(question, history=None):
    normalized, changes = normalize(question)
    rewritten = normalized
    subjects = subjects_in(normalized)
    topic, intent = detect_topic(normalized), detect_intent(normalized)
    clarification, context = False, ''

    is_route_followup = bool(re.search(
        r'^(大概|走过去|走路|步行|骑车|要花|需要|要|预计|\s)*(多长时间|多久|多远|几分钟|几小时|几米|多少米|远吗|远不远)[？?]?$',
        normalized
    )) or bool(re.search(
        r'^(怎么走|如何走|路线|怎么去|有多远|多远|步行要多久|走过去要多久|要花多长时间|要多久|远吗|远不远)[？?]?$',
        normalized
    ))

    # 优先检查多轮对话中的校园导航路线继承
    prior_nav = None
    if history:
        for turn in reversed(history[-12:]):
            content = str(turn.get('content', '')).strip()
            prior_nav = extract_navigation_route(content)
            if prior_nav:
                break

    if prior_nav:
        if is_route_followup and len(subjects) == 0:
            if any(w in normalized for w in ('多远', '几米', '多少米', '距离', '远不远', '远吗')):
                rewritten = f"从{prior_nav['from_name']}到{prior_nav['to_name']}有多远？"
                intent = 'distance'
            else:
                rewritten = f"从{prior_nav['from_name']}到{prior_nav['to_name']}步行要花多长时间？"
                intent = 'duration'
            context = f"从{prior_nav['from_name']}到{prior_nav['to_name']}"
            subjects = [prior_nav['from_name'], prior_nav['to_name']]
            topic = 'campus_landmarks'
            clarification = False
        elif (bool(re.search(r'^(那|那么)?(去|到|前往|走)', normalized)) or bool(re.search(r'那.*呢|呢[？?]?$', normalized))) and len(subjects) == 1 and subjects[0] != prior_nav['from_name']:
            new_to = subjects[0]
            rewritten = f"从{prior_nav['from_name']}到{new_to}怎么走？"
            context = f"从{prior_nav['from_name']}到{new_to}"
            subjects = [prior_nav['from_name'], new_to]
            topic = 'campus_landmarks'
            intent = 'location'
            clarification = False

    elliptical = bool(re.search(r'它|那里|那边|这个|那个|这里|此地|^那|那.*呢|呢[？?]?$|周末|节假日|还可以|能借|能申请|多少册|几本', normalized)) or bool(re.search(r'^(几点.*|什么时候.*|开放时间|闭馆时间|开门时间|开门吗|关门吗|怎么走|怎么去|在哪.*|在哪里.*|电话.*|收费.*|逾期.*|怎么联系|如何申请|申请条件|多少钱|金额.*|期限.*|多长时间|能借多少)[？?]?$', normalized)) or is_route_followup
    if rewritten == normalized and not subjects and elliptical and (not topic or re.search(r'它|那里|那边|这个|那个|^那', normalized) or topic == 'library' and '图书' not in normalized and '借' in normalized):
        previous = []
        for turn in (history or [])[-12:]:
            if turn.get('role') == 'user':
                text, _ = normalize(str(turn.get('content', ''))[:1000])
                if subjects_in(text) or detect_topic(text):
                    previous.append(text)
                elif not re.search(r'^(那|那么|它|这里|那里)|呢[？?]?$|^(能借|还可以|能申请)', text):
                    # 一个新的完整问题即使超出词典，也会阻断旧话题。
                    previous.append(text)
        if previous:
            context = previous[-1]
            prior_subjects = subjects_in(context)
            if len(prior_subjects) == 1:
                rewritten = prior_subjects[0] + '，' + re.sub(r'^(那么|那个|这个|那里|那|它)[，,\s]*', '', normalized)
                if intent == 'general':
                    intent = detect_intent(context)
                    hints = {'amount': '金额是多少', 'time': '开放或截止时间', 'duration': '期限多久',
                             'contact': '联系电话', 'eligibility': '申请条件', 'location': '位置在哪'}
                    if intent in hints:
                        rewritten += '，' + hints[intent]
                subjects, topic = prior_subjects, detect_topic(rewritten)
            else:
                clarification = True
        elif re.search(r'它|那里|那边|这个|那个|^那|^还可以|^能申请', normalized):
            clarification = True
    if not topic:
        topic = detect_topic(rewritten)
    suggestions = []
    if not topic and not changes:
        for token in re.findall(r'[\u4e00-\u9fff]{3,5}', normalized):
            suggestions.extend(get_close_matches(token, SUBJECTS, n=1, cutoff=.8))
    return {'original_query': question, 'normalized_query': normalized, 'rewritten_query': rewritten,
        'normalizations': changes, 'topic': topic, 'intent': intent, 'subjects': subjects,
        'context_used': context if rewritten != normalized else '', 'clarification': clarification,
        'suggestions': list(dict.fromkeys(suggestions)), 'slots': fact_slots(rewritten, subjects, intent)}


def plan_subqueries(question, history=None):
    """Expand explicit clauses, known subject lists and award grades only.

    Do not split arbitrary 和/与 characters: they may belong to a proper name.
    """
    analysis = analyze_query(question, history)
    text = analysis['rewritten_query']
    if extract_navigation_route(text):
        return [{'question': text, 'label': text, 'slots': analysis['slots']}]
    def attribute_clauses(clause):
        protected = [(m.start(), m.end()) for subject in subjects_in(clause)
                     for m in re.finditer(re.escape(subject), clause)]
        for match in re.finditer(r'以及|并且|同时|和|与|及', clause):
            if any(start <= match.start() < end for start, end in protected):
                continue
            left, right = clause[:match.start()], clause[match.end():]
            if detect_intent(left) != 'general' and detect_intent(right) != 'general':
                return attribute_clauses(left) + attribute_clauses(right)
        return [clause]
    clauses = [part.strip(' ，,。？！?') for clause in re.split(r'[；;，,？?！!]', text)
               for part in attribute_clauses(clause)]
    clauses = [c for c in clauses if c]
    if len(clauses) > 1 and detect_intent(clauses[0]) == 'general':
        prefix = clauses[0]
        if subjects_in(prefix) or not re.search(r'什么|谁|为何|怎么|如何|吗|呢|是否|为什么|有无|介绍', prefix):
            clauses[:2] = [prefix + '，' + clauses[1]]
    planned = []
    inherited = []
    inherited_intent = ''
    intent_hints = {'amount': '金额多少钱', 'quota': '借阅上限', 'time': '时间是什么',
                    'duration': '期限多久', 'location': '位置在哪里', 'contact': '联系电话',
                    'website': '官方网站', 'eligibility': '申请条件', 'major': '有哪些专业'}
    for clause in clauses:
        subjects = subjects_in(clause)
        subjects.sort(key=clause.find)
        if not subjects and inherited:
            clause = '、'.join(inherited) + '，' + clause
            subjects = inherited[:]
        elif subjects:
            inherited = subjects[:]
        intent = detect_intent(clause)
        if intent == 'general' and inherited_intent and (re.search(GRADE_PATTERN, clause) or re.search(r'呢[？?]?$', clause)):
            clause += '，' + intent_hints.get(inherited_intent, '')
            intent = inherited_intent
        if intent != 'general':
            inherited_intent = intent
        variants = [clause]
        if len(subjects) > 1:
            first = min(clause.find(s) for s in subjects)
            last = max(clause.find(s) + len(s) for s in subjects)
            # Only a coordinated subject span is expanded; separate full
            # propositions are handled as clauses above.
            middle = clause[first:last]
            residue = middle
            for subject in sorted(subjects, key=len, reverse=True):
                residue = residue.replace(subject, '')
            if re.fullmatch(r'[和与及、\s]*', residue):
                variants = [clause[:first] + subject + clause[last:] for subject in subjects]
        for variant in variants:
            grades = list(dict.fromkeys(re.findall(GRADE_PATTERN, variant)))
            grade_variants = [variant]
            if len(grades) > 1:
                first = min(variant.find(g) for g in grades)
                last = max(variant.find(g) + len(g) for g in grades)
                residue = variant[first:last]
                for grade in grades:
                    residue = residue.replace(grade, '')
                if re.fullmatch(r'[和与及、\s]*', residue):
                    grade_variants = [variant[:first] + grade + variant[last:] for grade in grades]
            for item in grade_variants:
                sub = analyze_query(item, history)
                planned.append({'question': sub['rewritten_query'], 'label': sub['rewritten_query'], 'slots': sub['slots']})
                if len(planned) > 6:
                    raise ValueError('一次最多支持6个子问题，请分批提问')
    return planned or [{'question': text, 'label': text, 'slots': analysis['slots']}]
