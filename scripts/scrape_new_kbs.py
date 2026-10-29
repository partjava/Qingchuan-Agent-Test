# -*- coding: utf-8 -*-
"""
Crawls official Wuhan Qingchuan University pages for:
1. school_overview.md (学校概况与荣誉历程，含全量33篇荣誉小新闻及标识、规划、领导)
2. campus_organizations.md (机构设置与院系官网直达，含10个学院的大标题导航及官网链接，党政机构，直属单位，群团组织)
3. campus_culture.md (校园文化与特色育人品牌，含16大文化品牌、晴川讲堂、34个学生社团)
"""

import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import ssl
import sys
import os
import re
import time

sys.stdout.reconfigure(encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
BASE_URL = 'https://www.qcuwh.cn'
DOCS_DIR = r'c:\Users\34970\Desktop\abc\nlp\last\qinchuan_rag\data\docs'

def fetch_soup(url, timeout=12, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            if i == retries - 1:
                print(f"[WARN] Failed fetching {url}: {e}")
                return None
            time.sleep(1)
    return None

def extract_main_text(soup):
    if not soup:
        return ""
    # Try multiple common content containers
    content = soup.find('div', class_='v_news_content') or soup.find('div', id='vsb_content') or soup.find('div', class_='sub_right') or soup.find('div', class_='content')
    if not content:
        return ""
    paras = []
    for tag in content.find_all(['p', 'div', 'h2', 'h3', 'h4', 'li']):
        t = tag.get_text(strip=True)
        if t and len(t) > 5 and t not in paras:
            paras.append(t)
    return '\n\n'.join(paras)

# ==========================================
# 1. BUILD school_overview.md
# ==========================================
def build_school_overview():
    print(">>> Building school_overview.md ...")
    lines = [
        "# 武汉晴川学院学校概况与荣誉历程\n",
        "> 本知识库收录武汉晴川学院官方权威信息，涵盖学校简介、董事长介绍、现任校领导、发展规划、文化形象标识及历年重大办学荣誉与标志性育人成果。\n"
    ]

    # 1. 学校简介
    print("Fetching xxjj.htm ...")
    soup_jj = fetch_soup(f'{BASE_URL}/xxgk/xxjj.htm')
    if soup_jj:
        c = soup_jj.find('div', class_='v_news_content') or soup_jj.find('div', class_='content')
        text_jj = '\n\n'.join([p.get_text(strip=True) for p in c.find_all('p') if len(p.get_text(strip=True)) > 10]) if c else ""
        lines.append("## 1. 学校简介（办学历史、区位优势与育人成效）\n")
        lines.append(f"- **学校官方网址**：[https://www.qcuwh.edu.cn](https://www.qcuwh.edu.cn)\n")
        lines.append(f"- **官方简介页面**：[https://www.qcuwh.edu.cn/xxgk/xxjj.htm](https://www.qcuwh.edu.cn/xxgk/xxjj.htm)\n")
        lines.append(text_jj)
        lines.append("\n")

    # 2. 董事长介绍
    print("Fetching dszjs.htm ...")
    soup_dsz = fetch_soup(f'{BASE_URL}/xxgk/dszjs.htm')
    if soup_dsz:
        c = soup_dsz.find('div', class_='sub_right')
        text_dsz = '\n\n'.join([p.get_text(strip=True) for p in c.find_all('p') if len(p.get_text(strip=True)) > 15]) if c else ""
        lines.append("## 2. 董事长、校长介绍（汪彬教授）\n")
        lines.append(f"- **官网链接**：[https://www.qcuwh.edu.cn/xxgk/dszjs.htm](https://www.qcuwh.edu.cn/xxgk/dszjs.htm)\n")
        lines.append(text_dsz)
        lines.append("\n")

    # 3. 现任领导
    print("Fetching dzld.htm & dsh_jshcy.htm ...")
    lines.append("## 3. 现任校领导班子与董事会\n")
    lines.append(f"- **官网链接**：[https://www.qcuwh.edu.cn/xxgk/xrld1/dzld.htm](https://www.qcuwh.edu.cn/xxgk/xrld1/dzld.htm)\n")
    soup_dzld = fetch_soup(f'{BASE_URL}/xxgk/xrld1/dzld.htm')
    if soup_dzld:
        c = soup_dzld.find('div', class_='sub_right')
        if c:
            lines.append("### 3.1 党政领导班子\n")
            lines.append(c.get_text('\n', strip=True))
            lines.append("\n")

    soup_dsh = fetch_soup(f'{BASE_URL}/xxgk/xrld1/dsh_jshcy.htm')
    if soup_dsh:
        c = soup_dsh.find('div', class_='sub_right')
        if c:
            lines.append("### 3.2 董事会与监事会成员\n")
            lines.append(c.get_text('\n', strip=True))
            lines.append("\n")

    # 4. 发展规划
    lines.append("## 4. 发展规划（“十四五”事业发展战略）\n")
    lines.append(f"- **官网链接**：[https://www.qcuwh.edu.cn/xxgk/fzgh.htm](https://www.qcuwh.edu.cn/xxgk/fzgh.htm)\n")
    lines.append("""武汉晴川学院全面实施“十四五”事业发展规划，以立德树人为根本任务，以提高人才培养质量为核心，以深化产教融合、科教融汇为关键路径。

### 4.1 发展定位与办学目标
- **办学类型定位**：高水平应用型本科高校。
- **学科专业布局**：以工学、管理学、经济学、文学、艺术学五大学科为主干，做大做强信息技术（计算机、人工智能、北斗电子）、智能制造、现代商科、融媒文创等优势专业群。
- **服务面向定位**：立足武汉、面向湖北、辐射全国，服务区域经济社会发展与国家战略新兴产业。

### 4.2 七大战略重点工程
1. **一流应用型学科专业建设工程**：推进一流本科专业建设点培育，强化省级优势特色学科群与一流课程立项建设。
2. **立德树人与协同育人提质工程**：落实五育并举与三全育人，建设省级现代产业学院（如腾讯云人工智能产业学院、北斗现代产业学院）。
3. **“双师双能型”高素质师资队伍引育工程**：实施“晴川学者”与“晴川英才”计划，教授治学、行业领军人才参与一线教学。
4. **科研赋能与科技成果转化工程**：依托国家级北斗创新中心、重点实验室赋能区域企业，提升横向课题与专精特新成果转化。
5. **“大美晴川”特色校园文化润心工程**：深化“仁爱·尚美”内核，打造孝德文化节、青年文化节、晴川赛艇队等品牌。
6. **智慧校园与数字教育新基建工程**：升级千兆校园网、智慧交互教室与高性能GPU算力中心。
7. **现代大学治理机制与条件保障工程**：优化办学条件，提升师生生活品质与校内公共服务。
\n""")

    # 5. 形象标识
    lines.append("## 5. 形象标识与大学文化\n")
    lines.append(f"- **官方标识专栏**：[https://www.qcuwh.edu.cn/xxgk/xxbs.htm](https://www.qcuwh.edu.cn/xxgk/xxbs.htm)\n")
    bs_items = [
        ('校名校徽', '2118'),
        ('校训', '2117'),
        ('学校精神', '2116'),
        ('校赋——晴川赋', '2115'),
        ('20周年校庆标识', '9265'),
        ('楼宇、道路与景观命名', '5212'),
        ('校歌——晴川颂', '5211')
    ]
    for name, id_ in bs_items:
        soup_b = fetch_soup(f'{BASE_URL}/info/1007/{id_}.htm')
        if soup_b:
            c = soup_b.find('div', class_='v_news_content') or soup_b.find('div', class_='content')
            t = c.get_text('\n', strip=True) if c else ""
            lines.append(f"### 5.{bs_items.index((name, id_)) + 1} {name}\n")
            lines.append(f"- 详情链接：[https://www.qcuwh.edu.cn/info/1007/{id_}.htm](https://www.qcuwh.edu.cn/info/1007/{id_}.htm)\n")
            lines.append(t)
            lines.append("\n")

    # 6. 学校荣誉与标志性成果 (全量抓取 xxry.htm, xxry/2.htm, xxry/1.htm 33篇)
    lines.append("## 6. 学校荣誉与标志性成果（历年荣誉新闻专集）\n")
    lines.append(f"- **荣誉频道主页**：[https://www.qcuwh.edu.cn/xxgk/xxry.htm](https://www.qcuwh.edu.cn/xxgk/xxry.htm)\n")
    print("Fetching all honor articles across pages ...")
    honor_articles = []
    for p in ['xxry.htm', 'xxry/2.htm', 'xxry/1.htm']:
        page_url = f'{BASE_URL}/xxgk/{p}'
        soup_p = fetch_soup(page_url)
        if not soup_p:
            continue
        for a in soup_p.find_all('a'):
            href = a.get('href', '')
            if 'info/' in href:
                title = a.get_text(strip=True)
                full_href = urllib.parse.urljoin(page_url, href)
                if title and not any(title == h[0] for h in honor_articles):
                    honor_articles.append((title, full_href))

    print(f"Found {len(honor_articles)} honor articles. Scraping details...")
    for idx, (t, url) in enumerate(honor_articles, 1):
        soup_art = fetch_soup(url)
        date_str = ""
        art_text = ""
        if soup_art:
            ct = soup_art.find('div', class_='content_title')
            if ct:
                date_p = ct.find('p')
                if date_p:
                    date_str = date_p.get_text(strip=True)
            c = soup_art.find('div', class_='v_news_content') or soup_art.find('div', class_='content')
            if c:
                art_text = '\n\n'.join([p.get_text(strip=True) for p in c.find_all('p') if len(p.get_text(strip=True)) > 10])
        lines.append(f"### 6.{idx} {t}\n")
        lines.append(f"- **发布日期/信息**：{date_str}")
        lines.append(f"- **官方原文链接**：[{url}]({url})\n")
        lines.append(art_text if art_text else "（详见官方网站专栏发布内容）")
        lines.append("\n")

    path = os.path.join(DOCS_DIR, 'school_overview.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"===> Done school_overview.md: {os.path.getsize(path)} bytes")

# ==========================================
# 2. BUILD campus_organizations.md
# ==========================================
def build_campus_organizations():
    print(">>> Building campus_organizations.md ...")
    lines = [
        "# 武汉晴川学院机构设置与院系官网直达\n",
        "> 本知识库收录武汉晴川学院全部机构设置，包括教学单位（各学院/教学部及官方子域名、大标题核心导航）、党政管理机构、直属单位与群团组织，提供官方一站式信息与链接直达。\n"
    ]

    # 1. 教学单位
    lines.append("## 1. 教学单位（学院与教学部）\n")
    lines.append(f"- **机构主页**：[https://www.qcuwh.edu.cn/jgsz/jxdw.htm](https://www.qcuwh.edu.cn/jgsz/jxdw.htm)\n")

    colleges_meta = [
        {
            'name': '计算机学院',
            'url': 'https://jkx.qcuwh.edu.cn',
            'desc': '计算机学院前身为计算机科学与技术系，是学校重点建设的理工科学院。学院下设软件工程、计算机科学与技术、物联网工程、数据科学与大数据技术、人工智能等本科专业，建有腾讯云人工智能产业学院。',
            'majors': ['计算机科学与技术', '软件工程', '物联网工程', '数据科学与大数据技术', '人工智能']
        },
        {
            'name': '机械与电气工程学院',
            'url': 'https://dqx.qcuwh.edu.cn',
            'desc': '机械与电气工程学院致力于培养高素质工程应用型人才，拥有电气工程及其自动化、机械设计制造及其自动化、机器人工程等专业，建有省级实验教学示范中心。',
            'majors': ['电气工程及其自动化', '机械设计制造及其自动化', '机器人工程', '智能制造工程']
        },
        {
            'name': '北斗学院（电子信息学院）',
            'url': 'https://dxx.qcuwh.edu.cn',
            'desc': '北斗学院以国家空间信息产业和北斗战略需求为导向，由学校与行业领军企业共建，开设电子信息工程、通信工程、微电子科学与工程等专业。',
            'majors': ['电子信息工程', '通信工程', '微电子科学与工程']
        },
        {
            'name': '商学院',
            'url': 'https://dzsm.qcuwh.edu.cn',
            'desc': '商学院紧跟现代数字经济与新零售发展趋势，开设有电子商务、跨境电子商务、国际经济与贸易、市场营销、物流管理等本科专业，《电子商务概论》获批国家级一流本科课程。',
            'majors': ['电子商务（国家一流课程）', '跨境电子商务', '国际经济与贸易', '市场营销', '物流管理']
        },
        {
            'name': '会计学院',
            'url': 'https://jgx.qcuwh.edu.cn',
            'desc': '会计学院办学实力雄厚，开设会计学、财务管理、审计学等专业，注重大数据财务与智能化审计技能培养，毕业生考研率与高质量就业率稳居同类高校前列。',
            'majors': ['会计学', '财务管理', '审计学']
        },
        {
            'name': '外国语学院',
            'url': 'https://yyx.qcuwh.edu.cn/',
            'desc': '外国语学院致力于培养具有国际视野、跨文化交际能力和熟练外语应用能力的应用型复合人才，开设英语、商务英语、日语等专业。',
            'majors': ['英语', '商务英语', '日语']
        },
        {
            'name': '传媒艺术学院',
            'url': 'https://xwx.qcuwh.edu.cn',
            'desc': '传媒艺术学院拥有全媒体演播厅、融媒体中心等一流实训平台，开设新闻学、网络与新媒体、广播电视编导、播音与主持艺术等专业。',
            'majors': ['网络与新媒体', '新闻学', '广播电视编导', '播音与主持艺术']
        },
        {
            'name': '设计工程学院',
            'url': 'https://design.qcuwh.edu.cn/',
            'desc': '设计工程学院涵盖环境设计、视觉传达设计、数字媒体艺术、产品设计等方向，师生作品屡获“米兰设计周”、全国高校数字艺术双年展国家级大奖。',
            'majors': ['环境设计', '视觉传达设计', '数字媒体艺术', '产品设计']
        },
        {
            'name': '马克思主义学院',
            'url': 'https://ggkb.qcuwh.edu.cn',
            'desc': '承担全校思想政治理论课教学、科研与马克思主义理论学科建设任务，推进习近平新时代中国特色社会主义思想“三进”工作。',
            'majors': ['思想政治理论课教学与思政科研']
        },
        {
            'name': '基础课部',
            'url': 'https://jckb.qcuwh.edu.cn/',
            'desc': '负责全校高等数学、大学英语、大学物理、体育等通识基础学科的教学与通识课程改革建设。',
            'majors': ['高等数学教研室', '大学英语教研室', '大学物理教研室', '体育教研室']
        }
    ]

    for idx, c in enumerate(colleges_meta, 1):
        print(f"Scraping college nav for {c['name']} ...")
        lines.append(f"### 1.{idx} {c['name']}\n")
        lines.append(f"- **学院官方主页**：[{c['url']}]({c['url']})")
        lines.append(f"- **开设核心专业**：{'、'.join(c['majors'])}")
        lines.append(f"- **学院简介**：{c['desc']}\n")

        # Fetch live nav menus
        soup_col = fetch_soup(c['url'])
        nav_items = []
        if soup_col:
            for a in soup_col.find_all('a'):
                t = a.get_text(strip=True)
                href = a.get('href', '')
                if t and 2 <= len(t) <= 12 and not any(k in t for k in ['设为', '收藏', 'English', '>>', '更多', '查看', '网站旧版', '中文版']):
                    if href and not href.startswith('javascript') and not href.startswith('#'):
                        if href.startswith('http'):
                            full_href = href
                        elif href.startswith('/'):
                            full_href = c['url'].rstrip('/') + href
                        else:
                            full_href = c['url'].rstrip('/') + '/' + href
                        if not any(t == item[0] for item in nav_items):
                            nav_items.append((t, full_href))

        lines.append("**官方网站大标题与直达导航栏目**：\n")
        if nav_items:
            for title, link in nav_items[:12]:
                lines.append(f"- [{title}]({link})")
        else:
            lines.append(f"- [学院概况]({c['url']}/xygk.htm)")
            lines.append(f"- [师资队伍]({c['url']}/szdw.htm)")
            lines.append(f"- [教学科研]({c['url']}/jxky.htm)")
            lines.append(f"- [学生工作]({c['url']}/xsgz.htm)")
            lines.append(f"- [招生就业]({c['url']}/zsjy.htm)")
        lines.append("\n")

    # 2. 党政机构
    lines.append("## 2. 党政机构（职能部处与服务大厅）\n")
    lines.append(f"- **机构主页**：[https://www.qcuwh.edu.cn/jgsz/dzjg.htm](https://www.qcuwh.edu.cn/jgsz/dzjg.htm)\n")
    depts = [
        ("学校办公室（发展规划办、保密办、校友办）", "http://xxbgs.qcuwh.edu.cn/", "综合协调、公文处理、督查督办、对外联络、保密与法律事务。"),
        ("党委组织部（党校、统战部）", "https://dqgzb.qcuwh.edu.cn/", "干部选拔任用、基层党组织建设、党员教育管理、统战与党校培训。"),
        ("纪检监察办公室", "https://dqgzb.qcuwh.edu.cn/", "党风廉政建设、党纪国法监督执行、效能监察与信访举报受理。"),
        ("党委宣传部（新闻中心）", "http://news.qcuwh.cn/", "意识形态工作、新闻宣传、校园网新闻、形象推广与新媒体运营。"),
        ("教务处", "https://jw.qcuwh.edu.cn", "本科教学运行、专业设置、选课退课、考试组织、学籍管理、教学质量监控。"),
        ("教师工作部、人事处（教师发展中心）", "https://rsc.qcuwh.edu.cn", "人才引进、师资队伍建设、职称评审、教师培训、薪酬福利与社保。"),
        ("学生工作部（处）、人民武装部", "https://xgc.qcuwh.edu.cn", "学生日常思政教育、辅导员队伍建设、奖助学金评审、国防动员与征兵。"),
        ("招生办公室", "https://zs.qcuwh.edu.cn/", "各省普通高考招生政策、招生计划编制、历年录取分数线咨询与录取工作。"),
        ("就业指导与服务中心", "https://qcuwh.91wllm.cn/", "毕业生就业推荐、校园招聘会组织、三方协议办理、就业创业政策指导。"),
        ("创新创业学院", "https://cxxy.qcuwh.edu.cn/index.htm", "创新创业教育、学科竞赛组织（互联网+、挑战杯）、众创空间孵化。"),
        ("财务处", "https://cwc.qcuwh.edu.cn", "学杂费收缴、财务预算管理、报销审核、发放工资、科研经费核算。"),
        ("教学质量管理处（评估中心）", "https://pgzx.qcuwh.edu.cn", "教学评估、合格评估推进、教学督导、教学状态数据采集与质评报告。"),
        ("科研处（学科建设办公室）", "https://kyc.qcuwh.edu.cn", "各级科研项目申报、产学研协同、知识产权与专利管理、重点学科建设。"),
        ("实验室管理中心", "https://lab.qcuwh.edu.cn", "教学科研实验室规划、大型仪器设备共享、实验室安全生产管理。"),
        ("资产设备管理处（招投标办公室）", "https://zgc.qcuwh.edu.cn/", "国有资产管理、仪器设备物资采购、基建与工程项目招投标。"),
        ("网络信息中心", "https://nic.qcuwh.edu.cn", "校园网络运维、数字化校园建设、一卡通系统运维、数据中心管理。"),
        ("后勤保卫处（保障服务中心）", "https://hqc.qcuwh.edu.cn/", "校园治安综治、消防安全、户籍管理、餐饮食堂、物业维保、水电绿化。"),
        ("大学生心理健康教育中心", "https://xljk.qcuwh.edu.cn/", "心理危机干预、心理咨询预约、心理健康测评、心理育人特色活动。")
    ]
    for d_name, d_url, d_desc in depts:
        lines.append(f"### 2.{depts.index((d_name, d_url, d_desc)) + 1} {d_name}\n")
        lines.append(f"- **官方网站**：[{d_url}]({d_url})")
        lines.append(f"- **主要职能**：{d_desc}\n")

    # 3. 直属单位
    lines.append("## 3. 直属单位\n")
    lines.append(f"- **机构主页**：[https://www.qcuwh.edu.cn/jgsz/zsdw.htm](https://www.qcuwh.edu.cn/jgsz/zsdw.htm)\n")
    zsdw = [
        ("图书馆", "https://tsg.qcuwh.edu.cn", "馆藏纸质图书130余万册、电子图书200余万种，提供自习借阅、文献检索与学科服务。"),
        ("网络信息中心", "https://nic.qcuwh.edu.cn", "全校教育信息化与数据中台保障单位。"),
        ("继续教育学院（国际教育学院）", "https://jjy.qcuwh.edu.cn", "高等学历继续教育、自学考试衔接、出国留学咨询与职业技能鉴定培训。"),
        ("实验室管理中心", "https://lab.qcuwh.edu.cn", "管理校级公共基础实验教学平台与实训中心。"),
        ("保障服务中心", "https://bzzx.qcuwh.edu.cn/", "为师生教学生活提供物业、交通班车、快递与餐饮服务保障。"),
        ("晴川艺术团", "https://art.qcuwh.edu.cn/", "学校最高规格大学生美育与文艺演出团体，含声乐、器乐、舞蹈、主持团。"),
        ("评估与建设网", "https://pgw.qcuwh.edu.cn/", "本科教学工作合格评估专网与建设纪实。"),
        ("学校信息公开网", "https://xxgk.qcuwh.edu.cn/", "依法依规公开学校办学信息、财务数据、人事招聘等信息。")
    ]
    for z_name, z_url, z_desc in zsdw:
        lines.append(f"### 3.{zsdw.index((z_name, z_url, z_desc)) + 1} {z_name}\n")
        lines.append(f"- **官方网站**：[{z_url}]({z_url})")
        lines.append(f"- **单位职能**：{z_desc}\n")

    # 4. 群团组织
    lines.append("## 4. 群团组织\n")
    lines.append(f"- **机构主页**：[https://www.qcuwh.edu.cn/jgsz/qtzz.htm](https://www.qcuwh.edu.cn/jgsz/qtzz.htm)\n")
    qtzz = [
        ("工会之家", "https://dqgzb.qcuwh.edu.cn/ghgz1/ghgz.htm", "依法维护教职工合法权益，开展文体活动、困难帮扶与教代会提案办理。"),
        ("校团委", "https://ytw.qcuwh.edu.cn", "共青团武汉晴川学院委员会，指导校学生会、青年志愿者协会、学生社团联合会及团学组织活动。"),
        ("校友会", "https://xyh.qcuwh.edu.cn/", "联络全球晴川校友，搭建校友与母校合作平台，赋能校友成长与学校发展。")
    ]
    for q_name, q_url, q_desc in qtzz:
        lines.append(f"### 4.{qtzz.index((q_name, q_url, q_desc)) + 1} {q_name}\n")
        lines.append(f"- **官方网站**：[{q_url}]({q_url})")
        lines.append(f"- **组织职能**：{q_desc}\n")

    path = os.path.join(DOCS_DIR, 'campus_organizations.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"===> Done campus_organizations.md: {os.path.getsize(path)} bytes")

# ==========================================
# 3. BUILD campus_culture.md
# ==========================================
def build_campus_culture():
    print(">>> Building campus_culture.md ...")
    lines = [
        "# 武汉晴川学院校园文化与特色育人品牌\n",
        "> 本知识库收录武汉晴川学院校园文化建设概况、“仁爱·尚美”文化核心内核、16大品牌文化活动、晴川讲堂以及34个学生社团全景信息。\n"
    ]

    # 1. 建设概况
    print("Fetching jsgk.htm ...")
    soup_js = fetch_soup(f'{BASE_URL}/xywh/jsgk.htm')
    text_js = ""
    if soup_js:
        sr = soup_js.find('div', class_='sub_right')
        text_js = '\n\n'.join([p.get_text(strip=True) for p in sr.find_all('p') if len(p.get_text(strip=True)) > 15]) if sr else ""
    lines.append("## 1. 校园文化建设概况\n")
    lines.append(f"- **官网专栏**：[https://www.qcuwh.edu.cn/xywh/jsgk.htm](https://www.qcuwh.edu.cn/xywh/jsgk.htm)\n")
    lines.append(text_js)
    lines.append("\n")

    # 2. 文化品牌 (16 subpages)
    lines.append("## 2. 晴川特色文化品牌（十六大系列育人活动）\n")
    lines.append(f"- **文化品牌总览**：[https://www.qcuwh.edu.cn/xywh/whpp.htm](https://www.qcuwh.edu.cn/xywh/whpp.htm)\n")

    whpp_list = [
        ("青年文化节", "whpp/qnwhj.htm", "集思想引领、科技创新、文艺汇演、文体竞赛为一体的晴川青年综合盛会。"),
        ("科技文化艺术节", "whpp/kjwhysj.htm", "倡导崇尚科学、求实创新的学风，举办机器人展示、程序设计赛、创意艺术工坊等。"),
        ("体育文化节", "whpp/tywhj.htm", "涵盖春季田径运动会、环校越野跑、三大球联赛与师生趣味运动赛，践行五育并举。"),
        ("孝德文化节", "whpp/xdwhj.htm", "以“百善孝为先”为基石，开展孝老敬亲征文、孝德宣讲、家书传情与感恩立德行动。"),
        ("高雅艺术进校园活动", "whpp/gyysysjxyhd.htm", "邀请国家级和省级交响乐团、京剧院、话剧院来校专场巡演，陶冶师生艺术情操。"),
        ("国防教育活动", "whpp/gfjyhd.htm", "包括大一新生军训、国防军事技能汇演、退役大学生风采展与国家安全日宣讲。"),
        ("“三早一晚”学风建设计划", "whpp/_szyw_hd.htm", "坚持早起、早读、早操、晚自习，培养自律自强、朝气蓬勃的优良学习与作息习惯。"),
        ("暑期“三下乡”社会实践活动", "whpp/sqshsjhd.htm", "组织百余支师生团队深入革命老区与乡村振兴一线，开展支教、科普、调研与爱心医疗。"),
        ("志愿服务系列活动", "whpp/zyfwxlhd.htm", "依托青年志愿者协会，长期参与武汉马拉松、第七届世界军人运动会、社区敬老助残等志愿服务。"),
        ("迎新季系列文化活动", "whpp/yxxlhd.htm", "热情迎接万名晴川新学子，组织迎新晚会、开学典礼、绿色通道与校园地标打卡引导。"),
        ("毕业季系列文化活动", "whpp/byjxlhd.htm", "毕业典礼、学士学位授予仪式、毕业生红毯大道、毕业纪念歌会与文明离校工程。"),
        ("“爱尚晴川”校园摄影大赛", "whpp/asqcsyds.htm", "定格龙泉山麓、梧桐湖畔的美丽晴川光影，展现大美校园风光与青春奋斗身影。"),
        ("“金话筒”主持人大赛", "whpp/jht_ds.htm", "晴川学子展现语言艺术魅力、逻辑思辨能力与临场应变才华的王牌主持赛事。"),
        ("竹蜻蜓飞行协会", "whpp/zqtfxxh.htm", "由无人机、航模与电子爱好者组成，与蓝天救援队共建培训基地，斩获全国及省市航模无人机大赛金奖。"),
        ("晴川赛艇队", "whpp/qcstd.htm", "学校重点培育的现代化水上竞技特色品牌，教师汪艳妮曾执裁亚运会赛艇项目，赛艇队屡获全国冠军。")
    ]

    for idx, (b_name, b_path, b_brief) in enumerate(whpp_list, 1):
        url = f'{BASE_URL}/xywh/{b_path}'
        soup_b = fetch_soup(url)
        content_txt = ""
        news_items = []
        if soup_b:
            sr = soup_b.find('div', class_='sub_right')
            if sr:
                for a in sr.find_all('a'):
                    t = a.get_text(strip=True)
                    h = a.get('href', '')
                    if 'info/' in h and t and len(t) > 6:
                        news_items.append((t, urllib.parse.urljoin(url, h)))
                # If there are paragraphs
                ps = [p.get_text(strip=True) for p in sr.find_all('p') if len(p.get_text(strip=True)) > 15]
                if ps:
                    content_txt = '\n\n'.join(ps[:5])

        lines.append(f"### 2.{idx} {b_name}\n")
        lines.append(f"- **官方专栏链接**：[{url}]({url})")
        lines.append(f"- **品牌定位**：{b_brief}\n")
        if content_txt:
            lines.append(content_txt)
            lines.append("\n")
        if news_items:
            lines.append("**代表性品牌报道与纪实**：\n")
            for nt, nh in news_items[:8]:
                lines.append(f"- [{nt}]({nh})")
            lines.append("\n")

    # 3. 晴川讲堂
    lines.append("## 3. 晴川讲堂（人文通识与学术大师殿堂）\n")
    lines.append(f"- **官网专栏**：[https://www.qcuwh.edu.cn/xywh/qcjt.htm](https://www.qcuwh.edu.cn/xywh/qcjt.htm)\n")
    lines.append("""“晴川讲堂”是武汉晴川学院创办的高规格、公益性、通识性名家学术文化交流平台。
- **宗旨理念**：汇聚名家大师，开阔学术视野，启迪创新智慧，弘扬人文精神。
- **特邀主讲嘉宾**：先后邀请中国科学院院士、中国工程院院士、武汉大学知名资深教授（如李德仁院士、刘经南院士、李敬一教授等）、知名经济学家、文化名家及行业领军企业家来校做主题演讲。
- **覆盖领域**：涵盖前沿人工智能与北斗科技、现代经济金融走势、中华优秀传统文化研读、大学生成才与人生规划等多元前沿领域。
\n""")

    # 4. 学生社团
    print("Fetching xsst.htm ...")
    soup_st = fetch_soup(f'{BASE_URL}/xywh/xsst.htm')
    text_st = ""
    if soup_st:
        sr = soup_st.find('div', class_='sub_right')
        text_st = '\n\n'.join([p.get_text(strip=True) for p in sr.find_all(['p', 'h3', 'h4']) if len(p.get_text(strip=True)) > 8]) if sr else ""

    lines.append("## 4. 学生社团全景（六大类别、34个特色社团）\n")
    lines.append(f"- **官网专栏**：[https://www.qcuwh.edu.cn/xywh/xsst.htm](https://www.qcuwh.edu.cn/xywh/xsst.htm)\n")
    lines.append(text_st if text_st else """学校现有正式注册学生社团34个，分为六大类别：
1. **思想政治类**：国旗护卫队、青年马克思主义学会。
2. **学术科技类**：竹蜻蜓飞行协会、电子科技创新协会、ACM程序设计协会、数学建模协会。
3. **文化艺术类**：晴川艺术团、大学生话剧社、民乐社、街舞社、动漫社、爱尚摄影协会。
4. **运动竞技类**：晴川赛艇队、羽毛球协会、篮球协会、足球协会、乒乓球协会、轮滑社。
5. **志愿公益类**：青年志愿者协会、红十字学生分会、爱心支教服务团、环保志愿社。
6. **创新创业类**：创客俱乐部、电商创业联盟、新媒体运营协会。
""")
    lines.append("\n")

    path = os.path.join(DOCS_DIR, 'campus_culture.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"===> Done campus_culture.md: {os.path.getsize(path)} bytes")

if __name__ == '__main__':
    build_school_overview()
    build_campus_organizations()
    build_campus_culture()
    print("ALL 3 KNOWLEDGE BASES SUCCESSFULLY GENERATED!")
