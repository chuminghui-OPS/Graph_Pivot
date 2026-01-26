from app.core.config import settings
from app.core.celery_app import celery_app

# 对外导出核心对象
__all__ = ["settings", "celery_app"]
