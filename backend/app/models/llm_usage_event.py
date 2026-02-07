from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMUsageEvent(Base):
    __tablename__ = "llm_usage_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    book_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String, index=True, nullable=False)
    model: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
