"""
应用配置模块
使用 Pydantic Settings 集中管理环境变量
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """应用配置类"""

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@127.0.0.1:15432/masppt"
    REDIS_URL: str = "redis://127.0.0.1:16379/0"
    POSTGRES_PORT: int = 15432
    REDIS_PORT: int = 16379

    # CORS
    CORS_ORIGINS: str = (
        "http://localhost:15173,"
        "http://127.0.0.1:15173,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )
    FRONTEND_PORT: int = 15173
    BACKEND_PORT: int = 18000

    # JWT 认证
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小时

    # LLM (MiniMax via OpenAI-compatible API)
    MINIMAX_API_KEY: str = ""
    LLM_MODEL: str = "MiniMax-M2.5"
    LLM_BASE_URL: str = "https://api.minimax.io/v1"

    # 图片生成 (12ai Gemini 代理)
    IMAGEN_API_KEY: str = ""
    IMAGEN_MODEL: str = "gemini-3.1-flash-image-preview"
    IMAGEN_BASE_URL: str = "https://new.12ai.org"
    IMAGEN_IMAGE_SIZE: str = "1K"
    IMAGEN_NUMBER_OF_IMAGES: int = 1

    # 新闻搜索
    NEWS_API_KEY: str = ""

    # 兼容旧配置（保留但不再使用）
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
        env_file = str(ROOT_ENV_FILE)  # 始终从项目根目录读取
        env_file_encoding = "utf-8"
        case_sensitive = True


    def validate_settings(self) -> None:
        """Warn or raise if critical settings are missing or insecure."""
        import logging
        _logger = logging.getLogger(__name__)

        if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "your-super-secret-key-change-in-production":
            if self.APP_ENV == "production":
                raise RuntimeError(
                    "JWT_SECRET_KEY must be set to a strong secret value. "
                    "Set the JWT_SECRET_KEY environment variable before starting the server."
                )
            _logger.warning(
                "⚠️  JWT_SECRET_KEY is empty or insecure. "
                "This is acceptable for development, but MUST be set in production."
            )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
