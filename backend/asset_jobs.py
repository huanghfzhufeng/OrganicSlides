"""Background jobs for asset metadata maintenance and retention cleanup."""

from __future__ import annotations

import asyncio

from config import settings
from database.asset_store import (
    list_expired_assets,
    mark_asset_cleanup_failed,
    mark_asset_deleted,
)
from services.object_storage import get_object_storage


async def cleanup_expired_assets(stop_event: asyncio.Event | None = None) -> None:
    """Delete expired object-stored assets and mark metadata rows accordingly."""
    while stop_event is None or not stop_event.is_set():
        expired_assets = await list_expired_assets(settings.ASSET_CLEANUP_BATCH_SIZE)
        for asset in expired_assets:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda key=asset["object_key"]: get_object_storage().delete_object(key),
                )
                await mark_asset_deleted(asset["asset_id"])
            except FileNotFoundError:
                await mark_asset_deleted(asset["asset_id"])
            except Exception as exc:
                await mark_asset_cleanup_failed(asset["asset_id"], str(exc))

        await asyncio.sleep(settings.ASSET_CLEANUP_INTERVAL_SECONDS)
