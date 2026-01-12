"""
SQLAlchemy ORM 模型
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.postgres import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    """项目表"""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    user_intent = Column(Text, nullable=False)
    theme = Column(String(50), default="organic")
    outline = Column(JSON, default=list)
    status = Column(String(50), default="created")
    pptx_path = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="projects")
    slides = relationship("Slide", back_populates="project", cascade="all, delete-orphan")


class Slide(Base):
    """幻灯片表"""
    __tablename__ = "slides"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    
    page_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    content = Column(JSON, default=dict)
    layout_id = Column(Integer, default=1)
    layout_name = Column(String(50), default="bullet_list")
    speaker_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    project = relationship("Project", back_populates="slides")
