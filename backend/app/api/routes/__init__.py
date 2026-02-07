from app.api.routes.books import router as books_router
from app.api.routes.user import router as user_router
from app.api.routes.assets import router as assets_router
from app.api.routes.managers import router as managers_router
from app.api.routes.book_types import router as book_types_router

# 对外导出路由
__all__ = ["books_router", "user_router", "assets_router", "managers_router", "book_types_router"]
