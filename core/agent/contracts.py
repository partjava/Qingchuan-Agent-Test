"""Small public decision contract; deliberately excludes model reasoning."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class SearchArguments(StrictModel):
    query: str = Field(min_length=1, max_length=500)


class PlaceArguments(StrictModel):
    name: str = Field(min_length=1, max_length=80)


class RouteArguments(StrictModel):
    from_id: str = Field(min_length=1, max_length=64)
    to_id: str = Field(min_length=1, max_length=64)


class EmptyArguments(StrictModel):
    pass


ARGUMENTS = {'search_knowledge': SearchArguments, 'lookup_place': PlaceArguments,
             'plan_route': RouteArguments, 'current_time': EmptyArguments}


class ToolAction(StrictModel):
    action: Literal['tool']
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict


class PlanStep(StrictModel):
    instruction: str = Field(min_length=1, max_length=240)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)


class FinishAction(StrictModel):
    action: Literal['finish']
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    missing: list[str] = Field(default_factory=list, max_length=8)
    plan: list[PlanStep] = Field(default_factory=list, max_length=8)
    precautions: list[PlanStep] = Field(default_factory=list, max_length=6)


class ClarifyAction(StrictModel):
    action: Literal['clarify']
    question: str = Field(min_length=1, max_length=300)


DECISION = TypeAdapter(ToolAction | FinishAction | ClarifyAction)

TOOL_DESCRIPTIONS = [
    {'name':'search_knowledge', 'arguments':{'query':'校园事项的完整问题，最多500字'},
     'description':'查询本地知识库，返回可引用事实。政策事实与开放时间必须先查询，不能凭常识补全。'},
    {'name':'lookup_place', 'arguments':{'name':'地标ID或中文名称'},
     'description':'查找地图内置地点及可用于路线工具的ID；未知或歧义时返回候选，不能猜测机构所在楼栋。'},
    {'name':'plan_route', 'arguments':{'from_id':'已确认的地标ID', 'to_id':'已确认的地标ID'},
     'description':'在保存的示意路网内计算路线，不代表真实距离或实时路况；先查证两个地点ID。'},
    {'name':'current_time', 'arguments':{},
     'description':'查询上海时区当前日期。今天/明天等时间必须使用本工具；不能据此确认政策仍有效。'},
]
