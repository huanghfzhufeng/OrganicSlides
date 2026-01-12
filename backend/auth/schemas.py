"""
认证相关的 Pydantic 模型
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ==================== 请求模型 ====================

class UserRegister(BaseModel):
    """用户注册请求"""
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    """用户登录请求"""
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str


# ==================== 响应模型 ====================

class Token(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """用户信息响应"""
    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """认证响应（包含用户和 Token）"""
    user: UserResponse
    token: Token
