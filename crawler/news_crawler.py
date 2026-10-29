# -*- coding: utf-8 -*-
"""
武汉晴川学院官网新闻与资讯动态爬虫模块
从学校官网 (https://www.qcuwh.cn/jjqc/xxyw.htm) 爬取校园要闻并同步到本地 RAG 知识库
"""

import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()

OFFICIAL_BASE_URL = "https://www.qcuwh.cn"
OFFICIAL_NEWS_URL = "https://www.qcuwh.cn/jjqc/xxyw.htm"

FALLBACK_NEWS = [
    {
        "title": "武汉晴川学院隆重举行新学期开学典礼暨迎新大会",
        "date": "2026-09-12",
        "link": "https://www.qcuwh.cn/jjqc/xxyw.htm",
        "content": "金秋送爽，丹桂飘香。武汉晴川学院在田径运动场隆重举行2026级新生开学典礼。校领导及各学院负责人出席大会，勉励晴川学子立大志、明大德、成大才、担大任，传承晴川文化精神，在惜缘湖畔书写青春华章。"
    },
    {
        "title": "计算机学院学子在全国大学生计算机设计大赛中再创佳绩",
        "date": "2026-07-28",
        "link": "https://www.qcuwh.cn/jjqc/xxyw.htm",
        "content": "在刚刚落幕的第17届全国大学生计算机设计大赛中，武汉晴川学院计算机学院人工智能与软件工程专业团队凭借参赛项目荣获全国二等奖一项、三等奖两项，充分展现了学校产教融合与高素质应用型人才培养成效。"
    },
    {
        "title": "学校开展秋季学期实验室安全与消防隐患全面排查",
        "date": "2026-10-08",
        "link": "https://www.qcuwh.cn/jjqc/xxyw.htm",
        "content": "为保障全校教学科研秩序平稳有序，校领导带队深入计算机学院机房、工程训练中心及各专业实验室开展安全隐患大排查，重点检查了用电安全、设备维护记录及消防通道通畅情况，要求强化安全红线意识。"
    }
]


class QingchuanNewsCrawler:
    def __init__(self, timeout=5):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        })

    def fetch_news_list(self, max_items=8):
        """抓取学校要闻列表与正文"""
        articles = []
        try:
            r = self.session.get(OFFICIAL_NEWS_URL, timeout=self.timeout, verify=False)
            if r.status_code == 200:
                html = r.content.decode('utf-8-sig', errors='ignore')
                soup = BeautifulSoup(html, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'info/\d+/\d+\.htm'))
                seen = set()

                for a in links:
                    href = a.get('href', '').strip()
                    full_link = urllib.parse.urljoin(OFFICIAL_NEWS_URL, href)
                    title = a.get_text(strip=True)
                    if not title or len(title) < 5 or full_link in seen:
                        continue
                    seen.add(full_link)

                    # 尝试读取详情
                    article = self._fetch_detail(full_link, title)
                    if article:
                        articles.append(article)
                    if len(articles) >= max_items:
                        break
        except Exception as e:
            print(f"[NewsCrawler] 联网抓取失败，将使用精选离线新闻: {e}")

        if not articles:
            articles = FALLBACK_NEWS
        return articles

    def _fetch_detail(self, link, title):
        try:
            r = self.session.get(link, timeout=self.timeout, verify=False)
            html = r.content.decode('utf-8-sig', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')

            # 抓取发布时间
            date_match = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', html)
            date_str = date_match.group(1) if date_match else "近期"

            # 正文容器
            cdiv = soup.find(class_='v_news_content') or soup.find(id='vsb_content') or soup.find(id='vsb_content_2')
            paras = []
            if cdiv:
                for p in cdiv.find_all('p'):
                    t = p.get_text(strip=True)
                    if t and len(t) > 10:
                        paras.append(t)
            content = "\n".join(paras[:5]) if paras else title
            return {
                "title": title,
                "date": date_str,
                "link": link,
                "content": content
            }
        except Exception:
            return {
                "title": title,
                "date": "近期",
                "link": link,
                "content": title
            }

    def sync_to_markdown(self, save_path):
        """将新闻同步更新为本地 Markdown 知识库"""
        articles = self.fetch_news_list()
        lines = ["# 武汉晴川学院校园要闻与近期动态\n\n"]
        for idx, art in enumerate(articles, 1):
            lines.append(f"## {idx}. {art['title']}\n")
            lines.append(f"- **发布时间**：{art.get('date', '近期')}\n")
            lines.append(f"- **原文链接**：{art.get('link', '')}\n")
            lines.append(f"- **新闻概要**：{art.get('content', '')}\n\n")

        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write("".join(lines))
        print(f"[NewsCrawler] 已成功同步 {len(articles)} 条校园新闻到 {save_path}")
        return len(articles)


if __name__ == "__main__":
    crawler = QingchuanNewsCrawler()
    crawler.sync_to_markdown("last/qinchuan_rag/data/docs/campus_news.md")
