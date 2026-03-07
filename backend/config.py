"""
应用配置模块
使用 Pydantic Settings 集中管理环境变量
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置类"""

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/masppt"
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 认证
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小时

    # 大模型 API
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: str = ""

    # huashu-slides 集成
    SKILL_SCRIPTS_DIR: str = "./huashu-slides/scripts/"
    STYLE_SAMPLES_DIR: str = "./huashu-slides/assets/style-samples/"
    RENDER_PATH_DEFAULT: str = "auto"  # "auto" | "path_a" | "path_b"

    # 应用配置
    APP_ENV: str = "development"
    DEBUG: bool = True
    WORKER_QUEUE_POLL_INTERVAL_SECONDS: float = 1.0
    WORKER_JOB_STALE_SECONDS: int = 120
    WORKER_JOB_HEARTBEAT_SECONDS: int = 15

    # 对象存储
    OBJECT_STORAGE_BACKEND: str = "local"  # "local" | "s3"
    OBJECT_STORAGE_LOCAL_ROOT: str = "object_storage"
    OBJECT_STORAGE_PUBLIC_BASE_URL: str = "http://localhost:8000/api/v1/assets"
    OBJECT_STORAGE_BUCKET: str = "masppt-assets"
    OBJECT_STORAGE_ENDPOINT_URL: str = "http://127.0.0.1:9000"
    OBJECT_STORAGE_ACCESS_KEY: str = "minioadmin"
    OBJECT_STORAGE_SECRET_KEY: str = "minioadmin"
    OBJECT_STORAGE_REGION: str = "us-east-1"
    OBJECT_STORAGE_SECURE: bool = False

    # 资产保留与清理
    ASSET_RETENTION_HOURS: int = 168
    ASSET_CLEANUP_INTERVAL_SECONDS: int = 300
    ASSET_CLEANUP_BATCH_SIZE: int = 100

    class Config:
        env_file = "../.env"  # 从项目根目录读取
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
