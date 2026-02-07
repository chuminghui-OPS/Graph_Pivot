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
    book_type: Optional[str] = None
    word_count: Optional[int] = None


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


class ApiAssetCreate(BaseModel):
    name: str
    provider: str
    api_mode: str = "openai_compatible"
    api_key: str = ""
    base_url: Optional[str] = None
    api_path: Optional[str] = None
    models: Optional[List[str]] = None


class ApiAssetUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_mode: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_path: Optional[str] = None
    models: Optional[List[str]] = None


class ApiAssetOut(BaseModel):
    id: str
    name: str
    provider: str
    api_mode: str = "openai_compatible"
    api_key_masked: str = ""
    base_url: Optional[str] = None
    api_path: Optional[str] = None
    models: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DiscoverModelsResponse(BaseModel):
    models: List[str] = Field(default_factory=list)


class ApiManagerBase(BaseModel):
    name: str
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None


class ApiManagerCreate(ApiManagerBase):
    pass


class ApiManagerUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class ApiManagerOut(BaseModel):
    id: str
    name: str
    provider: str
    api_key_masked: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ApiSettingsCreate(BaseModel):
    name: str = "default"
    provider: str
    api_mode: str = "openai_compatible"
    api_key: str
    base_url: Optional[str] = None
    api_path: Optional[str] = None
    model: Optional[str] = None


class UserSettingsOut(BaseModel):
    default_asset_id: Optional[str] = None
    default_model: Optional[str] = None


class SettingsResponse(UserSettingsOut):
    assets: List[ApiAssetOut] = Field(default_factory=list)


class PublishBookRequest(BaseModel):
    title: Optional[str] = None
    cover_url: Optional[str] = None


class PublishBookByIdRequest(PublishBookRequest):
    book_id: str


class PublicBookOut(BaseModel):
    id: str
    title: str
    cover_url: Optional[str] = None
    owner_user_id: str
    favorites_count: int = 0
    reposts_count: int = 0
    published_at: Optional[str] = None
    updated_at: Optional[str] = None


class LLMUsageSummary(BaseModel):
    provider: str
    model: Optional[str] = None
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


class BookUsageResponse(BaseModel):
    book_id: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    by_model: List[LLMUsageSummary] = Field(default_factory=list)


class UserUsageBookRow(BaseModel):
    book_id: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
