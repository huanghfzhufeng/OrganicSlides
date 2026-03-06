"""
认证业务逻辑
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User
from auth.schemas import UserRegister, Token


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """认证服务"""

    @staticmethod
    def _build_token(subject: str, scope: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> Token:
        """Create a JWT token for a user or session scope."""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        if scope:
            to_encode["scope"] = scope

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        return Token(
            access_token=encoded_jwt,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> Token:
        """创建 JWT Token"""
        return AuthService._build_token(str(user_id), expires_delta=expires_delta)

    @staticmethod
    def create_project_access_token(session_id: str, expires_delta: Optional[timedelta] = None) -> Token:
        """Create a scoped JWT token for project/session access."""
        return AuthService._build_token(
            session_id,
            scope="project_access",
            expires_delta=expires_delta,
        )
    
    @staticmethod
    def decode_token(token: str) -> Optional[str]:
        """解码 Token，返回 user_id"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload.get("sub")
        except JWTError:
            return None

    @staticmethod
    def decode_project_access_token(token: str) -> Optional[str]:
        """Decode a project access token and return the authorized session_id."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            if payload.get("scope") != "project_access":
                return None
            return payload.get("sub")
        except JWTError:
            return None
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """通过 ID 获取用户"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @classmethod
    async def register(cls, db: AsyncSession, data: UserRegister) -> User:
        """注册新用户"""
        # 检查邮箱是否已存在
        existing = await cls.get_user_by_email(db, data.email)
        if existing:
            raise ValueError("邮箱已被注册")
        
        # 创建用户
        user = User(
            email=data.email,
            username=data.username,
            hashed_password=cls.hash_password(data.password)
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    
    @classmethod
    async def authenticate(cls, db: AsyncSession, email: str, password: str) -> Optional[User]:
        """验证用户凭据"""
        user = await cls.get_user_by_email(db, email)
        
        if not user:
            return None
        
        if not cls.verify_password(password, user.hashed_password):
            return None
        
        return user
