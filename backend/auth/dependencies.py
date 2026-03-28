"""
认证依赖注入
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from database.postgres import get_db
from database.models import User
from auth.service import AuthService


# HTTP Bearer 安全方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    获取当前用户（可选）
    如果没有提供 Token 或 Token 无效，返回 None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    user_id = AuthService.decode_token(token)
    
    if not user_id:
        return None
    
    try:
        user = await AuthService.get_user_by_id(db, UUID(user_id))
        return user
    except Exception:
        return None


async def get_current_active_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前活跃用户（必须登录）
    如果未认证或用户不存在，抛出 401 错误
    """
    token = credentials.credentials
    user_id = AuthService.decode_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        user = await AuthService.get_user_by_id(db, UUID(user_id))
    except Exception:
        user = None
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    return user


async def get_current_active_user_sse(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前活跃用户（支持 SSE / 下载等无法设置 Header 的场景）。

    优先使用 Authorization header，回退到 query parameter ``?token=xxx``。
    EventSource API 和 <a href> 下载链接均无法发送自定义 headers，
    因此这些端点需要支持 query param 认证。
    """
    raw_token: Optional[str] = None
    if credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = AuthService.decode_token(raw_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await AuthService.get_user_by_id(db, UUID(user_id))
    except Exception:
        user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    return user
