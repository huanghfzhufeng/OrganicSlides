"""
MAS-PPT 多智能体演示文稿生成系统
FastAPI 后端服务 - 集成数据库和认证
"""

import asyncio
import uuid
import json
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from state import PresentationState, create_initial_state
from graph import get_main_app, get_resume_app
from database.postgres import get_db, init_db, close_db
from database.redis_client import redis_client
from database.models import User, Project
from auth import auth_router, get_current_user, get_current_active_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 MAS-PPT 系统启动中...")
    
    # 连接 Redis
    await redis_client.connect()
    print("✅ Redis 连接成功")
    
    # 初始化数据库
    await init_db()
    print("✅ PostgreSQL 数据库初始化完成")
    
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

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册认证路由
app.include_router(auth_router)


# ==================== 请求/响应模型 ====================

class ProjectCreate(BaseModel):
    prompt: str
    style: str = "organic"


class OutlineUpdate(BaseModel):
    session_id: str
    outline: List[Dict[str, Any]]


class WorkflowResume(BaseModel):
    session_id: str


# ==================== SSE 流式响应 ====================

async def generate_sse_events(session_id: str, state: PresentationState):
    """生成 SSE 事件流"""
    main_app = get_main_app()
    
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
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                # 更新 Redis 缓存
                await redis_client.update_session(session_id, node_output)
                await redis_client.push_log(session_id, data)
                
                await asyncio.sleep(0.1)
        
        # 获取最终状态
        final_state = await redis_client.get_session(session_id) or {}
        
        if final_state.get("current_status") == "waiting_for_outline_approval":
            yield f"data: {json.dumps({'type': 'hitl', 'status': 'waiting_for_approval', 'outline': final_state.get('outline', [])}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'complete', 'status': 'done'}, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


async def generate_resume_sse_events(session_id: str):
    """生成恢复阶段的 SSE 事件流"""
    resume_app = get_resume_app()
    state = await redis_client.get_session(session_id)
    
    if not state:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'}, ensure_ascii=False)}\n\n"
        return
    
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
                
                data = {
                    "type": "status",
                    "agent": agent,
                    "status": status,
                    "message": messages[-1]["content"] if messages else ""
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                await redis_client.update_session(session_id, node_output)
                await redis_client.push_log(session_id, data)
                await asyncio.sleep(0.1)
        
        final_state = await redis_client.get_session(session_id) or {}
        pptx_path = final_state.get("pptx_path", "")
        
        yield f"data: {json.dumps({'type': 'complete', 'status': 'done', 'pptx_path': pptx_path}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """健康检查"""
    return {"message": "MAS-PPT API is running", "version": "1.0.0"}


@app.post("/api/v1/project/create")
async def create_project(
    project: ProjectCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建项目并启动工作流
    """
    session_id = str(uuid.uuid4())
    
    # 创建初始状态
    state = create_initial_state(
        session_id=session_id,
        user_intent=project.prompt,
        theme=project.style
    )
    
    # 保存到 Redis
    await redis_client.set_session(session_id, state)
    
    # 如果用户已登录，保存到数据库
    if current_user:
        db_project = Project(
            id=uuid.UUID(session_id),
            user_id=current_user.id,
            user_intent=project.prompt,
            theme=project.style,
            status="created"
        )
        db.add(db_project)
        await db.commit()
    
    return {"session_id": session_id, "status": "created"}


@app.get("/api/v1/workflow/start/{session_id}")
async def start_workflow(session_id: str):
    """
    启动工作流（SSE 流式响应）
    """
    state = await redis_client.get_session(session_id)
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
async def get_outline(session_id: str):
    """获取生成的大纲"""
    state = await redis_client.get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "outline": state.get("outline", []),
        "status": state.get("current_status", "unknown")
    }


@app.post("/api/v1/workflow/outline/update")
async def update_outline(
    data: OutlineUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    HITL 接口：用户修改大纲
    """
    state = await redis_client.get_session(data.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 更新 Redis
    await redis_client.update_session(data.session_id, {
        "outline": data.outline,
        "outline_approved": True
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


@app.get("/api/v1/workflow/resume/{session_id}")
async def resume_workflow(session_id: str):
    """
    恢复工作流（用户确认大纲后）
    """
    state = await redis_client.get_session(session_id)
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
async def download_pptx(session_id: str):
    """下载生成的 PPTX 文件"""
    state = await redis_client.get_session(session_id)
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
async def get_project_status(session_id: str):
    """获取项目状态"""
    state = await redis_client.get_session(session_id)
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
