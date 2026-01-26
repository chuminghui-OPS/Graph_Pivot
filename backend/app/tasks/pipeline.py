from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import uuid4

from celery import group, chord

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Book, Chapter, Chunk, ChapterGraph
from app.services.chunk_service import count_text_units, split_evenly
from app.services.graph_builder import build_chapter_graph
from app.services.llm_service import extract_with_validation
from app.services.md_service import load_chapter_text, parse_structure
from app.services.pdf_service import pdf_to_markdown
from app.utils.file_store import ensure_book_dir, new_chapter_id, new_chunk_id


# 创建数据库会话
def _db_session():
    return SessionLocal()


def _normalize_provider(provider: str | None) -> str:
    name = (provider or settings.llm_provider or "qwen").lower()
    return "gemini" if name == "gemini" else "qwen"


def _is_book_inactive(book: Book) -> bool:
    if not book.last_seen_at:
        return False
    return datetime.utcnow() - book.last_seen_at > timedelta(seconds=settings.book_inactive_seconds)


def _pause_book(db, book_id: str) -> None:
    book = db.get(Book, book_id)
    if not book:
        return
    book.status = "paused"
    db.query(Chapter).filter(
        Chapter.book_id == book_id, Chapter.status.in_(["PENDING", "PROCESSING"])
    ).update({"status": "PAUSED", "processing_started_at": None})
    db.commit()


def _update_book_status(db, book_id: str) -> None:
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


# Celery 任务：处理整本书（PDF->MD->章节入库）
@celery_app.task
def process_book(book_id: str, llm_provider: str | None = None) -> Dict[str, Any]:
    db = _db_session()
    try:
        book = db.get(Book, book_id)
        if not book:
            return {"error": "BOOK_NOT_FOUND"}

        # 标记书籍处理中
        book.status = "processing"
        db.commit()

        # PDF 转 Markdown
        book_dir = ensure_book_dir(book_id)
        md_path = pdf_to_markdown(book.pdf_path, book_dir)
        book.md_path = md_path
        db.commit()

        # 解析章节结构（优先使用 PDF 书签/目录）
        try:
            structure = parse_structure(md_path, book.pdf_path)
        except ValueError as exc:
            book.status = f"failed:{exc}"
            db.commit()
            return {"error": "INVALID_PDF", "message": str(exc)}

        # 使用解析后的分页 Markdown 作为章节读取来源
        book.md_path = structure.get("file_path", md_path)
        db.commit()

        # 全书字数预检查（中文按字符，英文按单词）
        with open(book.md_path, "r", encoding="utf-8", errors="ignore") as handle:
            total_units = count_text_units(handle.read())
        if total_units > 2_000_000:
            book.status = "failed:BOOK_TOO_LARGE"
            db.commit()
            return {"error": "BOOK_TOO_LARGE"}

        chapters = structure.get("chapters", [])
        if not chapters:
            book.status = "failed:未检测到目录或章节信息"
            db.commit()
            return {"error": "NO_CHAPTERS"}

        # 清理旧数据，避免重复
        db.query(Chapter).filter(Chapter.book_id == book_id).delete()
        db.query(Chunk).filter(Chunk.chapter_id.like(f"{book_id}:%")).delete()
        db.query(ChapterGraph).filter(ChapterGraph.chapter_id.like(f"{book_id}:%")).delete()
        db.commit()

        # 写入章节记录
        for idx, item in enumerate(chapters, start=1):
            chapter_code = new_chapter_id(idx)
            chapter_pk = f"{book_id}:{chapter_code}"
            title = (item.get("title") or "").strip()
            if not title or title.lower() == "full content":
                title = f"章节 {idx}"
            chapter = Chapter(
                id=chapter_pk,
                book_id=book_id,
                chapter_id=chapter_code,
                title=title,
                status="PENDING",
                processing_started_at=None,
                start_char=int(item.get("start_char", 0)),
                end_char=int(item.get("end_char", 0)),
                order_index=idx,
            )
            db.add(chapter)
        db.commit()

        # 若用户已离开页面，暂停任务派发
        if _is_book_inactive(book):
            _pause_book(db, book_id)
            return {"book_id": book_id, "chapters": len(chapters), "status": "PAUSED"}

        # 派发章节处理任务
        for chapter in db.query(Chapter).filter(Chapter.book_id == book_id).all():
            process_chapter.delay(book_id, chapter.chapter_id, llm_provider)

        return {"book_id": book_id, "chapters": len(chapters)}
    finally:
        db.close()


# Celery 任务：处理单个章节（切块 -> LLM -> 聚合）
@celery_app.task
def process_chapter(book_id: str, chapter_id: str, llm_provider: str | None = None) -> Dict[str, Any]:
    db = _db_session()
    try:
        chapter = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
            .first()
        )
        if not chapter:
            return {"error": "CHAPTER_NOT_FOUND"}

        book = db.get(Book, book_id)
        if not book or not book.md_path:
            chapter.status = "FAILED"
            db.commit()
            _update_book_status(db, book_id)
            return {"error": "BOOK_MD_NOT_READY"}
        if _is_book_inactive(book):
            _pause_book(db, book_id)
            return {"chapter_id": chapter_id, "status": "PAUSED"}

        # 标记章节处理中
        chapter.status = "PROCESSING"
        chapter.processing_started_at = datetime.utcnow()
        db.commit()

        provider = _normalize_provider(llm_provider)

        # 读取章节文本并切块
        text = load_chapter_text(book.md_path, chapter.start_char, chapter.end_char)
        if not text.strip():
            chunks = []
        else:
            unit_count = count_text_units(text)
            if provider == "gemini":
                if unit_count > 200_000:
                    chapter.status = "SKIPPED_TOO_LARGE"
                    db.query(Chunk).filter(Chunk.chapter_id == chapter.id).delete()
                    db.query(ChapterGraph).filter(ChapterGraph.chapter_id == chapter.id).delete()
                    db.commit()
                    _update_book_status(db, book_id)
                    return {"chapter_id": chapter_id, "chunks": 0, "status": "SKIPPED_TOO_LARGE"}
                chunks = [{"start": 0, "end": len(text), "text": text}]
            else:
                if unit_count <= 30_000:
                    chunks = [{"start": 0, "end": len(text), "text": text}]
                else:
                    chunk_count = (unit_count // 30_000) + 1
                    chunks = split_evenly(text, chunk_count)

        # 清理旧 chunk 与旧图谱
        db.query(Chunk).filter(Chunk.chapter_id == chapter.id).delete()
        db.query(ChapterGraph).filter(ChapterGraph.chapter_id == chapter.id).delete()
        db.commit()

        # 写入 chunk 记录
        chunk_ids: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            chunk_id = new_chunk_id(chapter.chapter_id, idx)
            chunk_row = Chunk(
                id=chunk_id,
                chapter_id=chapter.id,
                chunk_index=idx,
                start_char=int(chunk["start"]),
                end_char=int(chunk["end"]),
                status="pending",
                text=str(chunk["text"]),
                result_json=None,
            )
            db.add(chunk_row)
            chunk_ids.append(chunk_id)
        db.commit()

        if not chunk_ids:
            # 无内容则直接生成空图谱
            assemble_chapter_graph.delay([], book_id, chapter_id)
            return {"chapter_id": chapter_id, "chunks": 0}

        # 并发抽取所有 chunk，结束后回调聚合任务
        tasks = group(extract_chunk.s(chunk_id, llm_provider) for chunk_id in chunk_ids)
        callback = assemble_chapter_graph.s(book_id, chapter_id)
        chord(tasks)(callback)
        return {"chapter_id": chapter_id, "chunks": len(chunk_ids)}
    finally:
        db.close()


# Celery 任务：抽取单个 chunk 的实体关系
@celery_app.task
def extract_chunk(chunk_id: str, llm_provider: str | None = None) -> Dict[str, Any]:
    db = _db_session()
    try:
        chunk = db.get(Chunk, chunk_id)
        if not chunk:
            return {"ok": False, "chunk_id": chunk_id, "error": "CHUNK_NOT_FOUND"}

        # 标记处理中
        chunk.status = "processing"
        db.commit()

        # LLM 抽取并校验
        result = extract_with_validation(chunk.text, max_retries=2, provider_override=llm_provider)
        if result.get("error"):
            # 标记失败并记录错误
            chunk.status = "failed"
            chunk.error = result.get("details") or result.get("error")
            chunk.result_json = result
            db.commit()
            return {"ok": False, "chunk_id": chunk_id, "error": chunk.error, "result": result}

        # 成功写入结果
        chunk.status = "done"
        chunk.result_json = result
        db.commit()
        return {"ok": True, "chunk_id": chunk_id, "result": result}
    finally:
        db.close()


# Celery 任务：聚合章节图谱并更新章节状态
@celery_app.task
def assemble_chapter_graph(chunk_results: List[Dict[str, Any]], book_id: str, chapter_id: str) -> Dict[str, Any]:
    db = _db_session()
    try:
        chapter = (
            db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
            .first()
        )
        if not chapter:
            return {"error": "CHAPTER_NOT_FOUND"}

        if chapter.status in ["TIMEOUT", "SKIPPED_TOO_LARGE"]:
            db.commit()
            _update_book_status(db, book_id)
            return {"chapter_id": chapter_id, "status": chapter.status}

        # 聚合成功结果
        ok_results = [item.get("result", {}) for item in chunk_results if item.get("ok")]
        has_failures = any(not item.get("ok") for item in chunk_results)

        # 构建章节级图谱
        graph = build_chapter_graph(chapter_id, ok_results)
        graph_row = ChapterGraph(
            id=f"{chapter.id}:{uuid4().hex}",
            chapter_id=chapter.id,
            graph_json=graph,
        )
        db.add(graph_row)

        # 更新章节状态
        chapter.status = "FAILED" if has_failures else "DONE"
        db.commit()

        _update_book_status(db, book_id)

        return graph
    finally:
        db.close()
