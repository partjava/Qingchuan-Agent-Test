# -*- coding: utf-8 -*-
"""
Crawl all information disclosure pages from Wuhan Qingchuan University's official
information disclosure portal: https://xxgk.qcuwh.edu.cn/

Extracts:
1. All top-level navigation sections: 指南, 制度, 年报, 申请, 最新公开信息
2. All 48 gksx categories (10 major categories: 基本信息, 招生考试, 财务资产与收费, 人事师资, 教学质量, 学生服务, 学风建设, 学位学科, 对外合作, 其他)
3. For each category, crawls all articles (including pagination) with full texts, dates, PDF attachments, images, and external jumps.
4. Generates data/docs/info_disclosure.md
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
BASE_URL = 'https://xxgk.qcuwh.edu.cn'
DOCS_DIR = r'c:\Users\34970\Desktop\abc\nlp\last\qinchuan_rag\data\docs'

def fetch_soup(url, timeout=10, retries=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            if i == retries - 1:
                return None
            time.sleep(1)
    return None

def fetch_article_detail(url):
    soup = fetch_soup(url)
    if not soup:
        return None
    
    t_div = soup.find('div', class_='title')
    title = t_div.get_text(strip=True) if t_div else ""
    if not title and soup.title:
        title = soup.title.string.replace('-信息公开网', '').strip()
    
    # date
    date_str = ""
    date_match = re.search(r'发布时间[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', soup.get_text())
    if date_match:
        date_str = date_match.group(1)
        
    c_div = soup.find('div', class_='v_news_content') or soup.find('div', id='vsb_content') or soup.find('div', class_='content')
    text = ""
    if c_div:
        paras = []
        for p in c_div.find_all(['p', 'div', 'h2', 'h3', 'h4', 'li']):
            txt = p.get_text(strip=True)
            if txt and len(txt) > 5 and txt not in paras and not txt.startswith('showVsbpdf'):
                paras.append(txt)
        text = '\n\n'.join(paras)
        
    # check PDF attachment
    soup_str = str(soup)
    pdf_match = re.search(r'showVsbpdfIframe\("([^"]+)"', soup_str)
    pdf_url = urllib.parse.urljoin(url, pdf_match.group(1)) if pdf_match else ""
    if not pdf_url:
        for a in soup.find_all('a'):
            h = a.get('href', '')
            if any(h.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.xlsx', '.xls']):
                pdf_url = urllib.parse.urljoin(url, h)
                break
                
    # check images
    imgs = []
    img_match = re.search(r'vsb_pdf_image_data\s*=\s*\[(.*?)\]', soup_str)
    if img_match:
        for im in re.findall(r'"([^"]+)"', img_match.group(1)):
            imgs.append(urllib.parse.urljoin(url, im))
    if c_div:
        for im in c_div.find_all('img'):
            src = im.get('src')
            if src and not src.startswith('data:'):
                full_src = urllib.parse.urljoin(url, src)
                if full_src not in imgs:
                    imgs.append(full_src)
                    
    return {
        'title': title,
        'date': date_str,
        'url': url,
        'text': text,
        'pdf_url': pdf_url,
        'images': imgs[:4]
    }

def crawl_info_disclosure():
    print(">>> Starting comprehensive crawl of https://xxgk.qcuwh.edu.cn/ ...")
    home_soup = fetch_soup(BASE_URL)
    if not home_soup:
        print("[ERROR] Cannot fetch home page of xxgk!")
        return

    # Structure categories
    # 1. Top navigation
    top_nav = [
        ('信息公开指南', f'{BASE_URL}/xxgkzn.htm', '指南'),
        ('信息公开制度', f'{BASE_URL}/xxgkzd.htm', '制度'),
        ('信息公开年报', f'{BASE_URL}/xxgknb.htm', '年报'),
        ('信息公开申请', f'{BASE_URL}/xxgksq.htm', '申请'),
        ('最新公开信息', f'{BASE_URL}/zxgkxx.htm', '最新信息')
    ]

    # 2. 10 major gksx groups mapped from links
    group_mapping = {
        'jbxx': '一、基本信息公开事项',
        'zsksxx': '二、招生考试信息公开事项',
        'cw_zcjsfxx': '三、财务、资产及收费信息公开事项',
        'rsszxx': '四、人事师资信息公开事项',
        'jxzlxx': '五、教学质量与就业信息公开事项',
        'xsglfwxx': '六、学生管理服务信息公开事项',
        'xfjsxx': '七、学风建设与学术规范信息公开事项',
        'xwxkxx': '八、学位学科信息公开事项',
        'dwjlyhzxx': '九、对外交流与合作信息公开事项',
        'qt': '十、其他信息公开事项（巡视反馈与应急）'
    }

    category_list = []
    for a in home_soup.find_all('a'):
        h = a.get('href', '')
        t = a.get_text(strip=True)
        if 'gksx/' in h and t:
            full = urllib.parse.urljoin(BASE_URL, h)
            # determine group
            group_key = 'qt'
            for gk in group_mapping.keys():
                if f'/{gk}/' in full:
                    group_key = gk
                    break
            if not any(full == item['url'] for item in category_list):
                category_list.append({
                    'title': t,
                    'url': full,
                    'group_key': group_key,
                    'group_name': group_mapping.get(group_key, '其他信息')
                })

    print(f"Discovered {len(category_list)} gksx categories across 10 groups.")

    lines = [
        "# 武汉晴川学院信息公开权威全息知识库\n",
        "> 本知识库收录武汉晴川学院信息公开网（https://xxgk.qcuwh.edu.cn）全部权威公开内容，包括信息公开指南与实施办法、历年信息公开工作年度报告、依申请公开流程，以及涵盖基本信息、招生考试、财务资产与收费、人事师资、教学质量、学生服务、学风建设、学位学科、对外合作等十大类公开事项与官方通知报告全文。\n",
        f"- **学校信息公开网官方首页**：[{BASE_URL}]({BASE_URL})\n",
        "- **监督电话**：027-87934500\n",
        "- **信息公开工作机构**：学校办公室（党委办公室、校长办公室）\n",
        "- **通信地址**：湖北省武汉市东湖新技术开发区中华科技产业园玉屏大道9号（邮编：430204）\n",
        "\n---\n"
    ]

    # Part 1: Top Navigation Sections
    lines.append("## 第一部分：信息公开工作体系、制度与年度报告\n")
    for nav_title, nav_url, nav_type in top_nav:
        print(f"Crawling Top Nav: {nav_title} ({nav_url}) ...")
        lines.append(f"### 1.{top_nav.index((nav_title, nav_url, nav_type)) + 1} {nav_title}\n")
        lines.append(f"- **专栏网址**：[{nav_url}]({nav_url})\n")
        soup_nav = fetch_soup(nav_url)
        if not soup_nav:
            continue

        # Find articles in nav page
        nav_articles = []
        for a in soup_nav.find_all('a'):
            h = a.get('href', '')
            t = a.get_text(strip=True)
            if 'info/' in h and t and len(t) > 3 and not any(k in t for k in ['公开事项', '公开信息', '设为', '收藏', '查看更多']):
                full_h = urllib.parse.urljoin(nav_url, h)
                if not any(full_h == item[0] for item in nav_articles):
                    nav_articles.append((full_h, t))

        for art_url, art_title in nav_articles:
            detail = fetch_article_detail(art_url)
            if not detail:
                continue
            lines.append(f"#### 【{nav_title}】{detail['title']}\n")
            if detail['date']:
                lines.append(f"- **发布时间**：{detail['date']}")
            lines.append(f"- **官方来源链接**：[{detail['url']}]({detail['url']})\n")
            if detail['pdf_url']:
                lines.append(f"- **官方附件文档/PDF在线浏览**：[{detail['pdf_url']}]({detail['pdf_url']})\n")
            if detail['text']:
                lines.append(detail['text'])
                lines.append("\n")
            elif detail['pdf_url']:
                lines.append(f"（注：该报告/制度包含完整官方备案 PDF 文档，详见上方链接在线查阅。）\n")
            lines.append("\n")

    # Part 2: Ten Major Disclosure Groups
    lines.append("## 第二部分：十大类信息公开事项详解与官方条目\n")
    
    current_group = ""
    group_idx = 0
    for cat in category_list:
        if cat['group_name'] != current_group:
            current_group = cat['group_name']
            group_idx += 1
            lines.append(f"### 2.{group_idx} {current_group}\n")
            print(f"\nProcessing Group: {current_group} ...")

        print(f"  Category: {cat['title']} ({cat['url']}) ...")
        lines.append(f"#### 2.{group_idx}.{category_list.index(cat) + 1} {cat['title']}\n")
        lines.append(f"- **栏目网址**：[{cat['url']}]({cat['url']})\n")

        soup_cat = fetch_soup(cat['url'])
        if not soup_cat:
            continue

        # check pagination links
        all_cat_pages = [cat['url']]
        for a in soup_cat.find_all('a'):
            h = a.get('href', '')
            if h and any(h.endswith(f'/{i}.htm') for i in range(1, 4)):
                full_page = urllib.parse.urljoin(cat['url'], h)
                if full_page not in all_cat_pages:
                    all_cat_pages.append(full_page)

        # Collect articles & jump links
        cat_items = []
        for page_url in all_cat_pages:
            p_soup = fetch_soup(page_url) if page_url != cat['url'] else soup_cat
            if not p_soup:
                continue
            for a in p_soup.find_all('a'):
                h = a.get('href', '')
                t = a.get_text(strip=True)
                if h and t and len(t) > 3 and not any(k in t for k in ['首页', '公开事项', '上一页', '下一页', '尾页', '跳转', '公开信息', '设为', '收藏', '查看更多']):
                    full_h = urllib.parse.urljoin(page_url, h)
                    if not any(full_h == item[0] for item in cat_items):
                        cat_items.append((full_h, t))

        if not cat_items:
            lines.append("（本栏目依学校规程与工作动态实时更新公开事项）\n\n")
            continue

        lines.append(f"**该栏目收录的权威公开文件与项目清单**：\n")
        for item_url, item_title in cat_items:
            # Check if internal article
            if 'xxgk.qcuwh.edu.cn/info/' in item_url:
                detail = fetch_article_detail(item_url)
                if detail:
                    lines.append(f"##### 📄 {detail['title']}\n")
                    if detail['date']:
                        lines.append(f"- **发布日期**：{detail['date']}")
                    lines.append(f"- **官方原文章链接**：[{detail['url']}]({detail['url']})")
                    if detail['pdf_url']:
                        lines.append(f"- **PDF/附件直达**：[{detail['pdf_url']}]({detail['pdf_url']})")
                    lines.append("\n")
                    if detail['text']:
                        # provide text snippet or full text
                        lines.append(detail['text'])
                        lines.append("\n")
                    elif detail['pdf_url']:
                        lines.append(f"（注：该项目为官方核准公示文件，全文载于上述 PDF/附件链接中。）\n")
                else:
                    lines.append(f"- [{item_title}]({item_url})\n")
            else:
                # External jump link (e.g. cwc, zs, jw, rsc)
                lines.append(f"- 🔗 **[{item_title}]({item_url})**（直达相关业务部门官方专栏）\n")
        lines.append("\n")

    output_path = os.path.join(DOCS_DIR, 'info_disclosure.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\n===> Successfully generated info_disclosure.md! Size: {os.path.getsize(output_path)} bytes")

if __name__ == '__main__':
    crawl_info_disclosure()
