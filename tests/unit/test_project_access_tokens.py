"""Unit tests for project access tokens."""

from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from auth.service import AuthService


@pytest.mark.unit
class TestProjectAccessTokens:
    def test_project_access_token_round_trip(self):
        token = AuthService.create_project_access_token("session-123")

        decoded = AuthService.decode_project_access_token(token.access_token)

        assert decoded == "session-123"

    def test_user_access_token_is_not_valid_project_access_token(self):
        token = AuthService.create_access_token("00000000-0000-0000-0000-000000000001")

        decoded = AuthService.decode_project_access_token(token.access_token)

        assert decoded is None
