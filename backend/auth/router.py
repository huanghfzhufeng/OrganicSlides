"""
认证 API 路由
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.postgres import get_db
from database.models import User
from auth.schemas import UserRegister, UserLogin, AuthResponse, UserResponse, Token
from auth.service import AuthService
from auth.dependencies import get_current_active_user
from rate_limit import limiter


router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    用户注册
    """
    try:
        user = await AuthService.register(db, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    token = AuthService.create_access_token(user.id)
    
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=token
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    用户登录
    """
    user = await AuthService.authenticate(db, data.email, data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    token = AuthService.create_access_token(user.id)
    
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=token
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    获取当前用户信息
    """
    return UserResponse.model_validate(current_user)


@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: User = Depends(get_current_active_user)):
    """
    刷新 Token
    """
    return AuthService.create_access_token(current_user.id)
