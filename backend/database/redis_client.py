"""
Redis 客户端
用于会话缓存和实时状态存储
"""

import json
from typing import Any, Optional
import redis.asyncio as redis

from config import settings


class RedisClient:
    """Redis 客户端封装"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """连接 Redis"""
        self._client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        """断开连接"""
        if self._client:
            await self._client.close()
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not connected")
        return self._client
    
    # ==================== 会话状态操作 ====================
    
    async def set_session(self, session_id: str, data: dict, ttl: int = 86400):
        """设置会话状态（默认 24 小时过期）"""
        await self.client.setex(
            f"session:{session_id}",
            ttl,
            json.dumps(data, ensure_ascii=False)
        )
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话状态"""
        data = await self.client.get(f"session:{session_id}")
        return json.loads(data) if data else None
    
    async def update_session(self, session_id: str, updates: dict):
        """更新会话状态（合并更新）"""
        current = await self.get_session(session_id) or {}
        current.update(updates)
        await self.set_session(session_id, current)
    
    async def delete_session(self, session_id: str):
        """删除会话"""
        await self.client.delete(f"session:{session_id}")
    
    # ==================== 日志流操作 ====================
    
    async def push_log(self, session_id: str, log: dict, ttl: int = 3600):
        """推送 Agent 日志"""
        key = f"logs:{session_id}"
        await self.client.rpush(key, json.dumps(log, ensure_ascii=False))
        await self.client.expire(key, ttl)
    
    async def get_logs(self, session_id: str) -> list:
        """获取所有日志"""
        logs = await self.client.lrange(f"logs:{session_id}", 0, -1)
        return [json.loads(log) for log in logs]
    
    # ==================== 大纲缓存 ====================
    
    async def set_outline(self, session_id: str, outline: list, ttl: int = 86400):
        """缓存大纲"""
        await self.client.setex(
            f"outline:{session_id}",
            ttl,
            json.dumps(outline, ensure_ascii=False)
        )
    
    async def get_outline(self, session_id: str) -> Optional[list]:
        """获取缓存的大纲"""
        data = await self.client.get(f"outline:{session_id}")
        return json.loads(data) if data else None


# 全局客户端实例
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """获取 Redis 客户端（依赖注入）"""
    return redis_client
