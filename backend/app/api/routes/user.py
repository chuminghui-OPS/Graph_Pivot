from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import UserBook, UserProfile, UserUsageBookRow
from app.models import Book, Profile, LLMUsageEvent


router = APIRouter()


@router.get("/me", response_model=UserProfile)
def get_me(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> UserProfile:
    profile = db.get(Profile, user.user_id)
    if not profile:
        profile = Profile(id=user.user_id, email=user.email)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    total_books = db.query(Book).filter(Book.user_id == user.user_id).count()

    return UserProfile(
        user_id=user.user_id,
        email=profile.email or user.email,
        full_name=profile.full_name,
        avatar_url=profile.avatar_url,
        plan="Free",
        total_books=total_books,
    )


@router.get("/books", response_model=list[UserBook])
def list_user_books(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> list[UserBook]:
    rows = (
        db.query(Book)
        .filter(Book.user_id == user.user_id)
        .order_by(Book.created_at.desc())
        .all()
    )
    return [
        UserBook(
            book_id=book.id,
            title=book.filename,
            created_at=book.created_at.isoformat() if book.created_at else None,
        )
        for book in rows
    ]


@router.get("/usage", response_model=list[UserUsageBookRow])
def get_user_usage(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> list[UserUsageBookRow]:
    rows = (
        db.query(
            LLMUsageEvent.book_id,
            func.count(LLMUsageEvent.id),
            func.coalesce(func.sum(LLMUsageEvent.tokens_in), 0),
            func.coalesce(func.sum(LLMUsageEvent.tokens_out), 0),
        )
        .filter(LLMUsageEvent.user_id == user.user_id)
        .group_by(LLMUsageEvent.book_id)
        .all()
    )
    return [
        UserUsageBookRow(
            book_id=str(book_id),
            calls=int(calls or 0),
            tokens_in=int(tokens_in or 0),
            tokens_out=int(tokens_out or 0),
        )
        for book_id, calls, tokens_in, tokens_out in rows
    ]
