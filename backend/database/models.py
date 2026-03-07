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


class WorkflowSession(Base):
    """工作流会话持久化表"""
    __tablename__ = "workflow_sessions"

    session_id = Column(String(36), primary_key=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)

    status = Column(String(50), default="initialized", nullable=False, index=True)
    current_agent = Column(String(50), default="", nullable=False)
    state = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectRevision(Base):
    """项目修订快照表"""
    __tablename__ = "project_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)

    revision_number = Column(Integer, nullable=False)
    revision_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), default="created", nullable=False, index=True)
    theme = Column(String(100), nullable=True)
    outline = Column(JSON, default=list, nullable=False)
    state_snapshot = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class GenerationJob(Base):
    """生成任务表"""
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)

    trigger = Column(String(50), nullable=False, index=True)
    status = Column(String(50), default="created", nullable=False, index=True)
    current_agent = Column(String(50), default="", nullable=False)
    error_message = Column(Text, nullable=True)
    pptx_path = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class JobEvent(Base):
    """任务事件日志表"""
    __tablename__ = "job_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("generation_jobs.id"), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)

    event_type = Column(String(50), nullable=False, index=True)
    agent = Column(String(50), default="", nullable=False)
    status = Column(String(50), default="", nullable=False)
    message = Column(Text, default="", nullable=False)
    payload = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class StoredAsset(Base):
    """对象存储资产元数据表"""
    __tablename__ = "stored_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)

    asset_type = Column(String(50), nullable=False, index=True)
    object_key = Column(String(255), nullable=False, unique=True, index=True)
    public_url = Column(String(1024), nullable=False)
    content_type = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    slide_number = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="active", index=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)


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
