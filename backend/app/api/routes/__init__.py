from app.api.routes.books import router as books_router
from app.api.routes.user import router as user_router
from app.api.routes.assets import router as assets_router

# 对外导出路由
__all__ = ["books_router", "user_router", "assets_router"]
