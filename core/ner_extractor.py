# -*- coding: utf-8 -*-
"""
命名实体识别 (Named Entity Recognition - NER) 模块
专为晴川校园信息智能问答系统打造，支持识别：
1. LOC (校园地标与建筑环境)
2. ORG (二级学院、职能部处与群团组织)
3. RULE_MAJOR (校纪校规、培养条例与优势学科专业)
4. PER (校领导、知名学者与校友名人)
"""

import re
from typing import List, Dict, Any

CAMPUS_LOCATIONS = [
    "晴川图书馆", "博学楼", "笃行楼", "尚美楼", "行政综合楼", "晴川大礼堂",
    "教1栋", "教2栋", "教3栋", "教学1栋", "教学2栋", "教学3栋",
    "一食堂", "二食堂", "三食堂", "学生第一食堂", "学生第二食堂", "学生第三食堂", "食堂", "晴川食堂", "主食堂", "大食堂",
    "正大门", "南大门", "北大门", "东门", "西大门", "南门", "校门", "校门口", "大门", "正门",
    "情缘湖", "惜缘湖", "龙泉山", "梧桐湖", "迎宾大道", "晴韵大道", "仁爱路", "德馨路",
    "田径场", "晴川田径运动场", "田径运动场", "操场", "足球场", "体育场", "运动场", "体育馆", "室内综合体育馆", "风雨操场", "网球场", "篮球场", "排球场", "羽毛球馆", "乒乓球馆",
    "竹蜻蜓飞行基地", "校医院", "大学生活动中心", "创客中心", "众创空间", "融媒体中心",
    "梅苑", "兰苑", "竹苑", "菊苑", "桃苑", "李苑", "学生宿舍"
]

CAMPUS_ORGANIZATIONS = [
    "计算机学院", "机械与电气工程学院", "北斗学院", "电子信息学院", "商学院",
    "会计学院", "外国语学院", "传媒艺术学院", "设计工程学院", "马克思主义学院",
    "基础课部", "学校办公室", "发展规划办公室", "党委组织部", "党委宣传部", "党委统战部",
    "纪检监察办公室", "教务处", "人事处", "教师工作部", "学生工作处", "学工处", "人民武装部",
    "招生办公室", "招生办", "就业指导与服务中心", "就业中心", "创新创业学院", "财务处",
    "教学质量管理处", "评估中心", "科研处", "学科建设办公室", "实验室管理中心", "实验中心",
    "资产设备管理处", "网络信息中心", "网络中心", "后勤保卫处", "保卫处", "心理健康教育中心",
    "校团委", "工会", "校友会", "晴川艺术团", "晴川赛艇队", "国旗护卫队", "青年志愿者协会"
]

CAMPUS_RULES_AND_MAJORS = [
    "晴川奖学金", "综合奖学金", "国家奖学金", "国家励志奖学金", "学业奖学金",
    "退改选管理办法", "退改选办法", "选课管理办法", "选课规定",
    "毕业资格预审", "毕业预审", "学籍管理规定", "学籍管理办法", "学士学位授予细则",
    "转专业管理规定", "转专业办法", "考试违规处理办法", "学生违纪处分办法", "学生申诉办法",
    "实验室开放规范", "机房开放管理规范", "考研专座管理办法", "专业实习管理规范", "学生手册",
    "软件工程", "人工智能", "计算机科学与技术", "物联网工程", "数据科学与大数据技术",
    "电气工程及其自动化", "机械设计制造及其自动化", "机器人工程", "电子信息工程", "通信工程",
    "电子商务", "跨境电子商务", "国际经济与贸易", "市场营销", "物流管理",
    "会计学", "财务管理", "审计学", "英语", "商务英语", "网络与新媒体", "新闻学",
    "环境设计", "视觉传达设计", "数字媒体艺术", "产品设计"
]

CAMPUS_PERSONS = [
    "汪彬", "刘经南", "李德仁", "李敬一", "彭宇文", "张涛", "张克华", "向巍",
    "罗宏运", "汪澄", "翟细春", "杜晓玲", "周汉生", "朱宾忠", "易静", "汪艳妮"
]

class QingchuanNERExtractor:
    """晴川命名实体识别抽取器"""
    
    def __init__(self):
        # 预编译正则模式，按长度降序保证最长匹配优先
        self.loc_pattern = re.compile('|'.join(sorted([re.escape(x) for x in CAMPUS_LOCATIONS], key=len, reverse=True)))
        self.org_pattern = re.compile('|'.join(sorted([re.escape(x) for x in CAMPUS_ORGANIZATIONS], key=len, reverse=True)))
        self.rule_pattern = re.compile('|'.join(sorted([re.escape(x) for x in CAMPUS_RULES_AND_MAJORS], key=len, reverse=True)))
        self.per_pattern = re.compile('|'.join(sorted([re.escape(x) for x in CAMPUS_PERSONS], key=len, reverse=True)))

    def extract(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []
            
        entities = []
        seen_spans = set()
        
        # 1. 地标匹配
        for m in self.loc_pattern.finditer(text):
            span = (m.start(), m.end())
            if not any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                seen_spans.add(span)
                entities.append({
                    "text": m.group(),
                    "type": "LOC",
                    "label": "校园地标",
                    "color": "#10b981", # 绿色
                    "icon": "📍",
                    "start": m.start(),
                    "end": m.end()
                })

        # 2. 机构学院匹配
        for m in self.org_pattern.finditer(text):
            span = (m.start(), m.end())
            if not any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                seen_spans.add(span)
                entities.append({
                    "text": m.group(),
                    "type": "ORG",
                    "label": "学院机构",
                    "color": "#3b82f6", # 蓝色
                    "icon": "🏛️",
                    "start": m.start(),
                    "end": m.end()
                })

        # 3. 规章学科匹配
        for m in self.rule_pattern.finditer(text):
            span = (m.start(), m.end())
            if not any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                seen_spans.add(span)
                entities.append({
                    "text": m.group(),
                    "type": "RULE",
                    "label": "规章学科",
                    "color": "#f59e0b", # 琥珀金
                    "icon": "📜",
                    "start": m.start(),
                    "end": m.end()
                })

        # 4. 人物学者匹配
        for m in self.per_pattern.finditer(text):
            span = (m.start(), m.end())
            if not any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                seen_spans.add(span)
                entities.append({
                    "text": m.group(),
                    "type": "PER",
                    "label": "知名学者",
                    "color": "#8b5cf6", # 紫色
                    "icon": "👤",
                    "start": m.start(),
                    "end": m.end()
                })

        # 去重且保持出现顺序
        entities.sort(key=lambda x: x["start"])
        return entities
