from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import books, user, assets
from app.core.config import settings
from app.core.database import init_db


# 应用入口：初始化 FastAPI 实例
app = FastAPI(title="Graph Pivot", root_path=settings.root_path or "")

# 配置 CORS，允许前端访问后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册图书相关路由
api_prefix = settings.api_prefix
if api_prefix is None:
    api_prefix = "" if (settings.root_path or "").strip() else "/api"
api_prefix = api_prefix.rstrip("/")
app.include_router(books.router, prefix=f"{api_prefix}/books", tags=["books"])
app.include_router(user.router, prefix=f"{api_prefix}/user", tags=["user"])
app.include_router(assets.router, prefix=f"{api_prefix}/assets", tags=["assets"])


# 启动事件：创建数据库表结构
@app.on_event("startup")
def on_startup() -> None:
    init_db()
