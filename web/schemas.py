"""请求约束独立于模型初始化，便于验证和复用。"""
from typing import Literal
from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Literal['hybrid', 'bge', 'tfidf'] = 'hybrid'
    top_k: int = Field(default=3, ge=1, le=10)
    use_ollama: bool = False
    deepseek_key: str | None = None
    model: str | None = None
    api_url: str | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    thinking: bool = False
    session_id: str | None = 'web_session'
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
