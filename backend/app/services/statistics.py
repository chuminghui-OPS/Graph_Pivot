from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Statistics


def _get_or_create(
    db: Session,
    metric: str,
    book_type: str | None = None,
    provider: str | None = None,
) -> Statistics:
    row = (
        db.query(Statistics)
        .filter(
            Statistics.metric == metric,
            Statistics.book_type == book_type,
            Statistics.provider == provider,
        )
        .first()
    )
    if row:
        return row
    row = Statistics(
        id=uuid4().hex,
        metric=metric,
        book_type=book_type,
        provider=provider,
        count=0,
        tokens_in=0,
        tokens_out=0,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def record_book_upload(db: Session, book_type: str, book_id: str) -> None:
    row = _get_or_create(db, metric="book_upload", book_type=book_type)
    row.count += 1
    row.last_book_id = book_id
    row.updated_at = datetime.utcnow()
    db.commit()


def record_llm_usage(
    db: Session,
    provider: str | None,
    tokens_in: int,
    tokens_out: int,
    commit: bool = True,
) -> None:
    row = _get_or_create(db, metric="llm_call", provider=provider)
    row.count += 1
    row.tokens_in += max(0, tokens_in)
    row.tokens_out += max(0, tokens_out)
    row.updated_at = datetime.utcnow()
    if commit:
        db.commit()
