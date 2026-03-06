"""
MAS-PPT 多智能体演示文稿生成系统
FastAPI 后端服务 - 集成数据库和认证
"""

import asyncio
import logging
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from state import PresentationState, create_initial_state
from graph import get_main_app, get_resume_app
from database.postgres import get_db, init_db, close_db
from database.redis_client import redis_client
from database.models import User, Project
from database.project_tracking_store import (
    create_generation_job,
    create_project_revision,
    record_job_event,
    sync_project_state,
    update_generation_job,
)
from database.workflow_state_store import (
    load_workflow_state,
    save_workflow_state,
    update_workflow_state,
)
from auth import auth_router, get_current_user, get_current_active_user
from auth.service import AuthService
from styles.registry import get_registry
from styles.recommender import StyleRecommender

logger = logging.getLogger(__name__)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 MAS-PPT 系统启动中...")
    
    # 初始化数据库
    await init_db()
    print("✅ PostgreSQL 数据库初始化完成")

    if await _connect_optional_redis():
        print("✅ Redis 连接成功")
    else:
        print("⚠️ Redis 不可用，系统以 PostgreSQL-only 模式运行")
    
    yield
    
    # 关闭连接
    await _disconnect_optional_redis()
    await close_db()
    print("👋 MAS-PPT 系统关闭")


app = FastAPI(
    title="MAS-PPT API",
    description="多智能体协同演示文稿生成系统",
    version="1.0.0",
    lifespan=lifespan
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

async def generate_sse_events(session_id: str, state: PresentationState):
    """生成 SSE 事件流"""
    main_app = get_main_app()
    job = await create_generation_job(session_id, "start_workflow", dict(state))
    job_id = job["job_id"]
    
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        async for event in main_app.astream(state, config):
            for node_name, node_output in event.items():
                if node_name == "__end__":
                    continue
                    
                status = node_output.get("current_status", "processing")
                agent = node_output.get("current_agent", node_name)
                messages = node_output.get("messages", [])
                
                data = {
                    "type": "status",
                    "agent": agent,
                    "status": status,
                    "message": messages[-1]["content"] if messages else ""
                }
                persisted_state = await _merge_session_state(session_id, node_output) or dict(state)
                await update_generation_job(job_id, state=persisted_state, status=status)
                await record_job_event(session_id, data["type"], data, job_id=job_id)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                await asyncio.sleep(0.1)
        
        # 获取最终状态
        final_state = await _load_session_state(session_id) or {}
        
        if final_state.get("current_status") == "waiting_for_outline_approval":
            hitl_data = {
                "type": "hitl",
                "status": "waiting_for_approval",
                "outline": final_state.get("outline", []),
            }
            await update_generation_job(
                job_id,
                state=final_state,
                status="waiting_for_outline_approval",
            )
            await record_job_event(session_id, hitl_data["type"], hitl_data, job_id=job_id)
            await create_project_revision(session_id, "outline_generated", final_state)
            yield f"data: {json.dumps(hitl_data, ensure_ascii=False)}\n\n"
        else:
            complete_data = {"type": "complete", "status": "done"}
            await update_generation_job(job_id, state=final_state, status="completed")
            await record_job_event(session_id, complete_data["type"], complete_data, job_id=job_id)
            await create_project_revision(session_id, "generation_completed", final_state)
            yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        current_state = await _load_session_state(session_id) or dict(state)
        error_data = {"type": "error", "status": "error", "message": str(e)}
        await update_generation_job(
            job_id,
            state=current_state,
            status="error",
            error_message=str(e),
        )
        await record_job_event(session_id, error_data["type"], error_data, job_id=job_id)
        await create_project_revision(session_id, "generation_failed", current_state)
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


async def generate_resume_sse_events(session_id: str):
    """生成恢复阶段的 SSE 事件流"""
    resume_app = get_resume_app()
    state = await _load_session_state(session_id)

    if not state:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'}, ensure_ascii=False)}\n\n"
        return

    state["outline_approved"] = True
    await _save_session_state(session_id, state)
    job = await create_generation_job(session_id, "resume_workflow", dict(state))
    job_id = job["job_id"]

    config = {"configurable": {"thread_id": f"{session_id}_resume"}}

    try:
        async for event in resume_app.astream(dict(state), config):
            for node_name, node_output in event.items():
                if node_name == "__end__":
                    continue

                status = node_output.get("current_status", "processing")
                agent = node_output.get("current_agent", node_name)
                messages = node_output.get("messages", [])

                # Emit the standard status event
                data = {
                    "type": "status",
                    "agent": agent,
                    "status": status,
                    "message": messages[-1]["content"] if messages else ""
                }
                persisted_state = await _merge_session_state(session_id, node_output) or dict(state)
                await update_generation_job(job_id, state=persisted_state, status=status)
                await record_job_event(session_id, data["type"], data, job_id=job_id)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                # Emit individual render_progress events if the renderer produced them
                render_progress_events: list[dict] = node_output.get(
                    "render_progress_events", []
                )
                for rpe in render_progress_events:
                    await record_job_event(session_id, rpe.get("type", "render_progress"), rpe, job_id=job_id)
                    yield f"data: {json.dumps(rpe, ensure_ascii=False)}\n\n"

                await asyncio.sleep(0.1)

        final_state = await _load_session_state(session_id) or {}
        pptx_path = final_state.get("pptx_path", "")
        complete_data = {
            "type": "complete",
            "status": "done",
            "pptx_path": pptx_path,
        }
        await update_generation_job(job_id, state=final_state, status="completed")
        await record_job_event(session_id, complete_data["type"], complete_data, job_id=job_id)
        await create_project_revision(session_id, "generation_completed", final_state)
        yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

    except Exception as e:
        current_state = await _load_session_state(session_id) or dict(state)
        error_data = {"type": "error", "status": "error", "message": str(e)}
        await update_generation_job(
            job_id,
            state=current_state,
            status="error",
            error_message=str(e),
        )
        await record_job_event(session_id, error_data["type"], error_data, job_id=job_id)
        await create_project_revision(session_id, "generation_failed", current_state)
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """健康检查"""
    return {"message": "MAS-PPT API is running", "version": "1.0.0"}


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
    
    return StreamingResponse(
        generate_sse_events(session_id, state),
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

    updated_state = await _merge_session_state(data.session_id, {
        "theme_config": {
            "style_id": data.style_id,
            "style": style_config.get("id", data.style_id),
            "name_zh": style_config.get("name_zh", ""),
            "name_en": style_config.get("name_en", ""),
            "tier": style_config.get("tier", 1),
            "colors": style_config.get("colors", {}),
            "typography": style_config.get("typography", {}),
            "render_paths": style_config.get("render_paths", ["path_a"]),
            "base_style_prompt": style_config.get("base_style_prompt", ""),
            "sample_image_path": style_config.get("sample_image_path", ""),
            "render_path_preference": render_pref,
        }
    }) or {
        **state,
        "theme_config": {
            "style_id": data.style_id,
            "style": style_config.get("id", data.style_id),
            "name_zh": style_config.get("name_zh", ""),
            "name_en": style_config.get("name_en", ""),
            "tier": style_config.get("tier", 1),
            "colors": style_config.get("colors", {}),
            "typography": style_config.get("typography", {}),
            "render_paths": style_config.get("render_paths", ["path_a"]),
            "base_style_prompt": style_config.get("base_style_prompt", ""),
            "sample_image_path": style_config.get("sample_image_path", ""),
            "render_path_preference": render_pref,
        },
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
    
    return StreamingResponse(
        generate_resume_sse_events(session_id),
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
