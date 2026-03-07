"""Unit tests for environment-specific settings validation."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from config import Settings


@pytest.mark.unit
class TestSettingsEnvironments:
    def test_development_allows_default_local_settings(self):
        settings = Settings(APP_ENV="development", DEBUG=True, OBJECT_STORAGE_BACKEND="local")

        assert settings.APP_ENV == "development"
        assert settings.DEBUG is True

    def test_staging_rejects_debug_true(self):
        with pytest.raises(ValueError, match="DEBUG must be false"):
            Settings(
                APP_ENV="staging",
                DEBUG=True,
                JWT_SECRET_KEY="staging-secret",
                OBJECT_STORAGE_BACKEND="s3",
            )

    def test_production_requires_non_default_secret(self):
        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be overridden"):
            Settings(
                APP_ENV="production",
                DEBUG=False,
                OBJECT_STORAGE_BACKEND="s3",
            )

    def test_production_requires_non_local_object_storage(self):
        with pytest.raises(ValueError, match="OBJECT_STORAGE_BACKEND must not be 'local'"):
            Settings(
                APP_ENV="production",
                DEBUG=False,
                JWT_SECRET_KEY="prod-secret",
                OBJECT_STORAGE_BACKEND="local",
            )
