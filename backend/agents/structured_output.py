"""Helpers for parsing and repairing structured LLM outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import HumanMessage

from agents.base import create_system_message


Validator = Callable[[Any], tuple[bool, str]]
Parser = Callable[[str], Any]


@dataclass
class StructuredOutputResult:
    value: Any | None
    attempts: list[dict]
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def repaired(self) -> bool:
        return any(
            attempt.get("stage") == "repair" and attempt.get("success")
            for attempt in self.attempts
        )


def extract_json_payload(content: str) -> str:
    """Extract the JSON payload from a raw LLM response."""
    if "```json" in content:
        return content.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in content:
        return content.split("```", 1)[1].split("```", 1)[0].strip()

    # Try to recover the first JSON object/array if the model wrapped it in prose.
    match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()


async def resolve_structured_output(
    *,
    llm: Any,
    raw_content: str,
    parser: Parser,
    validator: Validator,
    repair_system_prompt: str,
    repair_user_template: str,
    repair_context: dict[str, Any],
) -> StructuredOutputResult:
    """Parse structured output once, then try a single repair pass if needed."""
    attempts: list[dict] = []

    parsed, error = _parse_and_validate(raw_content, parser, validator)
    attempts.append(_build_attempt("initial", error))
    if error is None:
        return StructuredOutputResult(value=parsed, attempts=attempts)

    try:
        repair_message = repair_user_template.format(
            raw_output=raw_content,
            failure_reason=error,
            **repair_context,
        )
        repaired_response = await llm.ainvoke(
            [
                create_system_message(repair_system_prompt),
                HumanMessage(content=repair_message),
            ]
        )
    except Exception as exc:  # pragma: no cover - defensive branch
        repair_error = f"repair invocation failed: {exc}"
        attempts.append(_build_attempt("repair", repair_error))
        return StructuredOutputResult(value=None, attempts=attempts, error=repair_error)

    repaired_value, repair_error = _parse_and_validate(
        repaired_response.content,
        parser,
        validator,
    )
    attempts.append(_build_attempt("repair", repair_error))
    if repair_error is None:
        return StructuredOutputResult(value=repaired_value, attempts=attempts)

    return StructuredOutputResult(value=None, attempts=attempts, error=repair_error)


def _parse_and_validate(
    content: str,
    parser: Parser,
    validator: Validator,
) -> tuple[Any | None, str | None]:
    try:
        parsed = parser(content)
    except Exception as exc:
        return None, f"parse failed: {exc}"

    is_valid, message = validator(parsed)
    if not is_valid:
        return None, f"validation failed: {message}"
    return parsed, None


def _build_attempt(stage: str, error: str | None) -> dict:
    if error is None:
        return {
            "stage": stage,
            "success": True,
            "error": None,
        }
    return {
        "stage": stage,
        "success": False,
        "error": error,
    }
