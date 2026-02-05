from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.core.database import get_db
from app.core.schemas import (
    ChapterListResponse,
    ChapterMarkdownResponse,
    KnowledgeGraph,
    ProcessResponse,
    UploadResponse,
)
from app.core.celery_app import celery_app
from app.core.auth import UserContext, get_current_user
from app.models import Book, Chapter, ChapterGraph
from app.services.llm_service import get_llm_info
from app.services.md_service import load_chapter_text
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


# 上传 PDF 并创建书籍记录
@router.post("/upload", response_model=UploadResponse)
async def upload_book(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # 生成 book_id 并写入磁盘
    book_id = new_book_id()
    book_dir = ensure_book_dir(book_id)
    pdf_path = os.path.join(book_dir, "source.pdf")

    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 写入数据库
    book = Book(
        id=book_id,
        user_id=user.user_id,
        filename=file.filename,
        pdf_path=pdf_path,
        status="uploaded",
        last_seen_at=datetime.utcnow(),
    )
    db.add(book)
    db.commit()

    return UploadResponse(book_id=book_id, filename=file.filename)


# 触发全书处理流水线
@router.post("/{book_id}/process", response_model=ProcessResponse)
def process_book(
    book_id: str,
    llm: str = Query("qwen", description="llm provider: gemini or qwen"),
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ProcessResponse:
    book = db.get(Book, book_id)
    if not book or book.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Book not found.")

    provider = llm.lower()
    if provider not in {"gemini", "qwen"}:
        raise HTTPException(status_code=400, detail="Invalid llm provider.")

    BOOK_LLM_PROVIDER[book_id] = provider
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
    if not book or book.user_id != user.user_id:
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
        if (
            chapter.status == "PROCESSING"
            and chapter.processing_started_at
            and now - chapter.processing_started_at > timedelta(seconds=280)
        ):
            chapter.status = "TIMEOUT"
            updated = True
    if updated:
        db.commit()
        _refresh_book_status(db, book_id)
    llm_info = get_llm_info(BOOK_LLM_PROVIDER.get(book_id))

    return ChapterListResponse(
        book_id=book_id,
        llm_provider=llm_info["provider"],
        llm_model=llm_info["model"],
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
    if not book or book.user_id != user.user_id or not book.md_path:
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

    return KnowledgeGraph(**graph_row.graph_json)


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
    headers = {"Content-Disposition": f'inline; filename="{book.filename}"'}
    return FileResponse(book.pdf_path, media_type="application/pdf", headers=headers)
