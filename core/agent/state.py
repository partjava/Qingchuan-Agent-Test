"""Per-invocation LangGraph state; persistent conversation history stays in AgentStore."""
from typing import Any
from typing_extensions import TypedDict

from .contracts import FinishAction, PlanStep, ToolAction


class AgentState(TypedDict):
    question: str
    messages: list[dict[str, str]]
    run_id: str
    start: float
    deadline: float
    step: int
    turn_started: float
    decision: ToolAction | FinishAction | None
    trace: list[dict[str, Any]]
    facts: dict[str, dict[str, Any]]
    selected: list[str]
    missing: list[str]
    plan: list[PlanStep]
    precautions: list[PlanStep]
    plan_attempts: int
    plan_status: str
    stop: str
    clarification: str
    called: bool
    last_action: str | None
    invalid_count: int
    node_trace: list[str]
    result: dict[str, Any]
