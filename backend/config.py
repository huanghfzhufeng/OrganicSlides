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

    class Config:
        env_file = "../.env"  # 从项目根目录读取
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
