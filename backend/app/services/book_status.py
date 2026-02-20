from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Book, Chapter


def update_book_status(db: Session, book_id: str) -> None:
    """检查所有章节是否处理完毕，并更新书籍状态为 done 或 failed。"""
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
