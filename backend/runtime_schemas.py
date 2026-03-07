"""Validated runtime schemas for research, style, slide, and render data."""

from __future__ import annotations

from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from rendering_policy import enforce_render_path_preference

RenderPath = Literal["path_a", "path_b"]
PathHint = Literal["path_a", "path_b", "auto"]
VisualType = Literal["illustration", "chart", "flow", "quote", "data", "cover"]


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validation_error_message(exc: ValidationError) -> str:
    """Collapse a Pydantic ValidationError into a compact message."""
    messages = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error.get("loc", ()))
        if path:
            messages.append(f"{path}: {error['msg']}")
        else:
            messages.append(error["msg"])
    return "; ".join(messages)


class RuntimeBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ResearchDocument(RuntimeBaseModel):
    chunk_id: str = ""
    content: str
    source: str = ""
    relevance_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunk_id", "source", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return _clean_str(value)

    @field_validator("content", mode="before")
    @classmethod
    def require_content(cls, value: Any) -> str:
        text = _clean_str(value)
        if not text:
            raise ValueError("content must not be empty")
        return text


class SearchResult(RuntimeBaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    domain: str = ""
    relevance_score: float | None = None

    @field_validator("title", "url", "snippet", "domain", mode="before")
    @classmethod
    def normalize_fields(cls, value: Any) -> str:
        return _clean_str(value)

    @model_validator(mode="after")
    def ensure_result_has_signal(self) -> "SearchResult":
        if not any((self.title, self.url, self.snippet)):
            raise ValueError("search result must contain title, url, or snippet")
        return self


class ResearchPacket(RuntimeBaseModel):
    query: str = ""
    source_docs: list[ResearchDocument] = Field(default_factory=list)
    search_results: list[SearchResult] = Field(default_factory=list)

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(cls, value: Any) -> str:
        return _clean_str(value)


class ColorPalette(RuntimeBaseModel):
    primary: str = "#5D7052"
    secondary: str = "#C18C5D"
    background: str = "#FFFFFF"
    text: str = "#1A1A1A"
    accent: str = "#0984E3"

    @field_validator("primary", "secondary", "background", "text", "accent", mode="before")
    @classmethod
    def normalize_colors(cls, value: Any) -> str:
        return _clean_str(value) or "#FFFFFF"


class TypographyConfig(RuntimeBaseModel):
    title_size: str = ""
    body_size: str = ""
    family: str = ""

    @field_validator("title_size", "body_size", "family", mode="before")
    @classmethod
    def normalize_fields(cls, value: Any) -> str:
        return _clean_str(value)


class StylePacket(RuntimeBaseModel):
    id: str
    style_id: str
    style: str
    name_zh: str = ""
    name_en: str = ""
    description: str = ""
    tier: int | str = 1
    colors: ColorPalette = Field(default_factory=ColorPalette)
    typography: TypographyConfig = Field(default_factory=TypographyConfig)
    use_cases: list[str] = Field(default_factory=list)
    key_principles: list[str] = Field(default_factory=list)
    render_paths: list[RenderPath] = Field(default_factory=lambda: ["path_a"])
    render_path_preference: PathHint = "auto"
    base_style_prompt: str = ""
    sample_image_path: str = ""
    sample_asset_path: str = ""
    sample_asset_exists: bool = False
    reference_sources: list[str] = Field(default_factory=list)
    reference_summary: str = ""
    gallery_excerpt: str = ""
    movement_excerpt: str = ""
    design_principles_excerpt: str = ""
    prompt_constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "id",
        "style_id",
        "style",
        "name_zh",
        "name_en",
        "description",
        "base_style_prompt",
        "sample_image_path",
        "sample_asset_path",
        "reference_summary",
        "gallery_excerpt",
        "movement_excerpt",
        "design_principles_excerpt",
        mode="before",
    )
    @classmethod
    def normalize_scalar_fields(cls, value: Any) -> str:
        return _clean_str(value)

    @field_validator("use_cases", "key_principles", "reference_sources", mode="before")
    @classmethod
    def normalize_use_cases(cls, value: Any) -> list[str]:
        if not value:
            return []
        return [_clean_str(item) for item in value if _clean_str(item)]

    @field_validator("render_paths", mode="before")
    @classmethod
    def normalize_render_paths(cls, value: Any) -> list[str]:
        if not value:
            return ["path_a"]
        if isinstance(value, str):
            return [value]
        normalized = []
        for item in value:
            text = _clean_str(item)
            if text and text not in normalized:
                normalized.append(text)
        return normalized or ["path_a"]

    @model_validator(mode="before")
    @classmethod
    def synchronize_style_ids(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        resolved_id = (
            _clean_str(data.get("style_id"))
            or _clean_str(data.get("id"))
            or _clean_str(data.get("style"))
            or "organic"
        )
        render_pref = _clean_str(data.get("render_path_preference")) or "auto"
        render_paths = data.get("render_paths") or []
        if render_pref in ("path_a", "path_b"):
            render_paths = [render_pref]

        return {
            **data,
            "id": resolved_id,
            "style_id": resolved_id,
            "style": resolved_id,
            "render_path_preference": render_pref,
            "render_paths": render_paths or ["path_a"],
        }

    @model_validator(mode="after")
    def ensure_preference_matches_paths(self) -> "StylePacket":
        if self.render_path_preference in ("path_a", "path_b"):
            self.render_paths = [self.render_path_preference]
        if not self.id:
            raise ValueError("style id must not be empty")
        return self


class SlideContent(RuntimeBaseModel):
    main_text: str | None = None
    bullet_points: list[str] = Field(default_factory=list)
    supporting_text: str | None = None

    @field_validator("main_text", "supporting_text", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        text = _clean_str(value)
        return text or None

    @field_validator("bullet_points", mode="before")
    @classmethod
    def normalize_bullets(cls, value: Any) -> list[str]:
        if not value:
            return []
        normalized = []
        for item in value:
            text = _clean_str(item)
            if text:
                normalized.append(text)
        return normalized[:4]

    @model_validator(mode="after")
    def validate_bullet_count(self) -> "SlideContent":
        if len(self.bullet_points) > 4:
            raise ValueError("bullet_points must not exceed 4 items")
        return self


class TextToRender(RuntimeBaseModel):
    title: str
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: Any) -> str:
        text = _clean_str(value)
        if not text:
            raise ValueError("title must not be empty")
        return text

    @field_validator("subtitle", mode="before")
    @classmethod
    def normalize_subtitle(cls, value: Any) -> str | None:
        text = _clean_str(value)
        return text or None

    @field_validator("bullets", mode="before")
    @classmethod
    def normalize_bullets(cls, value: Any) -> list[str]:
        if not value:
            return []
        return [_clean_str(item) for item in value if _clean_str(item)][:4]


class SlideSpec(RuntimeBaseModel):
    page_number: int = Field(ge=1)
    section_id: str
    title: str
    visual_type: VisualType = "illustration"
    path_hint: PathHint = "auto"
    layout_intent: str = "bullet_points"
    content: SlideContent = Field(default_factory=SlideContent)
    image_prompt: str | None = None
    text_to_render: TextToRender
    speaker_notes: str = ""

    @field_validator("section_id", "title", "layout_intent", "speaker_notes", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        return _clean_str(value)

    @field_validator("image_prompt", mode="before")
    @classmethod
    def normalize_image_prompt(cls, value: Any) -> str | None:
        text = _clean_str(value)
        return text or None

    @model_validator(mode="after")
    def ensure_required_prompt_fields(self) -> "SlideSpec":
        if not self.section_id:
            raise ValueError("section_id must not be empty")
        if not self.title:
            raise ValueError("title must not be empty")
        if (
            self.visual_type in {"illustration", "cover"}
            or self.path_hint == "path_b"
        ) and not self.image_prompt:
            raise ValueError("image_prompt is required for illustration, cover, or path_b slides")
        return self


class ColorSystem(RuntimeBaseModel):
    background: str = "#FFFFFF"
    text: str = "#1A1A1A"
    accent: str = "#0984E3"

    @field_validator("background", "text", "accent", mode="before")
    @classmethod
    def normalize_fields(cls, value: Any) -> str:
        return _clean_str(value) or "#FFFFFF"


class RenderPlan(RuntimeBaseModel):
    page_number: int = Field(ge=1)
    render_path: RenderPath
    layout_name: str = "bullet_list"
    title: str
    content: SlideContent = Field(default_factory=SlideContent)
    html_content: str | None = None
    image_prompt: str | None = None
    style_notes: str = ""
    color_system: ColorSystem = Field(default_factory=ColorSystem)

    @field_validator("layout_name", "title", "style_notes", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return _clean_str(value)

    @field_validator("html_content", "image_prompt", mode="before")
    @classmethod
    def normalize_optional_payloads(cls, value: Any) -> str | None:
        text = _clean_str(value)
        return text or None

    @model_validator(mode="after")
    def ensure_required_render_payload(self) -> "RenderPlan":
        if not self.title:
            raise ValueError("title must not be empty")
        if self.render_path == "path_a" and not self.html_content:
            raise ValueError("html_content is required for path_a render plans")
        if self.render_path == "path_b" and not self.image_prompt:
            raise ValueError("image_prompt is required for path_b render plans")
        return self


def build_research_packet(
    query: str,
    source_docs: Iterable[dict[str, Any]] | None,
    search_results: Iterable[dict[str, Any]] | None,
) -> ResearchPacket:
    return ResearchPacket.model_validate(
        {
            "query": query,
            "source_docs": list(source_docs or []),
            "search_results": list(search_results or []),
        }
    )


def build_style_packet(
    style_id: str = "",
    style_config: dict[str, Any] | None = None,
    theme_config: dict[str, Any] | None = None,
) -> StylePacket:
    source = dict(theme_config or {})
    source.update(style_config or {})
    if style_id:
        source["style_id"] = style_id
    from styles.style_packet_assembler import assemble_style_packet_context

    source.update(assemble_style_packet_context(source))
    return StylePacket.model_validate(source)


def validate_slide_specs(slides: Iterable[dict[str, Any]]) -> list[SlideSpec]:
    models: list[SlideSpec] = []
    for index, slide in enumerate(slides, start=1):
        payload = dict(slide)
        payload.setdefault("page_number", index)
        payload.setdefault("section_id", payload.get("section_id") or f"section_{index}")
        payload.setdefault("content", {})
        payload.setdefault("text_to_render", {})

        text_to_render = dict(payload.get("text_to_render") or {})
        content = dict(payload.get("content") or {})
        text_to_render.setdefault("title", payload.get("title"))
        text_to_render.setdefault("bullets", content.get("bullet_points", []))
        payload["text_to_render"] = text_to_render

        models.append(SlideSpec.model_validate(payload))
    return models


def validate_render_plans(
    plans: Iterable[dict[str, Any]],
    style_packet: StylePacket | dict[str, Any] | None = None,
) -> list[RenderPlan]:
    resolved_style: StylePacket | None = None
    if style_packet is not None:
        resolved_style = (
            style_packet
            if isinstance(style_packet, StylePacket)
            else build_style_packet(style_config=style_packet)
        )

    models: list[RenderPlan] = []
    for index, plan in enumerate(plans, start=1):
        payload = dict(plan)
        payload.setdefault("page_number", index)
        payload.setdefault("content", {})
        if resolved_style is not None:
            payload["render_path"] = enforce_render_path_preference(
                payload.get("render_path", "path_a"),
                serialize_models(resolved_style),
            )
            color_system = dict(payload.get("color_system") or {})
            payload["color_system"] = {
                "background": color_system.get("background", resolved_style.colors.background),
                "text": color_system.get("text", resolved_style.colors.text),
                "accent": color_system.get("accent", resolved_style.colors.accent),
            }
        models.append(RenderPlan.model_validate(payload))
    return models


def serialize_models(models: BaseModel | list[BaseModel]) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(models, list):
        return [model.model_dump(mode="python") for model in models]
    return models.model_dump(mode="python")
