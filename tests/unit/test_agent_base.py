"""Tests for shared agent helpers."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.base import strip_thinking_tags


def test_strip_thinking_tags_from_plain_string():
    content = "<think>internal reasoning</think>\n\nOK"
    assert strip_thinking_tags(content) == "OK"


def test_strip_thinking_tags_from_content_blocks():
    content = [
        {"type": "text", "text": "<think>hidden</think>"},
        {"type": "text", "text": "```json\n{\"ok\": true}\n```"},
    ]
    assert strip_thinking_tags(content) == "```json\n{\"ok\": true}\n```"


def test_strip_thinking_tags_handles_none():
    assert strip_thinking_tags(None) == ""
