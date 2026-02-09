from __future__ import annotations

import os
import shutil
from urllib.parse import quote
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.core.book_types import normalize_book_type
from app.core.database import get_db
from app.core.config import settings
from app.core.schemas import (
    ChapterListResponse,
    ChapterMarkdownResponse,
    KnowledgeGraph,
    ProcessResponse,
    UploadResponse,
    GraphNodeCreate,
    GraphNodeUpdate,
    GraphEdgeCreate,
    GraphEdgeUpdate,
    PublishBookRequest,
    PublishBookByIdRequest,
    PublicBookOut,
    BookUsageResponse,
    LLMUsageSummary,
)
from app.core.celery_app import celery_app
from app.core.auth import UserContext, get_current_user
from app.models import (
    Book,
    Chapter,
    ChapterGraph,
    ApiAsset,
    PublicBook,
    LLMUsageEvent,
    Chunk,
    PublicBookFavorite,
    PublicBookRepost,
)
from app.services.llm_service import get_llm_info
from app.services.md_service import load_chapter_text
from app.services.statistics import record_book_upload
from app.utils.file_store import ensure_book_dir, new_book_id


# API 路由器：图书相关接口
router = APIRouter()
# 进程内记录每本书的 LLM 选择（非持久化）
BOOK_LLM_PROVIDER: dict[str, str] = {}

_STATUS_MAP = {
    "pending": "PENDING",
    "processing": "PROCESSING",
    "done": "DONE",
    "failed": "FAILED",
    "paused": "PAUSED",
}


def _ensure_graph_payload(graph_json: dict, chapter_id: str) -> dict:
    payload = graph_json or {}
    payload["chapter_id"] = chapter_id
    payload.setdefault("nodes", [])
    payload.setdefault("edges", [])
    return payload


def _ensure_edge_ids(graph_json: dict) -> bool:
    changed = False
    for edge in graph_json.get("edges", []):
        if not edge.get("id"):
            edge["id"] = uuid4().hex
            changed = True
    return changed


def _get_latest_graph_row(db: Session, chapter: Chapter) -> ChapterGraph | None:
    return (
        db.query(ChapterGraph)
        .filter(ChapterGraph.chapter_id == chapter.id)
        .order_by(ChapterGraph.id.desc())
        .first()
    )


def _get_editable_graph(db: Session, chapter: Chapter) -> ChapterGraph:
    graph_row = _get_latest_graph_row(db, chapter)
    if graph_row:
        graph_row.graph_json = _ensure_graph_payload(
            graph_row.graph_json, chapter.chapter_id
        )
        if _ensure_edge_ids(graph_row.graph_json):
            db.commit()
        return graph_row

    graph_row = ChapterGraph(
        id=f"{chapter.id}:{uuid4().hex}",
        chapter_id=chapter.id,
        graph_json=_ensure_graph_payload({}, chapter.chapter_id),
    )
    db.add(graph_row)
    db.commit()
    db.refresh(graph_row)
    return graph_row


def _normalize_status(value: str) -> str:
    return _STATUS_MAP.get(value, value)


def _refresh_book_status(db: Session, book_id: str) -> None:
    remaining = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.status.in_(["PENDING", "PROCESSING"]))
        .count()
    )
    if remaining:
        return
    any_failed = (
        db.query(Chapter)
        .filter(
            Chapter.book_id == book_id,
            Chapter.status.in_(["FAILED", "SKIPPED_TOO_LARGE", "TIMEOUT"]),
        )
        .count()
        > 0
    )
    book = db.get(Book, book_id)
    if book:
        book.status = "failed" if any_failed else "done"
        db.commit()


def _can_access_book(db: Session, book: Book, user: UserContext) -> bool:
    if book.user_id == user.user_id:
        return True
    return db.get(PublicBook, book.id) is not None


# 上传 PDF 并创建书籍记录
@router.post("/upload", response_model=UploadResponse)
async def upload_book(
    file: UploadFile = File(...),
    book_type: str = Form(...),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    normalized_type = normalize_book_type(book_type)

    # 生成 book_id 并写入磁盘
    # 先用 0 作为字数占位，稍后异步估算并回填 word_count
    book_id = new_book_id(normalized_type, 0)
    for _ in range(5):
        if not db.get(Book, book_id):
            break
        book_id = new_book_id(normalized_type, 0)
    book_dir = ensure_book_dir(book_id)
    pdf_path = os.path.join(book_dir, "source.pdf")
    with open(pdf_path, "wb") as buffer:
        file.file.seek(0)
        shutil.copyfileobj(file.file, buffer)

    # 写入数据库
    book = Book(
        id=book_id,
        user_id=user.user_id,
        book_type=normalized_type,
        word_count=0,
        filename=file.filename,
        pdf_path=pdf_path,
        status="uploaded",
        last_seen_at=datetime.utcnow(),
    )
    db.add(book)
    db.commit()
    record_book_upload(db, normalized_type, book_id)
    # 异步估算字数并回填
    celery_app.send_task("app.tasks.pipeline.estimate_book_units", args=[book_id])

    return UploadResponse(
        book_id=book_id,
        filename=file.filename,
        book_type=normalized_type,
        word_count=None,
    )


# 触发全书处理流水线
@router.post("/{book_id}/process", response_model=ProcessResponse)
def process_book(
    book_id: str,
    llm: str = Query("qwen", description="llm provider: gemini, qwen, or custom"),
    asset_id: str | None = Query(None, description="LLM asset id"),
    asset_model: str | None = Query(None, description="LLM model name"),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ProcessResponse:
    book = db.get(Book, book_id)
    if not book or not _can_access_book(db, book, user):
        raise HTTPException(status_code=404, detail="Book not found.")

    provider = llm.lower()
    if provider != "custom":
        raise HTTPException(status_code=400, detail="Only custom assets are supported.")
    if not asset_id:
        raise HTTPException(status_code=400, detail="Asset id is required.")

    if asset_id:
        asset = db.get(ApiAsset, asset_id)
        if not asset or asset.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="Asset not found.")
        if not asset.models:
            raise HTTPException(status_code=400, detail="Asset has no models configured.")
        if not asset_model:
            raise HTTPException(status_code=400, detail="Asset model is required.")
        if asset_model not in asset.models:
            raise HTTPException(status_code=400, detail="Asset model not in configured list.")
        book.llm_asset_id = asset_id
        book.llm_model = asset_model
        provider = "custom"
    else:
        book.llm_asset_id = None
        book.llm_model = None

    BOOK_LLM_PROVIDER[book_id] = provider
    book.processing_started_at = datetime.utcnow()
    book.last_error = None
    book.last_seen_at = datetime.utcnow()
    db.commit()
    # 通过 Celery 派发任务
    task = celery_app.send_task("app.tasks.pipeline.process_book", args=[book_id, provider])
    return ProcessResponse(book_id=book_id, task_id=task.id, status="queued")


# 前端心跳：保持书籍处理活跃
@router.post("/{book_id}/heartbeat")
def heartbeat_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    book = db.get(Book, book_id)
    if not book or not _can_access_book(db, book, user):
        raise HTTPException(status_code=404, detail="Book not found.")
    book.last_seen_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "book_id": book_id, "last_seen_at": book.last_seen_at.isoformat()}


# 获取章节列表与状态
@router.get("/{book_id}/chapters", response_model=ChapterListResponse)
def list_chapters(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ChapterListResponse:
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")
    if book.status.startswith("failed:"):
        message = book.status.split(":", 1)[1] if ":" in book.status else "PDF 解析失败"
        raise HTTPException(status_code=400, detail=message)

    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.order_index)
        .all()
    )
    now = datetime.utcnow()
    updated = False
    for chapter in chapters:
        normalized = _normalize_status(chapter.status)
        if normalized != chapter.status:
            chapter.status = normalized
            updated = True
        if chapter.status == "PROCESSING" and chapter.processing_started_at:
            timeout_seconds = settings.chapter_processing_timeout_seconds
            if timeout_seconds > 0 and now - chapter.processing_started_at > timedelta(
                seconds=timeout_seconds
            ):
                chapter.status = "TIMEOUT"
                updated = True
    if updated:
        db.commit()
        _refresh_book_status(db, book_id)
    llm_info = get_llm_info(BOOK_LLM_PROVIDER.get(book_id))
    if book.llm_asset_id:
        asset = db.get(ApiAsset, book.llm_asset_id)
        if asset:
            llm_info = {
                "provider": asset.provider,
                "model": book.llm_model or (asset.models[0] if asset.models else ""),
            }

    usage_since = book.processing_started_at or book.created_at
    usage_row = (
        db.query(
            func.count(LLMUsageEvent.id),
            func.coalesce(func.sum(LLMUsageEvent.tokens_in), 0),
            func.coalesce(func.sum(LLMUsageEvent.tokens_out), 0),
        )
        .filter(
            LLMUsageEvent.book_id == book_id,
            LLMUsageEvent.user_id == user.user_id,
            LLMUsageEvent.created_at >= usage_since,
        )
        .first()
    )
    calls = int(usage_row[0] or 0) if usage_row else 0
    tokens_in = int(usage_row[1] or 0) if usage_row else 0
    tokens_out = int(usage_row[2] or 0) if usage_row else 0

    return ChapterListResponse(
        book_id=book_id,
        llm_provider=llm_info["provider"],
        llm_model=llm_info["model"],
        calls=calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        last_error=book.last_error,
        chapters=[
            {"chapter_id": chapter.chapter_id, "title": chapter.title, "status": chapter.status}
            for chapter in chapters
        ],
    )


# 获取指定章节 Markdown
@router.get("/{book_id}/chapters/{chapter_id}/md", response_model=ChapterMarkdownResponse)
def get_chapter_markdown(
    book_id: str,
    chapter_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ChapterMarkdownResponse:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")

    book = db.get(Book, book_id)
    if not book or not _can_access_book(db, book, user) or not book.md_path:
        raise HTTPException(status_code=404, detail="Markdown not ready.")

    # 按字符范围懒加载章节内容
    content = load_chapter_text(book.md_path, chapter.start_char, chapter.end_char)
    return ChapterMarkdownResponse(chapter_id=chapter_id, markdown=content)


# 获取章节知识图谱
@router.get("/{book_id}/chapters/{chapter_id}/graph", response_model=KnowledgeGraph)
def get_chapter_graph(
    book_id: str,
    chapter_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> KnowledgeGraph:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    # 取最新一条图谱记录
    graph_row = (
        db.query(ChapterGraph)
        .filter(ChapterGraph.chapter_id == chapter.id)
        .order_by(ChapterGraph.id.desc())
        .first()
    )

    if not graph_row:
        return KnowledgeGraph(chapter_id=chapter_id, nodes=[], edges=[])

    graph_row.graph_json = _ensure_graph_payload(graph_row.graph_json, chapter_id)
    if _ensure_edge_ids(graph_row.graph_json):
        db.commit()
    return KnowledgeGraph(**graph_row.graph_json)


@router.post(
    "/{book_id}/chapters/{chapter_id}/graph/nodes", response_model=GraphNodeCreate
)
def create_graph_node(
    book_id: str,
    chapter_id: str,
    payload: GraphNodeCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> GraphNodeCreate:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    graph_row = _get_editable_graph(db, chapter)
    graph_json = graph_row.graph_json

    node_id = payload.id or f"n{uuid4().hex}"
    node = {"id": node_id, "name": payload.name, "type": payload.type}
    graph_json["nodes"].append(node)
    db.commit()
    return GraphNodeCreate(**node)


@router.patch(
    "/{book_id}/chapters/{chapter_id}/graph/nodes/{node_id}",
    response_model=GraphNodeCreate,
)
def update_graph_node(
    book_id: str,
    chapter_id: str,
    node_id: str,
    payload: GraphNodeUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> GraphNodeCreate:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    graph_row = _get_editable_graph(db, chapter)
    graph_json = graph_row.graph_json
    node = next((item for item in graph_json["nodes"] if item.get("id") == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")

    prev_name = node.get("name")
    if payload.name is not None:
        node["name"] = payload.name
    if payload.type is not None:
        node["type"] = payload.type

    if payload.name and prev_name and payload.name != prev_name:
        for edge in graph_json.get("edges", []):
            if edge.get("source") == prev_name:
                edge["source"] = payload.name
            if edge.get("target") == prev_name:
                edge["target"] = payload.name

    db.commit()
    return GraphNodeCreate(**node)


@router.delete(
    "/{book_id}/chapters/{chapter_id}/graph/nodes/{node_id}",
    response_model=dict,
)
def delete_graph_node(
    book_id: str,
    chapter_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    graph_row = _get_editable_graph(db, chapter)
    graph_json = graph_row.graph_json

    node = next((item for item in graph_json["nodes"] if item.get("id") == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found.")

    graph_json["nodes"] = [item for item in graph_json["nodes"] if item.get("id") != node_id]
    node_name = node.get("name")
    if node_name:
        graph_json["edges"] = [
            edge
            for edge in graph_json.get("edges", [])
            if edge.get("source") not in {node_name, node_id}
            and edge.get("target") not in {node_name, node_id}
        ]
    db.commit()
    return {"ok": True, "node_id": node_id}


@router.post(
    "/{book_id}/chapters/{chapter_id}/graph/edges", response_model=GraphEdgeCreate
)
def create_graph_edge(
    book_id: str,
    chapter_id: str,
    payload: GraphEdgeCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> GraphEdgeCreate:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    graph_row = _get_editable_graph(db, chapter)
    graph_json = graph_row.graph_json

    edge_id = payload.id or uuid4().hex
    edge = {
        "id": edge_id,
        "source": payload.source,
        "target": payload.target,
        "relation": payload.relation,
        "evidence": payload.evidence or "",
        "confidence": payload.confidence if payload.confidence is not None else 0.5,
        "source_text_location": payload.source_text_location,
    }
    graph_json["edges"].append(edge)
    db.commit()
    return GraphEdgeCreate(**edge)


@router.patch(
    "/{book_id}/chapters/{chapter_id}/graph/edges/{edge_id}",
    response_model=GraphEdgeCreate,
)
def update_graph_edge(
    book_id: str,
    chapter_id: str,
    edge_id: str,
    payload: GraphEdgeUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> GraphEdgeCreate:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    graph_row = _get_editable_graph(db, chapter)
    graph_json = graph_row.graph_json
    edge = next((item for item in graph_json["edges"] if item.get("id") == edge_id), None)
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found.")

    if payload.source is not None:
        edge["source"] = payload.source
    if payload.target is not None:
        edge["target"] = payload.target
    if payload.relation is not None:
        edge["relation"] = payload.relation
    if payload.evidence is not None:
        edge["evidence"] = payload.evidence
    if payload.confidence is not None:
        edge["confidence"] = payload.confidence
    if "source_text_location" in payload.__fields_set__:
        edge["source_text_location"] = payload.source_text_location

    db.commit()
    return GraphEdgeCreate(**edge)


@router.delete(
    "/{book_id}/chapters/{chapter_id}/graph/edges/{edge_id}",
    response_model=dict,
)
def delete_graph_edge(
    book_id: str,
    chapter_id: str,
    edge_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    chapter = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
        .first()
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    graph_row = _get_editable_graph(db, chapter)
    graph_json = graph_row.graph_json

    before = len(graph_json.get("edges", []))
    graph_json["edges"] = [
        edge for edge in graph_json.get("edges", []) if edge.get("id") != edge_id
    ]
    if len(graph_json["edges"]) == before:
        raise HTTPException(status_code=404, detail="Edge not found.")
    db.commit()
    return {"ok": True, "edge_id": edge_id}


# 获取原始 PDF（内联预览）
@router.get("/{book_id}/pdf")
def get_book_pdf(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> FileResponse:
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")
    if not book.pdf_path or not os.path.exists(book.pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found.")
    filename = book.filename or f"{book_id}.pdf"
    ascii_fallback = filename
    try:
        filename.encode("ascii")
    except UnicodeEncodeError:
        ascii_fallback = f"{book_id}.pdf"
    encoded = quote(filename)
    headers = {
        "Content-Disposition": (
            f'inline; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
        )
    }
    return FileResponse(book.pdf_path, media_type="application/pdf", headers=headers)


@router.delete("/{book_id}")
def delete_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    book = db.get(Book, book_id)
    if not book or not _can_access_book(db, book, user):
        raise HTTPException(status_code=404, detail="Book not found.")

    chapter_ids = [
        row.id
        for row in db.query(Chapter.id).filter(Chapter.book_id == book_id).all()
    ]
    if chapter_ids:
        db.query(Chunk).filter(Chunk.chapter_id.in_(chapter_ids)).delete(
            synchronize_session=False
        )
        db.query(ChapterGraph).filter(ChapterGraph.chapter_id.in_(chapter_ids)).delete(
            synchronize_session=False
        )
    db.query(Chapter).filter(Chapter.book_id == book_id).delete(synchronize_session=False)
    db.query(LLMUsageEvent).filter(
        LLMUsageEvent.book_id == book_id, LLMUsageEvent.user_id == user.user_id
    ).delete(synchronize_session=False)
    db.query(PublicBookFavorite).filter(PublicBookFavorite.book_id == book_id).delete(
        synchronize_session=False
    )
    db.query(PublicBookRepost).filter(PublicBookRepost.book_id == book_id).delete(
        synchronize_session=False
    )
    db.query(PublicBook).filter(PublicBook.id == book_id).delete(
        synchronize_session=False
    )
    db.delete(book)
    db.commit()

    book_dir = os.path.join(settings.data_dir, "books", book_id)
    if os.path.isdir(book_dir):
        shutil.rmtree(book_dir, ignore_errors=True)
    for path in [book.pdf_path, book.md_path]:
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

    return {"ok": True, "book_id": book_id}


@router.post("/{book_id}/publish", response_model=PublicBookOut)
def publish_book(
    book_id: str,
    payload: PublishBookRequest | None = None,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> PublicBookOut:
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    payload = payload or PublishBookRequest()
    title = (payload.title or book.filename).strip() or book.filename
    cover_url = (payload.cover_url or "").strip() or None

    now = datetime.utcnow()
    row = db.get(PublicBook, book_id)
    if not row:
        row = PublicBook(
            id=book_id,
            owner_user_id=user.user_id,
            title=title,
            cover_url=cover_url,
            favorites_count=0,
            reposts_count=0,
            published_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if row.owner_user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Not allowed.")
        row.title = title
        row.cover_url = cover_url
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return PublicBookOut(
        id=row.id,
        title=row.title,
        cover_url=row.cover_url,
        owner_user_id=row.owner_user_id,
        favorites_count=row.favorites_count or 0,
        reposts_count=row.reposts_count or 0,
        published_at=row.published_at.isoformat() if row.published_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.post("/publish", response_model=PublicBookOut)
def publish_book_by_body(
    payload: PublishBookByIdRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> PublicBookOut:
    return publish_book(
        book_id=payload.book_id,
        payload=PublishBookRequest(title=payload.title, cover_url=payload.cover_url),
        db=db,
        user=user,
    )


@router.delete("/{book_id}/publish")
def unpublish_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    row = db.get(PublicBook, book_id)
    if not row:
        return {"ok": True, "book_id": book_id, "published": False}
    if row.owner_user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not allowed.")
    db.delete(row)
    db.commit()
    return {"ok": True, "book_id": book_id, "published": False}


@router.get("/{book_id}/usage", response_model=BookUsageResponse)
def get_book_usage(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> BookUsageResponse:
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    rows = (
        db.query(
            LLMUsageEvent.provider,
            LLMUsageEvent.model,
            func.count(LLMUsageEvent.id),
            func.coalesce(func.sum(LLMUsageEvent.tokens_in), 0),
            func.coalesce(func.sum(LLMUsageEvent.tokens_out), 0),
        )
        .filter(LLMUsageEvent.user_id == user.user_id, LLMUsageEvent.book_id == book_id)
        .group_by(LLMUsageEvent.provider, LLMUsageEvent.model)
        .order_by(LLMUsageEvent.provider.asc())
        .all()
    )

    by_model: list[LLMUsageSummary] = []
    total_calls = 0
    total_in = 0
    total_out = 0
    for provider, model, calls, tokens_in, tokens_out in rows:
        calls_i = int(calls or 0)
        in_i = int(tokens_in or 0)
        out_i = int(tokens_out or 0)
        by_model.append(
            LLMUsageSummary(
                provider=str(provider),
                model=str(model) if model else None,
                calls=calls_i,
                tokens_in=in_i,
                tokens_out=out_i,
            )
        )
        total_calls += calls_i
        total_in += in_i
        total_out += out_i

    return BookUsageResponse(
        book_id=book_id,
        calls=total_calls,
        tokens_in=total_in,
        tokens_out=total_out,
        by_model=by_model,
    )