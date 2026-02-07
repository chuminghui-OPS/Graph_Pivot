from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import PublicBookOut
from app.models import PublicBook, PublicBookFavorite, PublicBookRepost


router = APIRouter()


def _to_out(row: PublicBook) -> PublicBookOut:
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


@router.get("/books", response_model=list[PublicBookOut])
def list_public_books(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[PublicBookOut]:
    rows = (
        db.query(PublicBook)
        .order_by(PublicBook.published_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_to_out(row) for row in rows]


@router.get("/books/{book_id}", response_model=PublicBookOut)
def get_public_book(book_id: str, db: Session = Depends(get_db)) -> PublicBookOut:
    row = db.get(PublicBook, book_id)
    if not row:
        raise HTTPException(status_code=404, detail="Public book not found.")
    return _to_out(row)


@router.post("/books/{book_id}/favorite")
def favorite_public_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    book = db.get(PublicBook, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Public book not found.")

    now = datetime.utcnow()
    row = PublicBookFavorite(
        id=uuid4().hex,
        book_id=book_id,
        user_id=user.user_id,
        created_at=now,
    )
    db.add(row)
    book.favorites_count = (book.favorites_count or 0) + 1
    book.updated_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    db.refresh(book)
    return {"ok": True, "book_id": book_id, "favorites_count": book.favorites_count}


@router.delete("/books/{book_id}/favorite")
def unfavorite_public_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    book = db.get(PublicBook, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Public book not found.")

    row = (
        db.query(PublicBookFavorite)
        .filter(PublicBookFavorite.book_id == book_id, PublicBookFavorite.user_id == user.user_id)
        .first()
    )
    if row:
        db.delete(row)
        book.favorites_count = max(0, (book.favorites_count or 0) - 1)
        book.updated_at = datetime.utcnow()
        db.commit()
    db.refresh(book)
    return {"ok": True, "book_id": book_id, "favorites_count": book.favorites_count}


@router.post("/books/{book_id}/repost")
def repost_public_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    book = db.get(PublicBook, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Public book not found.")

    now = datetime.utcnow()
    row = PublicBookRepost(
        id=uuid4().hex,
        book_id=book_id,
        user_id=user.user_id,
        created_at=now,
    )
    db.add(row)
    book.reposts_count = (book.reposts_count or 0) + 1
    book.updated_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    db.refresh(book)
    return {"ok": True, "book_id": book_id, "reposts_count": book.reposts_count}


@router.delete("/books/{book_id}/repost")
def unrepost_public_book(
    book_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> dict:
    book = db.get(PublicBook, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Public book not found.")

    row = (
        db.query(PublicBookRepost)
        .filter(PublicBookRepost.book_id == book_id, PublicBookRepost.user_id == user.user_id)
        .first()
    )
    if row:
        db.delete(row)
        book.reposts_count = max(0, (book.reposts_count or 0) - 1)
        book.updated_at = datetime.utcnow()
        db.commit()
    db.refresh(book)
    return {"ok": True, "book_id": book_id, "reposts_count": book.reposts_count}

