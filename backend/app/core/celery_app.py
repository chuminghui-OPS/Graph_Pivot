from __future__ import annotations

from celery import Celery

from app.core.config import settings


# 创建 Celery 应用
celery_app = Celery(
    "graph_pivot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery 序列化与时区配置
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# 自动发现任务模块
celery_app.autodiscover_tasks(["app.tasks"])
