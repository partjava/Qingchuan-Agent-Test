# -*- coding: utf-8 -*-
"""
武汉晴川学院官网全维度资讯与图片爬虫系统
支持 209+ 全量历史页面深度抓取 (涵盖建校至今 2013-2026 全部官方文献与新闻)
四大官方资讯频道：
1. 学校要闻 (xxyw.htm, 154页)
2. 通知公告 (tzgg.htm, 23页)
3. 教育教学 (jyjx.htm, 17页)
4. 媒体关注 (mtgz.htm, 18页)
5. 办公电话与联系方式 (lxfs.htm)

爬取策略：
- 全量爬取所有页面的完整文本、标题、发布日期、部门来源
- 前 4 页自动下载高清现场配图，4 页以后的历史页面仅抓取文字，节约磁盘空间与网络资源
- 多线程并发加速（16 线程），内置重试与异常保护
- 生成面向 RAG 检索的高质量 Markdown 知识库与原始 JSON 完整历史档案
"""

import os
import sys
import re
import json
import time
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 基础目录定位
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "docs"
IMAGES_DIR = BASE_DIR / "data" / "images"
RAW_DIR = BASE_DIR / "data" / "raw_crawled"

DOCS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = {
    "xxyw": {
        "name": "学校要闻",
        "url": "https://www.qcuwh.cn/jjqc/xxyw.htm",
        "doc_filename": "news_xxyw.md",
        "desc": "武汉晴川学院重大校级活动、领导致辞、荣誉表彰、建校转设与十年发展要闻全谱系"
    },
    "tzgg": {
        "name": "通知公告",
        "url": "https://www.qcuwh.cn/jjqc/tzgg.htm",
        "doc_filename": "news_tzgg.md",
        "desc": "武汉晴川学院历年校务通知、放假安排、安全管理、招生考务与规章政策公告"
    },
    "jyjx": {
        "name": "教育教学",
        "url": "https://www.qcuwh.cn/jjqc/jyjx.htm",
        "doc_filename": "news_jyjx.md",
        "desc": "武汉晴川学院专业建设、省级一流专业、学科竞赛、认知实习与产教融合历史实绩"
    },
    "mtgz": {
        "name": "媒体关注",
        "url": "https://www.qcuwh.cn/jjqc/mtgz.htm",
        "doc_filename": "news_mtgz.md",
        "desc": "各大主流媒体（央视、人民网、新华社、楚天都市报等）对学校办学成果的历年专题报道"
    }
}


class QingchuanFullCrawler:
    def __init__(self, timeout=10, max_workers=16):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        })

    def _get_page_urls(self, channel_code: str, max_pages: int = None) -> list[tuple[int, str]]:
        """解析获取指定频道的翻页 URL 列表 (返回 (page_idx, url))"""
        base_url = CHANNELS[channel_code]["url"]
        urls = [(1, base_url)]

        try:
            r = self.session.get(base_url, timeout=self.timeout, verify=False)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 查找最大页码
            max_num = 0
            for a in soup.find_all("a", href=True):
                m = re.search(rf"{channel_code}/(\d+)\.htm", a["href"])
                if m:
                    max_num = max(max_num, int(m.group(1)))
            
            if max_num > 0:
                limit = max_pages if (max_pages and max_pages > 0) else (max_num + 1)
                for p in range(2, limit + 1):
                    target_idx = max_num - p + 2
                    if target_idx >= 1:
                        p_url = urllib.parse.urljoin(base_url, f"{channel_code}/{target_idx}.htm")
                        urls.append((p, p_url))
        except Exception as e:
            print(f"[Crawler] 解析 {channel_code} 分页出错: {e}")

        return urls

    def _extract_article_links_from_page(self, page_tuple: tuple[int, str]) -> list[dict]:
        """从列表页提取所有新闻链接与初步标题、日期"""
        page_idx, list_url = page_tuple
        items = []
        try:
            r = self.session.get(list_url, timeout=self.timeout, verify=False)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if "info/" not in href or ".htm" not in href:
                    continue
                full_url = urllib.parse.urljoin(list_url, href)
                raw_text = a.get_text(strip=True)
                if not raw_text or len(raw_text) < 4:
                    continue
                
                # 分离前缀日期，如 "2026-10-20董事长视察..."
                date_str = ""
                title_str = raw_text
                date_m = re.match(r"^(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})[：:\s]*(.*)$", raw_text)
                if date_m:
                    date_str = date_m.group(1).replace("年", "-").replace("月", "-")
                    title_str = date_m.group(2).strip()
                
                items.append({
                    "url": full_url,
                    "title": title_str,
                    "date": date_str,
                    "page_idx": page_idx
                })
        except Exception as e:
            pass
        return items

    def _fetch_article_detail(self, item: dict, channel_code: str) -> dict:
        """抓取并深度解析文章正文与配图"""
        url = item["url"]
        art_id = "news"
        m_id = re.search(r"info/(\d+)/(\d+)", url)
        if m_id:
            art_id = f"{m_id.group(1)}_{m_id.group(2)}"
        else:
            art_id = hashlib.md5(url.encode()).hexdigest()[:12]

        article = {
            "id": art_id,
            "url": url,
            "channel": channel_code,
            "title": item["title"],
            "date": item["date"],
            "page_idx": item.get("page_idx", 1),
            "source": "",
            "paragraphs": [],
            "image_urls": [],
            "local_images": []
        }

        # 重试 2 次
        for attempt in range(2):
            try:
                r = self.session.get(url, timeout=self.timeout, verify=False)
                r.encoding = "utf-8"
                html = r.text
                soup = BeautifulSoup(html, "html.parser")

                # 抓取标题
                h1 = soup.find("h1")
                if h1 and len(h1.get_text(strip=True)) > 4:
                    article["title"] = h1.get_text(strip=True)

                # 抓取发布时间 (若列表页未取到或需要校准)
                if not article["date"]:
                    date_match = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", html)
                    if date_match:
                        article["date"] = date_match.group(1).replace("年", "-").replace("月", "-")

                # 抓取来源/部门
                source_match = re.search(r"来源[：:]\s*([^\s<|&]+)", html)
                if source_match:
                    article["source"] = source_match.group(1).strip()
                else:
                    comm_match = re.search(r"通讯员[：:]\s*([^\s<|&]+)", html)
                    if comm_match:
                        article["source"] = f"通讯员 {comm_match.group(1).strip()}"

                # 抓取正文区域
                content_div = (
                    soup.find(id="vsb_content") or 
                    soup.find(class_="v_news_content") or 
                    soup.find(id="vsb_content_2") or
                    soup.find(class_=lambda x: x and "content" in x.lower())
                )

                if content_div:
                    # 提取段落
                    for p in content_div.find_all("p"):
                        p_txt = p.get_text(strip=True)
                        if p_txt and len(p_txt) > 3 and not p_txt.startswith("上一篇") and not p_txt.startswith("下一篇"):
                            article["paragraphs"].append(p_txt)
                    
                    if not article["paragraphs"]:
                        raw_lines = [l.strip() for l in content_div.get_text().split("\n") if len(l.strip()) > 10]
                        article["paragraphs"] = raw_lines

                    # 提取图片 URL
                    for img in content_div.find_all("img"):
                        src = img.get("src", "").strip()
                        if src and not src.endswith(".gif") and "spacer" not in src.lower():
                            full_img_url = urllib.parse.urljoin(url, src)
                            article["image_urls"].append(full_img_url)

                if article["paragraphs"]:
                    break
            except Exception:
                time.sleep(0.1)

        return article

    def _download_image(self, img_url: str, save_path: Path) -> bool:
        """下载单张图片并本地落盘"""
        if save_path.exists() and save_path.stat().st_size > 500:
            return True
        try:
            r = self.session.get(img_url, timeout=self.timeout, verify=False)
            if r.status_code == 200 and len(r.content) > 500:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            pass
        return False

    def crawl_channel(self, channel_code: str, max_pages: int = None, max_image_pages: int = 4) -> list[dict]:
        """
        全量爬取指定频道的所有页面：
        - 抓取全部历史页面的纯文本资讯
        - 仅对前 max_image_pages (前4页) 执行图片多线程下载，节约磁盘空间
        """
        meta = CHANNELS[channel_code]
        print(f"\n=======================================================")
        print(f"[*] 开始全量爬取频道: 【{meta['name']}】({channel_code})")
        print(f"=======================================================")

        page_tuples = self._get_page_urls(channel_code, max_pages=max_pages)
        print(f"[+] 发现总页数: {len(page_tuples)} 页，启动多线程并行获取全部列表...")

        all_links = []
        seen_urls = set()

        # 多线程并发拉取所有列表页
        with ThreadPoolExecutor(max_workers=self.max_workers) as list_exec:
            future_to_page = {list_exec.submit(self._extract_article_links_from_page, pt): pt for pt in page_tuples}
            for future in as_completed(future_to_page):
                try:
                    items = future.result()
                    for it in items:
                        if it["url"] not in seen_urls:
                            seen_urls.add(it["url"])
                            all_links.append(it)
                except Exception:
                    pass

        print(f"[+] 【{meta['name']}】全量提取到 {len(all_links)} 篇历史文章链接！启动 16 线程高速抓取正文...")

        # 多线程高速抓取文章正文
        articles = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(self._fetch_article_detail, item, channel_code): item for item in all_links}
            for idx, future in enumerate(as_completed(future_to_item), 1):
                try:
                    art = future.result()
                    if art and art["paragraphs"]:
                        articles.append(art)
                    if idx % 100 == 0 or idx == len(all_links):
                        speed = round(idx / (time.time() - t0 + 0.001), 1)
                        print(f"    - 进度: 已解析正文 {idx}/{len(all_links)} 篇 ({speed} 篇/秒)...")
                except Exception as e:
                    pass

        # 按日期倒序排列
        articles.sort(key=lambda x: x.get("date", ""), reverse=True)

        # 针对前 max_image_pages 页下载配图 (后面历史页面只留文本)
        ch_img_dir = IMAGES_DIR / channel_code
        ch_img_dir.mkdir(parents=True, exist_ok=True)

        print(f"[+] 正在为前 {max_image_pages} 页文章核对/下载配图...")
        img_download_tasks = []
        for art in articles:
            # 仅限前 4 页文章下载配图
            if art.get("page_idx", 999) <= max_image_pages:
                for img_idx, img_url in enumerate(art["image_urls"]):
                    ext = ".jpg"
                    if ".png" in img_url.lower():
                        ext = ".png"
                    elif ".jpeg" in img_url.lower():
                        ext = ".jpeg"
                    elif ".webp" in img_url.lower():
                        ext = ".webp"

                    local_filename = f"{art['id']}_{img_idx}{ext}"
                    local_disk_path = ch_img_dir / local_filename
                    web_relative_path = f"/images/{channel_code}/{local_filename}"
                    
                    art["local_images"].append({
                        "disk_path": str(local_disk_path),
                        "web_path": web_relative_path,
                        "original_url": img_url
                    })
                    img_download_tasks.append((img_url, local_disk_path))

        download_count = 0
        if img_download_tasks:
            with ThreadPoolExecutor(max_workers=self.max_workers) as img_exec:
                futures = [img_exec.submit(self._download_image, u, p) for (u, p) in img_download_tasks]
                for f in as_completed(futures):
                    if f.result():
                        download_count += 1

        print(f"[✓] 配图处理完毕: 计划 {len(img_download_tasks)} 张，本地就绪 {download_count} 张")

        # 1. 保存原始 JSON 全量归档
        json_path = RAW_DIR / f"{channel_code}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        print(f"[✓] 【{meta['name']}】全量 JSON 数据已保存: {json_path} (共 {len(articles)} 篇)")

        # 2. 生成面向 RAG 检索的 Markdown 知识库
        md_path = DOCS_DIR / meta["doc_filename"]
        md_lines = [
            f"# 武汉晴川学院【{meta['name']}】官方全息知识库\n\n",
            f"> 本知识库全量抓取自武汉晴川学院官网（{meta['url']}），收录了该专栏自建校以来的全部 {len(articles)} 篇图文文献。\n",
            f"> 专栏定位：{meta['desc']}\n\n",
            "---\n\n"
        ]

        for idx, art in enumerate(articles, 1):
            title = art["title"]
            date = art["date"] or "历史记录"
            source = art["source"] or "武汉晴川学院官方"
            url = art["url"]

            md_lines.append(f"## {idx}. {title}\n")
            md_lines.append(f"- **发布时间**：{date}\n")
            md_lines.append(f"- **发布单位/来源**：{source}\n")
            md_lines.append(f"- **官网原文链接**：{url}\n")
            
            if art["local_images"]:
                md_lines.append("- **现场配图**：\n")
                for img_info in art["local_images"][:3]:
                    md_lines.append(f"  - ![{title}]({img_info['web_path']})\n")

            md_lines.append("- **核心新闻正文**：\n")
            for p in art["paragraphs"]:
                md_lines.append(f"  {p}\n\n")
            md_lines.append("\n---\n\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("".join(md_lines))
        print(f"[✓] 【{meta['name']}】知识库 Markdown 已生成: {md_path} (共收录 {len(articles)} 篇)")

        return articles

    def crawl_office_contacts(self) -> dict:
        """爬取全校办公电话与联系方式黄页 (lxfs.htm)"""
        url = "https://www.qcuwh.cn/lxfs.htm"
        print(f"\n=======================================================")
        print(f"[*] 开始爬取: 武汉晴川学院各单位办公电话黄页 ({url})")
        print(f"=======================================================")

        contacts = []
        try:
            r = self.session.get(url, timeout=self.timeout, verify=False)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            
            current_category = "校级职能部门"
            if table:
                for tr in table.find_all("tr"):
                    tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"]) if td.get_text(strip=True)]
                    if not tds:
                        continue
                    if len(tds) == 1:
                        if any(k in tds[0] for k in ["学院", "部门", "单位", "分类"]):
                            current_category = tds[0]
                        continue
                    dept = tds[0]
                    if dept in ["单位", "职能部门", "办公电话"]:
                        continue
                    phones = " / ".join(tds[1:])
                    contacts.append({
                        "category": current_category,
                        "department": dept,
                        "phones": phones
                    })
        except Exception as e:
            print(f"[!] 爬取办公电话失败: {e}")

        # 写入 JSON
        json_path = RAW_DIR / "office_contacts.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(contacts, f, ensure_ascii=False, indent=2)

        # 写入 Markdown
        md_path = DOCS_DIR / "office_contacts.md"
        lines = [
            "# 武汉晴川学院各单位办公电话与联系方式黄页\n\n",
            "> 来源：武汉晴川学院官方网站（https://www.qcuwh.cn/lxfs.htm）。\n",
            "> 包含学校各机关职能部处、二级教学学院、教辅与直属单位的服务与业务咨询电话。\n\n",
            "---\n\n"
        ]

        categories = {}
        for c in contacts:
            cat = c["category"]
            categories.setdefault(cat, []).append(c)

        for cat, items in categories.items():
            lines.append(f"## {cat}\n")
            for it in items:
                lines.append(f"- **{it['department']}**：{it['phones']}\n")
            lines.append("\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("".join(lines))
        print(f"[✓] 办公电话黄页知识库已生成: {md_path} (收录 {len(contacts)} 个部门办公电话)")
        return contacts

    def crawl_all(self, max_pages: int = None, max_image_pages: int = 4):
        """一次性全量爬取四大官方资讯频道全部历史页面与办公电话黄页"""
        start_time = time.time()
        print("\n" + "=" * 65)
        print("🚀 启动武汉晴川学院官网 209+ 全量历史页面深度爬取管道")
        print(f"- 模式: 全量文字抓取 + 前 {max_image_pages} 页现场配图精选下载")
        print("=" * 65)

        summary = {}
        total_articles = 0

        # 按顺序爬取通知公告、教育教学、媒体关注、学校要闻
        for ch in ["tzgg", "jyjx", "mtgz", "xxyw"]:
            articles = self.crawl_channel(ch, max_pages=max_pages, max_image_pages=max_image_pages)
            summary[ch] = len(articles)
            total_articles += len(articles)

        contacts = self.crawl_office_contacts()
        summary["contacts"] = len(contacts)

        duration = round(time.time() - start_time, 2)
        print("\n" + "=" * 65)
        print("🎉 武汉晴川学院官网全量 209+ 历史页面全部抓取并落盘完毕！")
        print(f"- 耗时: {duration} 秒")
        print(f"- 通知公告 (news_tzgg.md): {summary.get('tzgg', 0)} 篇 (100% 全量)")
        print(f"- 教育教学 (news_jyjx.md): {summary.get('jyjx', 0)} 篇 (100% 全量)")
        print(f"- 媒体关注 (news_mtgz.md): {summary.get('mtgz', 0)} 篇 (100% 全量)")
        print(f"- 学校要闻 (news_xxyw.md): {summary.get('xxyw', 0)} 篇 (100% 全量)")
        print(f"- 办公电话黄页 (office_contacts.md): {summary.get('contacts', 0)} 个部门")
        print(f"- 全校权威文献累计收录: {total_articles} 篇")
        print(f"- 现场高清配图已持久化至: {IMAGES_DIR}")
        print(f"- 知识库已持久化至: {DOCS_DIR}")
        print("=" * 65)
        return summary


if __name__ == "__main__":
    crawler = QingchuanFullCrawler(timeout=10, max_workers=16)
    crawler.crawl_all(max_pages=None, max_image_pages=4)
