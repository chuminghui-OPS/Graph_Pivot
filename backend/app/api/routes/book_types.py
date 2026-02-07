from __future__ import annotations

from fastapi import APIRouter

from app.core.book_types import list_book_types


router = APIRouter()


@router.get("")
def get_book_types() -> list[dict[str, str]]:
    return list(list_book_types())
