from __future__ import annotations

import os
from pydantic_settings import BaseSettings


# 应用配置：统一管理环境变量与默认值
class Settings(BaseSettings):
    # 运行环境标识（便于日志、调试、区分开发/生产）
    app_env: str = "dev"
    # FastAPI 根路径（反向代理或子路径部署时使用）
    root_path: str = ""
    # API 前缀（兼容多版本路由或网关转发）
    api_prefix: str | None = None
    # 项目运行时数据根目录（上传文件/中间结果/数据库等）
    data_dir: str = "data"
    # PDF 上传文件存放目录
    upload_dir: str = "data/uploads"
    # PDF 转 Markdown 输出目录
    md_dir: str = "data/markdown"
    # SQLite 数据库文件路径（默认本地文件）
    sqlite_path: str = "data/app.db"
    # 可选数据库连接串（优先用于 PostgreSQL 等外部数据库）
    database_url: str | None = None

    # Celery Broker（任务队列）连接地址
    celery_broker_url: str = "redis://localhost:6379/0"
    # Celery 结果存储地址（用于回调或结果查询）
    celery_result_backend: str = "redis://localhost:6379/1"

    # 通用 LLM API Key（OpenAI 兼容协议）
    llm_api_key: str | None = None
    # 通用 LLM 兼容接口地址（可替换为代理/自部署服务）
    llm_base_url: str = "https://api.openai.com/v1"
    # 通用 LLM 模型名
    llm_model: str = "gpt-4o-mini"
    # LLM 请求超时时间（秒）
    llm_timeout_seconds: int = 60
    # 章节级最大 Token（用于切块策略阈值）
    llm_max_tokens: int = 30000
    # 章节处理超时阈值（秒），超过会标记 TIMEOUT
    chapter_processing_timeout_seconds: int = 900
    # 当前默认 LLM 提供方（qwen 或 gemini）
    llm_provider: str = "qwen"
    # Gemini API Key（使用 Google Gemini 时必填）
    gemini_api_key: str | None = None
    # Gemini 模型名
    gemini_model: str = "gemini-3-flash-preview"
    # API Key 加密密钥（Fernet, 32-byte urlsafe base64）
    api_key_encryption_key: str | None = None
    # 管理后台访问密钥（用于 /admin/dashboard）
    admin_api_key: str | None = None

    # 兜底切块长度（当使用固定切块策略时）
    chunk_size: int = 1500
    # 切块重叠长度（避免上下文断裂）
    chunk_overlap: int = 200

    # 允许跨域访问的前端地址列表（逗号分隔）
    cors_origins: str = "http://localhost:3000"
    # 前端心跳超时时间（秒），超时则暂停该书处理
    book_inactive_seconds: int = 60

    # Supabase 项目地址（前后端均需要）
    supabase_url: str = ""
    # Supabase 前端匿名访问 Key（仅前端使用）
    supabase_anon_key: str | None = None
    # Supabase Service Role Key（仅后端使用，拥有最高权限）
    supabase_service_role_key: str | None = None
    # Supabase JWKS 地址（用于后端 JWT 验证，留空则由 supabase_url 推导）
    supabase_jwks_url: str | None = None
    # Supabase JWT Secret（对称签名时使用，可与 JWKS 二选一）
    supabase_jwt_secret: str | None = None
    # JWT 验证时的 audience（Supabase 默认是 authenticated）
    supabase_jwt_audience: str = "authenticated"
    # JWT 验证时的 issuer（留空则由 supabase_url 推导）
    supabase_jwt_issuer: str | None = None

    # Pydantic Settings 行为配置
    class Config:
        env_file = (
            os.getenv("APP_ENV_FILE") or "config/.env",
            "backend/config/.env",
            ".env",
        )
        case_sensitive = False
        extra = "ignore" if os.getenv("APP_ENV", "dev").lower() == "dev" else "forbid"

    # 解析 CORS 允许域名列表（供中间件直接使用）
    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    # Supabase JWKS 地址（优先使用配置值）
    @property
    def resolved_supabase_jwks_url(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    # Supabase JWT issuer（优先使用配置值）
    @property
    def resolved_supabase_jwt_issuer(self) -> str | None:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    # 确保运行时数据目录存在（启动时创建必要目录）
    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.upload_dir,
            self.md_dir,
            os.path.dirname(self.sqlite_path),
        ):
            if path:
                os.makedirs(path, exist_ok=True)


# 全局配置实例
settings = Settings()
