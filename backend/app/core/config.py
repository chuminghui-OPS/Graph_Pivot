from __future__ import annotations

import os
from pydantic_settings import BaseSettings


# 应用配置：统一管理环境变量与默认值
class Settings(BaseSettings):
    app_env: str = "dev"
    data_dir: str = "data"
    upload_dir: str = "data/uploads"
    md_dir: str = "data/markdown"
    sqlite_path: str = "data/app.db"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_max_tokens: int = 30000
    llm_provider: str = "qwen"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3-flash-preview"

    chunk_size: int = 1500
    chunk_overlap: int = 200

    cors_origins: str = "http://localhost:3000"
    book_inactive_seconds: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False

    # 解析 CORS 允许域名列表
    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    # 确保运行时数据目录存在
    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.upload_dir, self.md_dir, os.path.dirname(self.sqlite_path)):
            if path:
                os.makedirs(path, exist_ok=True)


# 全局配置实例
settings = Settings()
