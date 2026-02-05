from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# ORM 基类：所有模型继承它
class Base(DeclarativeBase):
    pass


# 创建数据库引擎（SQLite）
def _build_engine():
    if settings.database_url:
        return create_engine(settings.database_url, future=True, pool_pre_ping=True)
    settings.ensure_dirs()
    return create_engine(
        f"sqlite:///{settings.sqlite_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )


# 全局数据库引擎
engine = _build_engine()
# 会话工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# 初始化数据库表
def init_db() -> None:
    from app.models import book, chapter, chunk, graph, api_asset, profile  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(chapters)"))}
        if "processing_started_at" not in columns:
            conn.execute(
                text("ALTER TABLE chapters ADD COLUMN processing_started_at DATETIME")
            )
        book_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(books)"))}
        if "last_seen_at" not in book_columns:
            conn.execute(text("ALTER TABLE books ADD COLUMN last_seen_at DATETIME"))
        if "user_id" not in book_columns:
            conn.execute(text("ALTER TABLE books ADD COLUMN user_id VARCHAR"))


# FastAPI 依赖：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
