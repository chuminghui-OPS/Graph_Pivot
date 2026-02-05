from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import UserContext, get_current_user
from app.core.database import get_db
from app.core.schemas import UserBook, UserProfile
from app.models import Book, Profile


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
