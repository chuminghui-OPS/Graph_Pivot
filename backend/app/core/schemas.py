from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


ChapterStatus = Literal[
    "PENDING",
    "PROCESSING",
    "DONE",
    "FAILED",
    "SKIPPED_TOO_LARGE",
    "TIMEOUT",
    "PAUSED",
]


class UploadResponse(BaseModel):
    book_id: str
    filename: str


class ProcessResponse(BaseModel):
    book_id: str
    task_id: str
    status: str = "queued"


class ChapterOut(BaseModel):
    chapter_id: str
    title: str
    status: ChapterStatus


class ChapterListResponse(BaseModel):
    book_id: str
    llm_provider: str
    llm_model: str
    chapters: List[ChapterOut]


class ChapterMarkdownResponse(BaseModel):
    chapter_id: str
    markdown: str


class GraphNode(BaseModel):
    id: str
    name: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    evidence: str
    confidence: float = 0.5


class KnowledgeGraph(BaseModel):
    chapter_id: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class LLMEntity(BaseModel):
    name: str
    type: str
    count: int = 1


class LLMRelation(BaseModel):
    source: str
    target: str
    relation: str
    evidence: str


class LLMChunkResult(BaseModel):
    entities: List[LLMEntity] = Field(default_factory=list)
    relations: List[LLMRelation] = Field(default_factory=list)


class UserProfile(BaseModel):
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    plan: str = "Free"
    total_books: int = 0


class UserBook(BaseModel):
    book_id: str
    title: str
    created_at: Optional[str] = None


class ApiAssetBase(BaseModel):
    name: str
    provider: str
    api_mode: str = "openai_compatible"
    api_key: str
    base_url: Optional[str] = None
    api_path: Optional[str] = None
    models: Optional[List[str]] = None


class ApiAssetCreate(ApiAssetBase):
    pass


class ApiAssetUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_mode: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_path: Optional[str] = None
    models: Optional[List[str]] = None


class ApiAssetOut(ApiAssetBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
