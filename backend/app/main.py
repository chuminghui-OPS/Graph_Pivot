from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import books
from app.core.config import settings
from app.core.database import init_db


# 应用入口：初始化 FastAPI 实例
app = FastAPI(title="Graph Pivot")

# 配置 CORS，允许前端访问后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册图书相关路由
app.include_router(books.router, prefix="/api/books", tags=["books"])


# 启动事件：创建数据库表结构
@app.on_event("startup")
def on_startup() -> None:
    init_db()
