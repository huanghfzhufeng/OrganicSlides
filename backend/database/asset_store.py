"""Persistence helpers for object-stored asset metadata and cleanup."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from config import settings
from database.models import StoredAsset, WorkflowSession
from database.postgres import AsyncSessionLocal


async def _resolve_project_id(db, session_id: str):
    result = await db.execute(
        select(WorkflowSession).where(WorkflowSession.session_id == session_id)
    )
    workflow_session = result.scalar_one_or_none()
    if workflow_session is None:
        return None
    return workflow_session.project_id


async def record_stored_asset(
    session_id: str,
    asset_type: str,
    object_key: str,
    public_url: str,
    content_type: str,
    size_bytes: int,
    slide_number: Optional[int] = None,
) -> dict:
    """Persist object storage metadata for a generated asset."""
    async with AsyncSessionLocal() as db:
        project_id = await _resolve_project_id(db, session_id)
        expires_at = datetime.utcnow() + timedelta(hours=settings.ASSET_RETENTION_HOURS)

        asset = StoredAsset(
            project_id=project_id,
            session_id=session_id,
            asset_type=asset_type,
            object_key=object_key,
            public_url=public_url,
            content_type=content_type,
            size_bytes=size_bytes,
            slide_number=slide_number,
            expires_at=expires_at,
        )
        db.add(asset)
        await db.commit()

        return {
            "asset_id": str(asset.id),
            "object_key": asset.object_key,
            "asset_type": asset.asset_type,
        }


async def list_expired_assets(limit: int = 100) -> list[dict]:
    """Return expired active assets for cleanup workers."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StoredAsset)
            .where(
                StoredAsset.status == "active",
                StoredAsset.deleted_at.is_(None),
                StoredAsset.expires_at <= datetime.utcnow(),
            )
            .order_by(StoredAsset.expires_at.asc())
            .limit(limit)
        )
        assets = result.scalars().all()
        return [
            {
                "asset_id": str(asset.id),
                "session_id": asset.session_id,
                "asset_type": asset.asset_type,
                "object_key": asset.object_key,
                "slide_number": asset.slide_number,
            }
            for asset in assets
        ]


async def mark_asset_deleted(asset_id: str) -> Optional[dict]:
    """Mark an asset as deleted after successful cleanup."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StoredAsset).where(StoredAsset.id == uuid.UUID(asset_id))
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return None

        asset.status = "deleted"
        asset.deleted_at = datetime.utcnow()
        asset.error_message = None
        await db.commit()
        return {"asset_id": str(asset.id), "status": asset.status}


async def mark_asset_cleanup_failed(asset_id: str, error_message: str) -> Optional[dict]:
    """Persist cleanup failures without losing the asset metadata."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StoredAsset).where(StoredAsset.id == uuid.UUID(asset_id))
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return None

        asset.status = "cleanup_failed"
        asset.error_message = error_message[:500]
        await db.commit()
        return {"asset_id": str(asset.id), "status": asset.status}
