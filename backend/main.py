"""
MAS-PPT 多智能体演示文稿生成系统
FastAPI 后端服务 - 集成数据库和认证
"""

import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app_lifecycle import build_lifespan
from state import create_initial_state
from database.postgres import get_db
from database.models import User, Project
from database.project_tracking_store import (
    count_project_revisions,
    create_project_revision,
    find_session_active_generation_job,
    get_generation_failure_for_job,
    get_generation_job,
    get_generation_failure,
    list_failed_generation_jobs,
    list_job_events,
    list_project_revisions,
    list_session_generation_jobs,
    restore_project_revision as restore_project_revision_snapshot,
    sync_project_state,
)
from database.workflow_state_store import (
    load_workflow_state,
    save_workflow_state,
    update_workflow_state,
)
from auth import (
    auth_router,
    get_current_active_user,
    get_current_operator_user,
    get_current_user,
)
from auth.service import AuthService
from event_stream import stream_job_events
from job_queue import enqueue_generation_job
from project_preview import build_project_preview
from runtime_schemas import build_style_packet, serialize_models
from services.object_storage import get_object_storage
from styles.registry import get_registry
from styles.recommender import StyleRecommender

async def _load_session_state(session_id: str) -> Optional[dict]:
    """Load workflow state from durable PostgreSQL storage only."""
    return await load_workflow_state(session_id)


async def _save_session_state(
    session_id: str,
    state: dict,
    project_id: Optional[str] = None,
) -> dict:
    """Persist workflow state durably and synchronize the Project snapshot."""
    persisted = await save_workflow_state(session_id, state, project_id=project_id)
    await sync_project_state(session_id, persisted)
    return persisted


async def _merge_session_state(session_id: str, updates: dict) -> Optional[dict]:
    """Merge workflow state updates into durable storage."""
    persisted = await update_workflow_state(session_id, updates)
    if persisted is None:
        return None

    await sync_project_state(session_id, persisted)
    return persisted


app = FastAPI(
    title="MAS-PPT API",
    description="多智能体协同演示文稿生成系统",
    version="1.0.0",
    lifespan=build_lifespan("MAS-PPT API"),
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务 (style sample images)
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Output files service (thumbnails, generated PPTX previews)
_output_dir = Path(__file__).parent / "output"
_output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(_output_dir)), name="output")

# 注册认证路由
app.include_router(auth_router)


# ==================== 请求/响应模型 ====================

class ProjectCreate(BaseModel):
    prompt: str
    style_id: Optional[str] = None                # new style system (preferred)
    style: str = "organic"                         # legacy fallback
    render_path_preference: str = "auto"           # "auto" | "path_a" | "path_b"

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("prompt must not be empty")
        return v.strip()

    @field_validator("render_path_preference")
    @classmethod
    def valid_render_path(cls, v: str) -> str:
        if v not in ("auto", "path_a", "path_b"):
            return "auto"
        return v


class OutlineUpdate(BaseModel):
    session_id: str
    outline: List[Dict[str, Any]]
    access_token: Optional[str] = None


class WorkflowResume(BaseModel):
    session_id: str


class StyleUpdate(BaseModel):
    session_id: str
    style_id: str
    render_path_preference: str = "auto"  # "auto" | "path_a" | "path_b"
    access_token: Optional[str] = None


class RevisionRestoreRequest(BaseModel):
    session_id: str
    revision_number: Optional[int] = None
    revision_id: Optional[str] = None
    access_token: Optional[str] = None

    @field_validator("revision_number")
    @classmethod
    def revision_number_must_be_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 1:
            raise ValueError("revision_number must be greater than 0")
        return value

    @model_validator(mode="after")
    def require_exactly_one_revision_selector(self) -> "RevisionRestoreRequest":
        has_revision_number = self.revision_number is not None
        has_revision_id = bool(self.revision_id)
        if has_revision_number == has_revision_id:
            raise ValueError("Provide exactly one of revision_number or revision_id")
        return self


class RetryRequest(BaseModel):
    session_id: str
    trigger: Optional[str] = None
    access_token: Optional[str] = None

    @field_validator("trigger")
    @classmethod
    def valid_trigger(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value not in {"start_workflow", "resume_workflow"}:
            raise ValueError("trigger must be start_workflow or resume_workflow")
        return value


class OperatorRevisionRestoreRequest(BaseModel):
    revision_number: Optional[int] = None
    revision_id: Optional[str] = None

    @field_validator("revision_number")
    @classmethod
    def operator_revision_number_must_be_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 1:
            raise ValueError("revision_number must be greater than 0")
        return value

    @model_validator(mode="after")
    def require_exactly_one_revision_selector(self) -> "OperatorRevisionRestoreRequest":
        has_revision_number = self.revision_number is not None
        has_revision_id = bool(self.revision_id)
        if has_revision_number == has_revision_id:
            raise ValueError("Provide exactly one of revision_number or revision_id")
        return self


async def _authorize_project_access(
    session_id: str,
    access_token: Optional[str],
    current_user: Optional[User],
    db: AsyncSession,
) -> None:
    """Allow project access to the owning user or a valid session access token."""
    if access_token:
        authorized_session_id = AuthService.decode_project_access_token(access_token)
        if authorized_session_id == session_id:
            return

    if current_user is None:
        raise HTTPException(status_code=401, detail="Project access token required")

    try:
        project_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(
            Project.id == project_uuid,
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is not None:
        return

    raise HTTPException(status_code=403, detail="Forbidden")


# ==================== SSE 流式响应 ====================

async def generate_sse_events(job_id: str):
    """Proxy persisted queued worker job events as SSE."""
    async for chunk in stream_job_events(job_id):
        yield chunk


async def generate_resume_sse_events(job_id: str):
    """Proxy persisted queued worker job events for resumed workflows as SSE."""
    async for chunk in stream_job_events(job_id):
        yield chunk


async def _enqueue_worker_job(session_id: str, trigger: str) -> dict:
    try:
        return await enqueue_generation_job(session_id, trigger, source="api")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _infer_retry_trigger(state: dict) -> str:
    """Choose the next retry entrypoint from the persisted workflow state."""
    if state.get("outline_approved"):
        return "resume_workflow"
    return "start_workflow"


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """健康检查"""
    return {"message": "MAS-PPT API is running", "version": "1.0.0", "service": "api"}


# ==================== 风格 API ====================

@app.get("/api/v1/styles")
async def list_styles():
    """
    返回所有可用风格列表（含预览图 URL）。
    """
    registry = get_registry()
    styles = registry.list_styles()

    # Build lightweight summary list
    result = [
        {
            "id": s["id"],
            "name_zh": s["name_zh"],
            "name_en": s["name_en"],
            "tier": s["tier"],
            "use_cases": s.get("use_cases", []),
            "render_paths": s.get("render_paths", []),
            "sample_image_url": s.get("sample_image_path", ""),
        }
        for s in styles
    ]
    return {"styles": result, "total": len(result)}


@app.get("/api/v1/styles/recommend")
async def recommend_styles(intent: str = Query(..., min_length=1, description="用户意图描述")):
    """
    根据用户意图返回 Top 3 推荐风格 ID 列表。
    """
    recommender = StyleRecommender()
    recommended = recommender.recommend(intent, max_results=3)

    result = [
        {
            "id": s["id"],
            "name_zh": s["name_zh"],
            "name_en": s["name_en"],
            "tier": s["tier"],
            "sample_image_url": s.get("sample_image_path", ""),
        }
        for s in recommended
    ]
    return {"recommended": result, "intent": intent}


@app.get("/api/v1/styles/{style_id}/sample")
async def get_style_sample(style_id: str):
    """
    返回指定风格的预览样例图（静态文件）。
    """
    registry = get_registry()
    style = registry.get_style(style_id)
    if style is None:
        raise HTTPException(status_code=404, detail=f"Style '{style_id}' not found")

    sample_path_str = style.get("sample_image_path", "")
    if not sample_path_str:
        raise HTTPException(status_code=404, detail="No sample image available for this style")

    # sample_image_path is a URL path like "/static/styles/samples/style-01-snoopy.png"
    # Resolve to filesystem path relative to backend/
    relative = sample_path_str.lstrip("/")  # "static/styles/samples/..."
    file_path = Path(__file__).parent / relative

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Sample image file not found on disk")

    return FileResponse(str(file_path), media_type="image/png")


@app.get("/api/v1/assets/{object_key:path}")
async def get_object_asset(object_key: str):
    """Proxy generated assets from object storage."""
    try:
        payload, content_type = get_object_storage().read_object(object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Asset not found")

    return Response(content=payload, media_type=content_type)


@app.post("/api/v1/project/create")
async def create_project(
    project: ProjectCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建项目并启动工作流。

    接受 style_id（新样式系统）或 style（旧主题名，向后兼容）。
    """
    session_id = str(uuid.uuid4())

    # Resolve style from registry when style_id is supplied
    style_config: Optional[dict] = None
    resolved_style_id: Optional[str] = None
    if project.style_id:
        registry = get_registry()
        style_config = registry.get_style(project.style_id)
        if style_config is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown style_id: '{project.style_id}'"
            )
        resolved_style_id = project.style_id

    # Embed render_path_preference into style_config so renderer honours it
    if style_config is not None and project.render_path_preference != "auto":
        style_config = {
            **style_config,
            "render_path_preference": project.render_path_preference,
        }

    # 创建初始状态
    state = create_initial_state(
        session_id=session_id,
        user_intent=project.prompt,
        theme=project.style,
        style_id=resolved_style_id,
        style_config=style_config,
    )

    # 保存到持久化工作流状态存储
    persisted_state = await _save_session_state(session_id, state)
    session_access = AuthService.create_project_access_token(session_id)

    # 如果用户已登录，保存到数据库
    if current_user:
        db_project = Project(
            id=uuid.UUID(session_id),
            user_id=current_user.id,
            user_intent=project.prompt,
            theme=project.style_id or project.style,
            status="created"
        )
        db.add(db_project)
        await db.commit()
        persisted_state = await _save_session_state(session_id, state, project_id=str(db_project.id))

    await create_project_revision(
        session_id,
        "project_created",
        persisted_state,
        project_id=str(db_project.id) if current_user else None,
    )

    return {
        "session_id": session_id,
        "status": "created",
        "session_access_token": session_access.access_token,
    }


@app.get("/api/v1/workflow/start/{session_id}")
async def start_workflow(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    启动工作流（SSE 流式响应）
    """
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    job = await _enqueue_worker_job(session_id, "start_workflow")
    return StreamingResponse(
        generate_sse_events(job["job_id"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/v1/workflow/outline/{session_id}")
async def get_outline(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取生成的大纲"""
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "outline": state.get("outline", []),
        "status": state.get("current_status", "unknown")
    }


@app.post("/api/v1/workflow/outline/update")
async def update_outline(
    data: OutlineUpdate,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    HITL 接口：用户修改大纲
    """
    await _authorize_project_access(data.session_id, data.access_token, current_user, db)
    state = await _load_session_state(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    updated_state = await _merge_session_state(data.session_id, {
        "outline": data.outline,
        "outline_approved": True
    }) or {
        **state,
        "outline": data.outline,
        "outline_approved": True,
    }
    
    await create_project_revision(data.session_id, "outline_updated", updated_state)
    
    return {"status": "outline_updated", "outline": data.outline}


@app.post("/api/v1/project/style")
async def update_project_style(
    data: StyleUpdate,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新项目的视觉风格（在大纲确认后、恢复工作流前调用）。

    The frontend selects style at step 3, after the project is already
    created (step 0) and outline approved (step 2). This endpoint lets
    the frontend attach the chosen style before resuming generation.
    """
    await _authorize_project_access(data.session_id, data.access_token, current_user, db)
    state = await _load_session_state(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    registry = get_registry()
    style_config = registry.get_style(data.style_id)
    if style_config is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown style_id: '{data.style_id}'"
        )

    render_pref = data.render_path_preference
    if render_pref not in ("auto", "path_a", "path_b"):
        render_pref = "auto"

    effective_style_config = {
        **style_config,
        "render_path_preference": render_pref,
        "render_paths": [render_pref] if render_pref in ("path_a", "path_b") else style_config.get("render_paths", ["path_a"]),
    }
    effective_theme_config = {
        "style_id": data.style_id,
        "style": style_config.get("id", data.style_id),
        "name_zh": style_config.get("name_zh", ""),
        "name_en": style_config.get("name_en", ""),
        "tier": style_config.get("tier", 1),
        "colors": style_config.get("colors", {}),
        "typography": style_config.get("typography", {}),
        "render_paths": effective_style_config["render_paths"],
        "base_style_prompt": style_config.get("base_style_prompt", ""),
        "sample_image_path": style_config.get("sample_image_path", ""),
        "render_path_preference": render_pref,
    }
    style_packet = build_style_packet(
        style_id=data.style_id,
        style_config=effective_style_config,
        theme_config=effective_theme_config,
    )
    serialized_style_packet = serialize_models(style_packet)

    updated_state = await _merge_session_state(data.session_id, {
        "style_id": data.style_id,
        "style_config": effective_style_config,
        "style_packet": serialized_style_packet,
        "theme_config": effective_theme_config,
    }) or {
        **state,
        "style_id": data.style_id,
        "style_config": effective_style_config,
        "style_packet": serialized_style_packet,
        "theme_config": effective_theme_config,
    }
    await create_project_revision(data.session_id, "style_updated", updated_state)

    return {
        "status": "style_updated",
        "style_id": data.style_id,
        "style_name": style_config.get("name_zh", ""),
    }


@app.get("/api/v1/workflow/resume/{session_id}")
async def resume_workflow(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    恢复工作流（用户确认大纲后）
    """
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    job = await _enqueue_worker_job(session_id, "resume_workflow")
    return StreamingResponse(
        generate_resume_sse_events(job["job_id"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/v1/project/download/{session_id}")
async def download_pptx(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载生成的 PPTX 文件"""
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    storage_key = state.get("pptx_storage_key", "")
    if storage_key:
        try:
            payload, content_type = get_object_storage().read_object(storage_key)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="PPTX file not found")

        return Response(
            content=payload,
            media_type=content_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="presentation_{session_id[:8]}.pptx"'
                )
            },
        )

    pptx_path = state.get("pptx_path", "")
    if not pptx_path or not Path(pptx_path).exists():
        raise HTTPException(status_code=404, detail="PPTX file not found")

    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"presentation_{session_id[:8]}.pptx"
    )


@app.get("/api/v1/project/status/{session_id}")
async def get_project_status(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目状态"""
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "status": state.get("current_status", "unknown"),
        "current_agent": state.get("current_agent", ""),
        "outline": state.get("outline", []),
        "slides_count": len(state.get("slides_data", [])),
        "pptx_path": state.get("pptx_path", ""),
        "error": state.get("error")
    }


@app.get("/api/v1/project/preview/{session_id}")
async def get_project_preview(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a stable preview payload for the current persisted workflow state."""
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    preview = build_project_preview(state)
    return {
        "session_id": session_id,
        "status": state.get("current_status", "unknown"),
        "pptx_path": state.get("pptx_path", ""),
        "pptx_storage_key": state.get("pptx_storage_key", ""),
        "preview": preview,
        "last_restored_revision_number": state.get("last_restored_revision_number"),
    }


@app.get("/api/v1/project/revisions/{session_id}")
async def get_project_revisions(
    session_id: str,
    limit: int = Query(20, ge=1, le=100),
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List persisted revision history for a project session."""
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    revisions = await list_project_revisions(session_id, limit=limit)
    return {
        "session_id": session_id,
        "revisions": revisions,
        "total": await count_project_revisions(session_id),
    }


@app.post("/api/v1/project/revisions/restore")
async def restore_project_revision(
    data: RevisionRestoreRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore the current session state from a historical revision snapshot."""
    await _authorize_project_access(data.session_id, data.access_token, current_user, db)
    state = await _load_session_state(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    active_job = await find_session_active_generation_job(data.session_id)
    if active_job is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot restore revisions while a generation job is active",
        )

    restored = await restore_project_revision_snapshot(
        data.session_id,
        revision_number=data.revision_number,
        revision_id=data.revision_id,
    )
    if restored is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    restored_state = restored["state"]
    style_packet = restored_state.get("style_packet", {}) or {}
    return {
        "status": "revision_restored",
        "session_id": data.session_id,
        "restored_revision": restored["restored_revision"],
        "restoration_revision": restored["restoration_revision"],
        "current_state": {
            "status": restored_state.get("current_status", "unknown"),
            "current_agent": restored_state.get("current_agent", ""),
            "outline": restored_state.get("outline", []),
            "style_id": restored_state.get("style_id") or style_packet.get("style_id", ""),
            "pptx_path": restored_state.get("pptx_path", ""),
            "last_restored_revision_number": restored_state.get("last_restored_revision_number"),
        },
    }


@app.get("/api/v1/project/failure/{session_id}")
async def get_project_failure(
    session_id: str,
    access_token: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest user-facing failure summary for a project session."""
    await _authorize_project_access(session_id, access_token, current_user, db)
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    failure = await get_generation_failure(session_id)
    return {
        "session_id": session_id,
        "failure": failure,
    }


@app.post("/api/v1/project/retry")
async def retry_project_generation(
    data: RetryRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue a retry for the latest failed workflow phase."""
    await _authorize_project_access(data.session_id, data.access_token, current_user, db)
    state = await _load_session_state(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    active_job = await find_session_active_generation_job(data.session_id)
    if active_job is not None:
        raise HTTPException(status_code=409, detail="Generation is already in progress")

    failure = await get_generation_failure(data.session_id)
    if failure and not failure["retry_available"]:
        raise HTTPException(status_code=409, detail=failure["message"])

    trigger = data.trigger or (failure["retry_trigger"] if failure else None) or _infer_retry_trigger(state)
    job = await _enqueue_worker_job(data.session_id, trigger)
    return {
        "status": "retry_queued",
        "session_id": data.session_id,
        "job_id": job["job_id"],
        "trigger": trigger,
    }


@app.get("/api/v1/operator/jobs/failed")
async def operator_list_failed_jobs(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_operator_user),
):
    """List recent failed jobs for operator triage."""
    jobs = await list_failed_generation_jobs(limit=limit)
    return {
        "operator": current_user.email,
        "jobs": jobs,
        "total": len(jobs),
    }


@app.get("/api/v1/operator/jobs/{job_id}")
async def operator_get_job_detail(
    job_id: str,
    current_user: User = Depends(get_current_operator_user),
):
    """Return job details, failure summary, and persisted events for operators."""
    job = await get_generation_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "operator": current_user.email,
        "job": job,
        "failure": await get_generation_failure_for_job(job_id),
        "events": await list_job_events(job_id),
    }


@app.get("/api/v1/operator/sessions/{session_id}/support")
async def operator_get_support_snapshot(
    session_id: str,
    current_user: User = Depends(get_current_operator_user),
):
    """Return a single support snapshot for a failed or in-progress session."""
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    jobs = await list_session_generation_jobs(session_id, limit=10)
    latest_job_id = jobs[0]["job_id"] if jobs else None
    latest_job_events = await list_job_events(latest_job_id) if latest_job_id else []
    return {
        "operator": current_user.email,
        "session_id": session_id,
        "current_state": {
            "status": state.get("current_status", "unknown"),
            "current_agent": state.get("current_agent", ""),
            "error": state.get("error"),
        },
        "preview": build_project_preview(state),
        "failure": await get_generation_failure(session_id),
        "revisions": await list_project_revisions(session_id, limit=10),
        "jobs": jobs,
        "latest_job_events": latest_job_events[-25:],
    }


@app.post("/api/v1/operator/jobs/{job_id}/retry")
async def operator_retry_failed_job(
    job_id: str,
    current_user: User = Depends(get_current_operator_user),
):
    """Retry a failed job using the same session and trigger."""
    job = await get_generation_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    active_job = await find_session_active_generation_job(job["session_id"])
    if active_job is not None:
        raise HTTPException(status_code=409, detail="Generation is already in progress")

    queued = await _enqueue_worker_job(job["session_id"], job["trigger"])
    return {
        "operator": current_user.email,
        "status": "retry_queued",
        "source_job_id": job_id,
        "session_id": job["session_id"],
        "job_id": queued["job_id"],
        "trigger": job["trigger"],
    }


@app.post("/api/v1/operator/sessions/{session_id}/restore")
async def operator_restore_project_revision(
    session_id: str,
    data: OperatorRevisionRestoreRequest,
    current_user: User = Depends(get_current_operator_user),
):
    """Restore a historical revision without requiring project-level user access."""
    state = await _load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    active_job = await find_session_active_generation_job(session_id)
    if active_job is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot restore revisions while a generation job is active",
        )

    restored = await restore_project_revision_snapshot(
        session_id,
        revision_number=data.revision_number,
        revision_id=data.revision_id,
    )
    if restored is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    restored_state = restored["state"]
    return {
        "operator": current_user.email,
        "status": "revision_restored",
        "session_id": session_id,
        "restored_revision": restored["restored_revision"],
        "restoration_revision": restored["restoration_revision"],
        "preview": build_project_preview(restored_state),
        "current_state": {
            "status": restored_state.get("current_status", "unknown"),
            "current_agent": restored_state.get("current_agent", ""),
            "outline": restored_state.get("outline", []),
            "style_id": restored_state.get("style_id", ""),
            "pptx_path": restored_state.get("pptx_path", ""),
            "last_restored_revision_number": restored_state.get("last_restored_revision_number"),
        },
    }


@app.get("/api/v1/projects")
async def list_projects(current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """获取当前用户的项目列表"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    
    return {
        "projects": [
            {
                "id": str(p.id),
                "user_intent": p.user_intent,
                "theme": p.theme,
                "status": p.status,
                "created_at": p.created_at.isoformat()
            }
            for p in projects
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
