"""
MAS-PPT 多智能体演示文稿生成系统
FastAPI 后端服务 - 集成数据库和认证
"""

import asyncio
import hashlib
import logging
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Depends, Query, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from rate_limit import limiter, SLOWAPI_AVAILABLE
from state import PresentationState, create_initial_state
from graph import get_main_app, get_resume_app
from database.postgres import get_db, init_db, close_db, AsyncSessionLocal
from database.redis_client import redis_client
from database.models import User, Project, Slide
from auth import auth_router, get_current_user, get_current_active_user, get_current_active_user_sse
from agents.blueprint import run as blueprint_agent
from agents.blueprint.tools import normalize_slide_blueprint, validate_slide_blueprint
from agents import writer_agent, visual_agent, renderer_agent
from skills.runtime import get_skill_runtime_packet, list_skill_runtimes
from styles.registry import get_registry
from styles.recommender import StyleRecommender
from services.document_parser import parse_document, get_chapter_summary, ALLOWED_EXTENSIONS as DOC_EXTENSIONS


async def _verify_project_ownership(session_id: str, user: User, db: AsyncSession) -> Project:
    """Verify that session_id belongs to user. Raises HTTPException if not."""
    from sqlalchemy import select
    try:
        project_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid session ID format")

    result = await db.execute(
        select(Project).where(Project.id == project_uuid)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project


def _hydrate_skill_runtime_state(state: dict[str, Any]) -> dict[str, Any]:
    """Backfill SkillRuntime fields for legacy sessions."""
    if state.get("skill_packet"):
        state.setdefault("slide_reviews", [])
        state.setdefault("slide_review_required", False)
        state.setdefault("slide_review_approved", False)
        return state

    skill_id = state.get("skill_id") or "huashu-slides"
    collaboration_mode = state.get("collaboration_mode") or "guided"
    skill_packet = get_skill_runtime_packet(skill_id, collaboration_mode)
    state.update(
        {
            "skill_id": skill_packet["skill_id"],
            "collaboration_mode": skill_packet["collaboration_mode"],
            "skill_packet": skill_packet,
            "slide_reviews": state.get("slide_reviews", []),
            "slide_review_required": state.get("slide_review_required", False),
            "slide_review_approved": state.get("slide_review_approved", False),
        }
    )
    return state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 MAS-PPT 系统启动中...")

    # Validate critical settings before anything else
    try:
        settings.validate_settings()
    except RuntimeError as e:
        print(f"[STARTUP ERROR] {e}")
        raise

    # 连接 Redis
    await redis_client.connect()
    print("✅ Redis 连接成功")

    # 初始化数据库
    await init_db()
    print("✅ PostgreSQL 数据库初始化完成")

    from agents.renderer.paths import cleanup_tmp_files
    removed = cleanup_tmp_files()
    if removed:
        print(f"🧹 Cleaned up {removed} temp files")
    
    yield
    
    # 关闭连接
    await redis_client.disconnect()
    await close_db()
    print("👋 MAS-PPT 系统关闭")


app = FastAPI(
    title="MAS-PPT API",
    description="多智能体协同演示文稿生成系统",
    version="1.0.0",
    lifespan=lifespan
)

# 速率限制（仅在 slowapi 可用时生效）
if SLOWAPI_AVAILABLE:
    from slowapi.errors import RateLimitExceeded
    from slowapi import _rate_limit_exceeded_handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
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

# ==================== 文件上传常量 ====================

_upload_dir = Path(__file__).parent / "uploads"
_upload_dir.mkdir(exist_ok=True)
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


class ProjectCreate(BaseModel):
    prompt: str
    style_id: Optional[str] = None                # new style system (preferred)
    style: str = "organic"                         # legacy fallback
    skill_id: str = "huashu-slides"
    collaboration_mode: str = "guided"
    render_path_preference: str = "auto"           # "auto" | "path_a" | "path_b"
    source_docs: Optional[List[Dict[str, Any]]] = None  # 预解析的论文 chunks
    is_thesis_mode: bool = False                   # 答辩PPT模式

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("prompt must not be empty")
        v = v.strip()
        if len(v) > 2000:
            raise ValueError("prompt must not exceed 2000 characters")
        return v

    @field_validator("render_path_preference")
    @classmethod
    def valid_render_path(cls, v: str) -> str:
        if v not in ("auto", "path_a", "path_b"):
            return "auto"
        return v

    @field_validator("collaboration_mode")
    @classmethod
    def valid_collaboration_mode(cls, v: str) -> str:
        normalized = (v or "guided").strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in {"full_auto", "guided", "collaborative"}:
            return "guided"
        return normalized


class OutlineUpdate(BaseModel):
    session_id: str
    outline: List[Dict[str, Any]]

    @field_validator("outline")
    @classmethod
    def outline_length_limit(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(v) > 30:
            raise ValueError("outline must not exceed 30 items")
        return v


class WorkflowResume(BaseModel):
    session_id: str


class WorkflowBlueprintGenerate(BaseModel):
    session_id: str


class StyleUpdate(BaseModel):
    session_id: str
    style_id: str
    render_path_preference: str = "auto"  # "auto" | "path_a" | "path_b"


class BlueprintUpdate(BaseModel):
    session_id: str
    slide_blueprint: List[Dict[str, Any]]

    @field_validator("slide_blueprint")
    @classmethod
    def blueprint_length_limit(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(v) > 40:
            raise ValueError("slide_blueprint must not exceed 40 pages")
        return v


class SlideReviewUpdate(BaseModel):
    session_id: str
    page_number: int
    slide_patch: Dict[str, Any] = {}
    render_patch: Dict[str, Any] = {}
    feedback: str = ""


class SlideReviewAction(BaseModel):
    session_id: str
    page_number: int


class SlideReviewContinue(BaseModel):
    session_id: str


# ==================== DB helpers ====================

async def _update_project_completed(session_id: str, pptx_path: str, slide_count: int) -> None:
    """Update project status and persist slide data to DB after generation completes."""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import update, delete
            project_uuid = uuid.UUID(session_id)

            # Update project status
            await db.execute(
                update(Project)
                .where(Project.id == project_uuid)
                .values(status="completed", pptx_path=pptx_path)
            )

            # Persist slides from Redis
            state = await redis_client.get_session(session_id)
            if state:
                slides_data = state.get("slides_data", [])
                # Remove old slides first (idempotent)
                await db.execute(
                    delete(Slide).where(Slide.project_id == project_uuid)
                )
                # Insert new slides
                for i, sd in enumerate(slides_data):
                    slide = Slide(
                        project_id=project_uuid,
                        page_number=sd.get("page_number", i + 1),
                        title=sd.get("title", ""),
                        content=sd.get("content", {}),
                        layout_name=sd.get("layout_name", sd.get("layout_intent", "bullet_list")),
                        speaker_notes=sd.get("speaker_notes", ""),
                    )
                    db.add(slide)

            await db.commit()
            logger.info("Project %s marked completed (slides=%d persisted)", session_id[:8], slide_count)
    except Exception:
        logger.exception("Failed to update project %s in DB", session_id[:8])


def _build_slide_review_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Build a collaborative review payload from current slide drafts."""
    slides_data = state.get("slides_data", []) or []
    render_plans = state.get("slide_render_plans", []) or []
    reviews = state.get("slide_reviews", []) or []

    slides_by_page = {
        int(slide.get("page_number", index + 1)): slide
        for index, slide in enumerate(slides_data)
    }
    plans_by_page = {
        int(plan.get("page_number", index + 1)): plan
        for index, plan in enumerate(render_plans)
    }
    reviews_by_page = {
        int(review.get("page_number", index + 1)): review
        for index, review in enumerate(reviews)
    }

    pages = sorted(set(slides_by_page) | set(plans_by_page) | set(reviews_by_page))
    items: list[dict[str, Any]] = []
    for page_number in pages:
        slide = slides_by_page.get(page_number, {})
        plan = plans_by_page.get(page_number, {})
        review = reviews_by_page.get(page_number, {})
        bullet_points = slide.get("content", {}).get("bullet_points", [])
        items.append(
            {
                "page_number": page_number,
                "title": slide.get("title", ""),
                "visual_type": slide.get("visual_type", plan.get("visual_type", "")),
                "path_hint": slide.get("path_hint", plan.get("render_path", "auto")),
                "render_path": plan.get("render_path", "path_a"),
                "layout_name": slide.get("layout_intent", plan.get("layout_name", "bullet_list")),
                "bullet_points": bullet_points,
                "speaker_notes": slide.get("speaker_notes", ""),
                "image_prompt": slide.get("image_prompt") or plan.get("image_prompt", ""),
                "html_content": plan.get("html_content", ""),
                "style_notes": plan.get("style_notes", ""),
                "review_status": review.get("status", "pending"),
                "accepted": bool(review.get("accepted", False)),
                "revision_count": int(review.get("revision_count", 0)),
                "feedback": review.get("feedback", ""),
            }
        )

    approved = bool(items) and all(item["accepted"] for item in items)
    return {
        "session_id": state.get("session_id", ""),
        "slides": items,
        "approved": approved,
        "status": state.get("current_status", "waiting_for_slide_review"),
    }


def _merge_slide_review_status(
    state: dict[str, Any],
    page_number: int,
    *,
    accepted: bool | None = None,
    status: str | None = None,
    feedback: str | None = None,
    revision_increment: bool = False,
) -> list[dict[str, Any]]:
    reviews = list(state.get("slide_reviews", []) or [])
    updated = False
    for item in reviews:
        if int(item.get("page_number", 0)) != page_number:
            continue
        if accepted is not None:
            item["accepted"] = accepted
        if status is not None:
            item["status"] = status
        if feedback is not None:
            item["feedback"] = feedback
        if revision_increment:
            item["revision_count"] = int(item.get("revision_count", 0)) + 1
        updated = True
        break

    if not updated:
        reviews.append(
            {
                "page_number": page_number,
                "accepted": accepted if accepted is not None else False,
                "status": status or "pending",
                "feedback": feedback or "",
                "revision_count": 1 if revision_increment else 0,
            }
        )
    return sorted(reviews, key=lambda item: int(item.get("page_number", 0)))


def _update_slide_for_page(items: list[dict[str, Any]], page_number: int, patch: dict[str, Any]) -> list[dict[str, Any]]:
    updated_items = []
    for index, item in enumerate(items):
        current_page = int(item.get("page_number", index + 1))
        if current_page == page_number:
            updated_items.append({**item, **patch, "page_number": page_number})
        else:
            updated_items.append(item)
    return updated_items


async def _regenerate_single_slide(state: dict[str, Any], page_number: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Regenerate a single slide via writer+visual using its blueprint item."""
    blueprint_items = state.get("slide_blueprint", []) or []
    target_blueprint = next(
        (
            item
            for item in blueprint_items
            if int(item.get("page_number", 0) or 0) == page_number
        ),
        None,
    )
    if target_blueprint is None:
        raise HTTPException(status_code=404, detail=f"Blueprint for page {page_number} not found")

    regen_state = {
        **state,
        "slide_blueprint": [target_blueprint],
        "slides_data": [],
        "slide_render_plans": [],
        "slide_review_required": False,
        "slide_review_approved": False,
    }
    writer_result = await writer_agent(regen_state)
    if writer_result.get("error"):
        raise HTTPException(status_code=500, detail=writer_result["error"])

    visual_result = await visual_agent({**regen_state, **writer_result})
    if visual_result.get("error"):
        raise HTTPException(status_code=500, detail=visual_result["error"])

    slides_data = list(state.get("slides_data", []) or [])
    render_plans = list(state.get("slide_render_plans", []) or [])
    if writer_result.get("slides_data"):
        slides_data = _update_slide_for_page(slides_data, page_number, writer_result["slides_data"][0])
    if visual_result.get("slide_render_plans"):
        render_plans = _update_slide_for_page(render_plans, page_number, visual_result["slide_render_plans"][0])
    return slides_data, render_plans


# ==================== SSE 流式响应 ====================

async def generate_sse_events(session_id: str, state: PresentationState):
    """生成 SSE 事件流"""
    main_app = get_main_app()
    state = _hydrate_skill_runtime_state(dict(state))
    
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        async for event in main_app.astream(state, config):
            for node_name, node_output in event.items():
                if node_name == "__end__":
                    continue

                # LangGraph interrupt_before 可能产生非 dict 输出（如 tuple）
                if not isinstance(node_output, dict):
                    logger.debug(
                        "Skipping non-dict event: node=%s type=%s",
                        node_name, type(node_output).__name__,
                    )
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
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                # 更新 Redis 缓存
                await redis_client.update_session(session_id, node_output)
                await redis_client.push_log(session_id, data)

                await asyncio.sleep(0.1)

        # 获取最终状态
        final_state = await redis_client.get_session(session_id) or {}
        outline = final_state.get("outline", [])
        approved = final_state.get("outline_approved", False)

        # interrupt_before 在 wait_for_approval 前中断，
        # 此时 current_status 为 "outline_generated" 而非 "waiting_for_outline_approval"
        if outline and not approved:
            yield f"data: {json.dumps({'type': 'hitl', 'status': 'waiting_for_approval', 'outline': outline}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'complete', 'status': 'done'}, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        logger.exception("SSE workflow error for session %s", session_id)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


async def generate_resume_sse_events(session_id: str):
    """生成恢复阶段的 SSE 事件流"""
    resume_app = get_resume_app()
    state = await redis_client.get_session(session_id)

    if not state:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'}, ensure_ascii=False)}\n\n"
        return

    state = _hydrate_skill_runtime_state(state)
    state["outline_approved"] = True

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
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                # Emit individual render_progress events if the renderer produced them
                render_progress_events: list[dict] = node_output.get(
                    "render_progress_events", []
                )
                for rpe in render_progress_events:
                    yield f"data: {json.dumps(rpe, ensure_ascii=False)}\n\n"

                await redis_client.update_session(session_id, node_output)
                await redis_client.push_log(session_id, data)
                await asyncio.sleep(0.1)

        final_state = await redis_client.get_session(session_id) or {}
        final_state = _hydrate_skill_runtime_state(final_state)
        pptx_path = final_state.get("pptx_path", "")
        slide_count = len(final_state.get("slides_data", []))

        # Persist completion to database
        if pptx_path:
            await _update_project_completed(session_id, pptx_path, slide_count)
        elif (
            final_state.get("collaboration_mode") == "collaborative"
            and final_state.get("current_status") == "waiting_for_slide_review"
        ):
            review_payload = _build_slide_review_payload(final_state)
            yield f"data: {json.dumps({'type': 'hitl', 'status': 'waiting_for_slide_review', 'review': review_payload}, ensure_ascii=False)}\n\n"
            return

        yield f"data: {json.dumps({'type': 'complete', 'status': 'done', 'pptx_path': pptx_path}, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.exception("SSE resume workflow error for session %s", session_id)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


async def generate_render_only_sse_events(session_id: str):
    """Render-only SSE stream after collaborative review is approved."""
    state = await redis_client.get_session(session_id)
    if not state:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'}, ensure_ascii=False)}\n\n"
        return

    state = _hydrate_skill_runtime_state(state)
    slides = _build_slide_review_payload(state)["slides"]
    if slides:
        init_payload = {
            "type": "slides_initialized",
            "slides": [
                {
                    "index": max(int(slide.get("page_number", 1)) - 1, 0),
                    "title": slide.get("title", ""),
                    "render_path": slide.get("render_path", "path_a"),
                }
                for slide in slides
            ],
        }
        yield f"data: {json.dumps(init_payload, ensure_ascii=False)}\n\n"

    yield f"data: {json.dumps({'type': 'status', 'agent': 'renderer', 'status': 'rendering', 'message': '正在根据审阅后的页面开始渲染'}, ensure_ascii=False)}\n\n"

    try:
        result = await renderer_agent(state)
        await redis_client.update_session(session_id, result)

        data = {
            "type": "status",
            "agent": result.get("current_agent", "renderer"),
            "status": result.get("current_status", "processing"),
            "message": (result.get("messages") or [{}])[-1].get("content", ""),
        }
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        for event in result.get("render_progress_events", []) or []:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if result.get("error"):
            yield f"data: {json.dumps({'type': 'error', 'message': result['error']}, ensure_ascii=False)}\n\n"
            return

        pptx_path = result.get("pptx_path", "")
        slide_count = len(state.get("slides_data", []))
        if pptx_path:
            await _update_project_completed(session_id, pptx_path, slide_count)
        yield f"data: {json.dumps({'type': 'complete', 'status': 'done', 'pptx_path': pptx_path}, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.exception("Render-only SSE error for session %s", session_id)
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"


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


# ==================== 文档上传 ====================

@app.post("/api/v1/document/upload")
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """
    上传论文文件（PDF/DOCX），解析为 source_docs 列表。

    返回解析结果，前端在创建项目时将 source_docs 传入。
    """
    # 验证文件名
    if not file.filename:
        raise HTTPException(status_code=422, detail="文件名不能为空")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in DOC_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的文件类型: {suffix}，仅支持 PDF 和 DOCX",
        )

    # 读取文件内容并检查大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"文件过大（{len(content) // 1024 // 1024}MB），最大支持 15MB",
        )

    if not content:
        raise HTTPException(status_code=422, detail="文件内容为空")

    # 保存到临时文件（用 hash 避免文件名冲突）
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    safe_filename = f"{file_hash}{suffix}"
    file_path = _upload_dir / safe_filename

    file_path.write_bytes(content)

    try:
        source_docs = parse_document(str(file_path), file.filename)
        chapters = get_chapter_summary(source_docs)

        return {
            "document_id": file_hash,
            "filename": file.filename,
            "source_docs": source_docs,
            "chunk_count": len(source_docs),
            "chapters": chapters,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Document parsing failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"文档解析失败: {str(e)}")


# ==================== 项目创建 ====================

@app.post("/api/v1/project/create")
@limiter.limit("5/minute")
async def create_project(
    request: Request,
    project: ProjectCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建项目并启动工作流。

    接受 style_id（新样式系统）或 style（旧主题名，向后兼容）。
    当 source_docs 和 is_thesis_mode 提供时，启用答辩PPT模式。
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

    try:
        skill_packet = get_skill_runtime_packet(project.skill_id, project.collaboration_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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
        skill_id=skill_packet["skill_id"],
        collaboration_mode=skill_packet["collaboration_mode"],
        source_docs=project.source_docs,
        is_thesis_mode=project.is_thesis_mode,
    )

    # 保存到 Redis
    await redis_client.set_session(session_id, state)

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

    return {
        "session_id": session_id,
        "status": "created",
        "skill_id": skill_packet["skill_id"],
        "collaboration_mode": skill_packet["collaboration_mode"],
    }


@app.get("/api/v1/skills")
async def get_skill_runtimes():
    """列出当前项目可用的本地 SkillRuntime。"""
    return {"skills": list_skill_runtimes(), "total": len(list_skill_runtimes())}


@app.get("/api/v1/skills/{skill_id}")
async def get_skill_runtime_detail(skill_id: str):
    """获取指定 SkillRuntime 的结构化配置。"""
    try:
        return get_skill_runtime_packet(skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/v1/workflow/start/{session_id}")
@limiter.limit("10/minute")
async def start_workflow(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user_sse),
    db: AsyncSession = Depends(get_db),
):
    """
    启动工作流（SSE 流式响应）
    """
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    
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
async def get_outline(session_id: str):
    """获取生成的大纲"""
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    
    return {
        "outline": state.get("outline", []),
        "status": state.get("current_status", "unknown")
    }


@app.post("/api/v1/workflow/outline/update")
async def update_outline(
    data: OutlineUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    HITL 接口：用户修改大纲
    """
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    
    # 更新 Redis
    await redis_client.update_session(data.session_id, {
        "outline": data.outline,
        "outline_approved": True,
        "slide_blueprint": [],
        "slide_blueprint_approved": False,
        "slide_reviews": [],
        "slide_review_required": False,
        "slide_review_approved": False,
    })
    
    # 更新数据库
    from sqlalchemy import update
    await db.execute(
        update(Project)
        .where(Project.id == uuid.UUID(data.session_id))
        .values(outline=data.outline, status="outline_approved")
    )
    await db.commit()
    
    return {"status": "outline_updated", "outline": data.outline}


@app.post("/api/v1/workflow/blueprint/generate")
async def generate_blueprint(
    data: WorkflowBlueprintGenerate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """根据确认后的章节级大纲生成逐页 Slide Blueprint。"""
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    if not state.get("outline"):
        raise HTTPException(status_code=422, detail="Outline must be generated before blueprint")
    if not state.get("outline_approved", False):
        raise HTTPException(status_code=409, detail="Outline must be approved before blueprint")
    if state.get("slide_blueprint"):
        return {
            "status": state.get("current_status", "blueprint_generated"),
            "slide_blueprint": state.get("slide_blueprint", []),
        }

    result = await blueprint_agent(state)
    payload = {
        "slide_blueprint": result.get("slide_blueprint", []),
        "slide_blueprint_approved": False,
        "current_status": "blueprint_generated",
        "current_agent": "blueprint_planner",
        "messages": result.get("messages", state.get("messages", [])),
    }
    await redis_client.update_session(data.session_id, payload)

    from sqlalchemy import update
    await db.execute(
        update(Project)
        .where(Project.id == uuid.UUID(data.session_id))
        .values(status="blueprint_generated")
    )
    await db.commit()

    return {
        "status": "blueprint_generated",
        "slide_blueprint": payload["slide_blueprint"],
    }


@app.get("/api/v1/workflow/blueprint/{session_id}")
async def get_blueprint(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取逐页 Slide Blueprint。"""
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)

    return {
        "slide_blueprint": state.get("slide_blueprint", []),
        "status": state.get("current_status", "unknown"),
        "approved": state.get("slide_blueprint_approved", False),
    }


@app.post("/api/v1/workflow/blueprint/update")
async def update_blueprint(
    data: BlueprintUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """用户确认或修改逐页 Slide Blueprint。"""
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    outline = state.get("outline", [])
    if not outline:
        raise HTTPException(status_code=422, detail="Outline must be generated before blueprint")
    if not state.get("outline_approved", False):
        raise HTTPException(status_code=409, detail="Outline must be approved before blueprint")

    normalized_blueprint = normalize_slide_blueprint(data.slide_blueprint)
    is_valid, message = validate_slide_blueprint(normalized_blueprint, outline)
    if not is_valid:
        raise HTTPException(status_code=422, detail=message)

    await redis_client.update_session(
        data.session_id,
        {
            "slide_blueprint": normalized_blueprint,
            "slide_blueprint_approved": True,
            "slide_reviews": [],
            "slide_review_required": False,
            "slide_review_approved": False,
            "current_status": "blueprint_approved",
        },
    )

    from sqlalchemy import update
    await db.execute(
        update(Project)
        .where(Project.id == uuid.UUID(data.session_id))
        .values(status="blueprint_approved")
    )
    await db.commit()

    return {
        "status": "blueprint_updated",
        "slide_blueprint": normalized_blueprint,
    }


@app.post("/api/v1/project/style")
async def update_project_style(
    data: StyleUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新项目的视觉风格（在大纲确认后、恢复工作流前调用）。

    The frontend selects style at step 3, after the project is already
    created (step 0) and outline approved (step 2). This endpoint lets
    the frontend attach the chosen style before resuming generation.
    """
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    if not state.get("outline_approved", False):
        raise HTTPException(status_code=409, detail="Outline must be approved before style selection")
    if not state.get("slide_blueprint_approved", False):
        raise HTTPException(status_code=409, detail="Slide blueprint must be approved before style selection")

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

    style_config_with_pref = {
        **style_config,
        "render_path_preference": render_pref,
    }
    theme_config_payload = {
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

    await redis_client.update_session(data.session_id, {
        "style_id": data.style_id,
        "style_config": style_config_with_pref,
        "theme_config": theme_config_payload,
        "slide_reviews": [],
        "slide_review_required": False,
        "slide_review_approved": False,
    })

    # Keep DB project theme in sync with runtime session state.
    from sqlalchemy import update
    await db.execute(
        update(Project)
        .where(Project.id == uuid.UUID(data.session_id))
        .values(theme=data.style_id)
    )
    await db.commit()

    return {
        "status": "style_updated",
        "style_id": data.style_id,
        "style_name": style_config.get("name_zh", ""),
    }


@app.get("/api/v1/workflow/slide-review/{session_id}")
async def get_slide_review(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get collaborative slide review package."""
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    return _build_slide_review_payload(state)


@app.post("/api/v1/workflow/slide-review/update")
async def update_slide_review(
    data: SlideReviewUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Patch a single slide draft before collaborative rendering."""
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)

    slides_data = _update_slide_for_page(list(state.get("slides_data", []) or []), data.page_number, data.slide_patch)
    render_plans = _update_slide_for_page(list(state.get("slide_render_plans", []) or []), data.page_number, data.render_patch)
    reviews = _merge_slide_review_status(
        state,
        data.page_number,
        accepted=False,
        status="revised",
        feedback=data.feedback,
        revision_increment=bool(data.slide_patch or data.render_patch),
    )
    approved = all(item.get("accepted", False) for item in reviews) if reviews else False
    updates = {
        "slides_data": slides_data,
        "slide_render_plans": render_plans,
        "slide_reviews": reviews,
        "slide_review_required": True,
        "slide_review_approved": approved,
        "current_status": "waiting_for_slide_review",
        "current_agent": "collaborative_reviewer",
    }
    await redis_client.update_session(data.session_id, updates)
    updated_state = {**state, **updates}
    return _build_slide_review_payload(updated_state)


@app.post("/api/v1/workflow/slide-review/accept")
async def accept_slide_review(
    data: SlideReviewAction,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a single slide during collaborative review."""
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)

    reviews = _merge_slide_review_status(
        state,
        data.page_number,
        accepted=True,
        status="accepted",
    )
    approved = bool(reviews) and all(item.get("accepted", False) for item in reviews)
    updates = {
        "slide_reviews": reviews,
        "slide_review_required": not approved,
        "slide_review_approved": approved,
        "current_status": "slide_review_approved" if approved else "waiting_for_slide_review",
        "current_agent": "collaborative_reviewer",
    }
    await redis_client.update_session(data.session_id, updates)
    updated_state = {**state, **updates}
    return _build_slide_review_payload(updated_state)


@app.post("/api/v1/workflow/slide-review/regenerate")
async def regenerate_slide_review(
    data: SlideReviewAction,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate a single slide draft using current blueprint and style."""
    await _verify_project_ownership(data.session_id, current_user, db)
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)

    slides_data, render_plans = await _regenerate_single_slide(state, data.page_number)
    reviews = _merge_slide_review_status(
        state,
        data.page_number,
        accepted=False,
        status="regenerated",
        revision_increment=True,
    )
    updates = {
        "slides_data": slides_data,
        "slide_render_plans": render_plans,
        "slide_reviews": reviews,
        "slide_review_required": True,
        "slide_review_approved": False,
        "current_status": "waiting_for_slide_review",
        "current_agent": "collaborative_reviewer",
    }
    await redis_client.update_session(data.session_id, updates)
    updated_state = {**state, **updates}
    return _build_slide_review_payload(updated_state)


@app.get("/api/v1/workflow/render/{session_id}")
@limiter.limit("10/minute")
async def render_after_collaborative_review(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user_sse),
    db: AsyncSession = Depends(get_db),
):
    """Continue to renderer after collaborative review is complete."""
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    if state.get("collaboration_mode") != "collaborative":
        raise HTTPException(status_code=409, detail="Render review endpoint is only for collaborative mode")
    if not state.get("slide_review_approved", False):
        raise HTTPException(status_code=409, detail="All slides must be accepted before rendering")

    return StreamingResponse(
        generate_render_only_sse_events(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/v1/workflow/resume/{session_id}")
@limiter.limit("10/minute")
async def resume_workflow(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user_sse),
    db: AsyncSession = Depends(get_db),
):
    """
    恢复工作流（用户确认大纲后）
    """
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    if state.get("outline_approved") and not state.get("slide_blueprint_approved", False):
        raise HTTPException(status_code=409, detail="Slide blueprint must be approved before resume")
    
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
    current_user: User = Depends(get_current_active_user_sse),
    db: AsyncSession = Depends(get_db),
):
    """下载生成的 PPTX 文件"""
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _hydrate_skill_runtime_state(state)
    
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
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目状态"""
    await _verify_project_ownership(session_id, current_user, db)
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "status": state.get("current_status", "unknown"),
        "current_agent": state.get("current_agent", ""),
        "skill_id": state.get("skill_id", "huashu-slides"),
        "collaboration_mode": state.get("collaboration_mode", "guided"),
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
                "pptx_path": p.pptx_path or "",
                "has_pptx": bool(p.pptx_path and Path(p.pptx_path).exists()),
                "created_at": p.created_at.isoformat(),
            }
            for p in projects
        ]
    }


@app.get("/api/v1/project/{session_id}/preview")
async def get_project_preview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return slide data for in-browser preview."""
    project = await _verify_project_ownership(session_id, current_user, db)

    # Try Redis first (fresh data)
    state = await redis_client.get_session(session_id)
    if state and state.get("slides_data"):
        slides_data = state.get("slides_data", [])
        return {
            "session_id": session_id,
            "user_intent": state.get("user_intent", project.user_intent),
            "slides": [
                {
                    "page_number": s.get("page_number", i + 1),
                    "title": s.get("title", ""),
                    "content": s.get("content", {}),
                    "speaker_notes": s.get("speaker_notes", ""),
                    "visual_type": s.get("visual_type", ""),
                }
                for i, s in enumerate(slides_data)
            ],
            "total": len(slides_data),
        }

    # Fallback to DB
    from sqlalchemy import select
    result = await db.execute(
        select(Slide)
        .where(Slide.project_id == uuid.UUID(session_id))
        .order_by(Slide.page_number)
    )
    db_slides = result.scalars().all()

    if not db_slides:
        raise HTTPException(status_code=404, detail="No slide data available")

    return {
        "session_id": session_id,
        "user_intent": project.user_intent,
        "slides": [
            {
                "page_number": s.page_number,
                "title": s.title or "",
                "content": s.content or {},
                "speaker_notes": s.speaker_notes or "",
                "visual_type": "",
            }
            for s in db_slides
        ],
        "total": len(db_slides),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
