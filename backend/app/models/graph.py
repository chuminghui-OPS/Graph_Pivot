from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChapterGraph(Base):
    __tablename__ = "chapter_graphs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    chapter_id: Mapped[str] = mapped_column(String, index=True)
    graph_json: Mapped[dict] = mapped_column(JSON, nullable=False)
