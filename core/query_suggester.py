# -*- coding: utf-8 -*-
"""
智能相关问题推荐模块 (Intelligent Query Suggester)
基于实体识别、用户提问意图与检出的晴川知识库主题，生成 3 个高度相关的延伸追问。
"""

from typing import List, Dict, Any

class CampusQuerySuggester:
    """晴川校园智能追问推荐引擎"""

    def __init__(self):
        # 预设基于实体/意图的专业推荐问句池
        self.entity_suggestions = {
            "晴川图书馆": [
                "晴川图书馆开放时间是几点？周末和节假日开馆吗？",
                "普通本科生在图书馆最多可以借阅多少册图书？借期多长？",
                "考研自习专座如何申请与选座？超期未签到会取消资格吗？"
            ],
            "计算机学院": [
                "计算机学院开设了哪些特色本科专业？",
                "计算机学院实验机房开放时间和课后预约规则是什么？",
                "怎么从正大门走到教1栋（计算机学院办公教学楼）？"
            ],
            "机械与电气工程学院": [
                "机械与电气工程学院有哪些专业？建有哪些省级实验中心？",
                "机电学院的官方网站地址是什么？有哪些大标题导航？",
                "怎么去笃行楼（教2栋机电学院）？"
            ],
            "商学院": [
                "商学院的电子商务专业是国家级一流本科课程吗？",
                "商学院开设了哪些专业？有跨境电商人才培养基地吗？",
                "商学院的办公电话和教务科电话是多少？"
            ],
            "教务处": [
                "选课退改选通常在开学第几周截止？",
                "大四毕业资格预审在第几周开展？学分不够如何处理？",
                "在校本科生申请转专业的条件和流程是什么？"
            ],
            "奖学金": [
                "晴川奖学金和综合奖学金的金额标准分别是多少？",
                "评选奖学金对上一学年课程有挂科/不及格要求吗？",
                "国家奖学金和国家励志奖学金的申请时间与名额评定流程是怎样的？"
            ],
            "选课": [
                "新学期选课退改选在第几周周五几点截止？",
                "选课超期后如何提交教务处人工复核审批？",
                "每学期修读课程学分的上限和下限是多少？"
            ],
            "毕业": [
                "第14周毕业资格预审需要审核哪些学分材料？",
                "发现个人毕业信息或学分有误，时限内如何勘误？",
                "应届本科毕业生申请学士学位的绩点门槛是多少？"
            ],
            "一食堂": [
                "一食堂、二食堂就餐高峰期是几点？支持哪些支付方式？",
                "从教1栋去一食堂步行怎么走？",
                "校园卡充值和挂失在哪个部门办理？"
            ],
            "汪彬": [
                "汪彬董事长的学术背景与办学教育理念是什么？",
                "汪彬校长作词的晴川校歌《晴川颂》歌词全文是什么？",
                "学校董事会与现任党政领导班子由哪些专家组成？"
            ],
            "校训": [
                "晴川学院的校训‘明体达用、抱璞开新’出自哪里？有什么历史内涵？",
                "学校精神‘仁爱天下、克难奋进’的深刻寓意是什么？",
                "晴川学院20周年校庆LOGO的造型构想是什么？"
            ]
        }

        # 默认兜底高频推荐
        self.default_suggestions = [
            "从南大门怎么走到晴川图书馆？",
            "选课退改选通常在第几周截止？超期如何处理？",
            "晴川学院一等综合奖学金金额是多少？评定条件是什么？",
            "计算机学院有哪些特色专业和产业学院？",
            "晴川学院有哪些特色校园文化品牌活动？"
        ]

    def suggest(self, query: str, entities: List[Dict[str, Any]], citations: List[Dict[str, Any]]) -> List[str]:
        suggestions = []

        # 1. 优先根据识别到的实体推荐
        for ent in entities:
            t = ent["text"]
            for key, rec_list in self.entity_suggestions.items():
                if key in t or t in key:
                    for rec in rec_list:
                        if rec not in suggestions and rec != query:
                            suggestions.append(rec)
                            if len(suggestions) >= 3:
                                return suggestions[:3]

        # 2. 检查用户提问关键词
        for key, rec_list in self.entity_suggestions.items():
            if key in query:
                for rec in rec_list:
                    if rec not in suggestions and rec != query:
                        suggestions.append(rec)
                        if len(suggestions) >= 3:
                            return suggestions[:3]

        # 3. 检查检索来源文档主题
        if citations:
            first_doc = citations[0].get("source", "")
            if "course_selection" in first_doc or "graduation" in first_doc:
                for rec in self.entity_suggestions["选课"] + self.entity_suggestions["毕业"]:
                    if rec not in suggestions and rec != query:
                        suggestions.append(rec)
            elif "scholarship" in first_doc:
                for rec in self.entity_suggestions["奖学金"]:
                    if rec not in suggestions and rec != query:
                        suggestions.append(rec)
            elif "campus_landmarks" in first_doc:
                suggestions.extend([
                    "从博学楼去一食堂怎么走？",
                    "晴川图书馆在校园哪个位置？",
                    "晴韵大道和仁爱路在哪里？"
                ])

        # 4. 补充默认推荐至满 3 条
        for d in self.default_suggestions:
            if d not in suggestions and d != query:
                suggestions.append(d)
                if len(suggestions) >= 3:
                    break

        return suggestions[:3]
