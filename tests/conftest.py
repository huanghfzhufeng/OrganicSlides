"""Shared test configuration and fixtures"""

import asyncio
import pytest
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get_session = AsyncMock(return_value={})
    redis.set_session = AsyncMock()
    redis.update_session = AsyncMock()
    redis.push_log = AsyncMock()
    redis.connect = AsyncMock()
    redis.disconnect = AsyncMock()
    return redis


@pytest.fixture
async def test_client():
    """FastAPI test client - use this for integration tests"""
    from main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def styles_path():
    """Path to styles directory"""
    return Path(__file__).parent.parent / "backend" / "static" / "styles"


@pytest.fixture
def sample_style_json():
    """Sample style JSON for testing"""
    return {
        "id": "test-style",
        "name_zh": "测试风格",
        "name_en": "Test Style",
        "tier": 1,
        "description": "A test style for unit testing",
        "colors": {
            "primary": "#FF0000",
            "secondary": "#00FF00",
            "background": "#FFFFFF",
            "text": "#000000",
            "accent": "#0000FF",
            "additional": ["#FFFF00"]
        },
        "typography": {
            "title_size": "32pt",
            "body_size": "16pt",
            "family": "System default"
        },
        "use_cases": ["education", "business"],
        "sample_image_path": "/static/styles/samples/test-sample.png",
        "render_paths": ["path_a", "path_b"],
        "base_style_prompt": "A test prompt for style generation",
        "key_principles": ["test principle 1", "test principle 2"]
    }


@pytest.fixture
def invalid_style_json():
    """Invalid style JSON (missing required fields)"""
    return {
        "id": "invalid-style",
        "name_zh": "无效风格"
        # Missing other required fields
    }
