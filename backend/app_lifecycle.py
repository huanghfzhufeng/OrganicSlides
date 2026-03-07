"""Shared FastAPI lifecycle for API and worker services."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.postgres import close_db, init_db
from database.redis_client import redis_client

logger = logging.getLogger(__name__)


async def _connect_optional_redis() -> bool:
    """Connect Redis if available without making startup depend on it."""
    try:
        await redis_client.connect()
        logger.info("Redis connection established")
        return True
    except Exception:
        logger.warning("Redis unavailable; continuing without it", exc_info=True)
        return False


async def _disconnect_optional_redis() -> None:
    """Disconnect Redis if it was available during runtime."""
    try:
        await redis_client.disconnect()
    except Exception:
        logger.warning("Redis disconnect failed during shutdown", exc_info=True)


def build_lifespan(service_name: str):
    """Create a shared lifecycle context for a named service."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        print(f"🚀 {service_name} 启动中...")
        await init_db()
        print("✅ PostgreSQL 数据库初始化完成")

        if await _connect_optional_redis():
            print("✅ Redis 连接成功")
        else:
            print("⚠️ Redis 不可用，系统以 PostgreSQL-only 模式运行")

        yield

        await _disconnect_optional_redis()
        await close_db()
        print(f"👋 {service_name} 已关闭")

    return lifespan
