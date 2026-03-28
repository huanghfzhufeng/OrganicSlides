# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OrganicSlides is an AI-powered presentation generator using a LangGraph multi-agent pipeline. Users enter a topic, the system researches, outlines, writes, and renders a professional PPTX through 5 specialized agents with human-in-the-loop checkpoints.

**Stack**: FastAPI + LangGraph (backend), React 19 + Vite + TailwindCSS 4 (frontend), PostgreSQL + Redis, Docker Compose.

**LLM**: MiniMax (via OpenAI-compatible `langchain_openai`, base URL must be `/v1` not `/anthropic`). **Image Gen**: Gemini via 12ai proxy (`image_size` uses `0.5K/1K/2K/4K`, not aspect ratios).

## Common Commands

### Local Development

```bash
# Prerequisites: .env file in project root (copy from .env.sample)

# Start infrastructure
docker compose up -d postgres redis

# Backend (from project root)
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
./scripts/start-local-backend.sh   # uvicorn on :18000

# Frontend (from project root)
./scripts/start-local-frontend.sh  # vite dev on :15173

# Or manually:
cd frontend && npm install && npm run dev
```

### Docker (full stack)

```bash
docker-compose up --build
```

### Tests

```bash
# Backend (pytest, run from project root)
.venv/bin/pytest tests/                          # all tests
.venv/bin/pytest tests/unit/                     # unit only
.venv/bin/pytest tests/unit/test_script_wrappers.py  # single file
.venv/bin/pytest tests/unit/test_script_wrappers.py::test_name -v  # single test

# Frontend (vitest, run from frontend/)
cd frontend
npm run test                    # watch mode
npm run test -- --run           # single run
npm run test -- StyleSelector   # filter by name
npm run test:coverage           # with coverage
npm run lint                    # eslint
```

### Build

```bash
cd frontend && npm run build    # tsc + vite build
```

## Architecture

### Agent Pipeline (backend/graph.py)

```
Input → researcher_local → [researcher_web] → planner → [wait_for_approval (HITL)]
  → writer → visual → render_preparation → [wait_for_slide_review (HITL, collaborative mode only)]
  → renderer → PPTX
```

Each agent is in `backend/agents/<name>/` with `agent.py` (logic), `prompts.py` (templates), `tools.py` (utilities). All agents return new state dicts — **never mutate `PresentationState`**.

**Conditional routing**:
- After local research: skips `researcher_web` unless `needs_web_search` is true.
- After planner: pauses at `wait_for_approval` for outline HITL.
- After `render_preparation`: pauses at `wait_for_slide_review` only when `collaboration_mode == "collaborative"`.

**Resume workflow** (`/workflow/resume`): starts from Writer, skipping research/planning.

### State (backend/state.py)

`PresentationState` is a TypedDict (`total=False`) flowing through the graph. Key field groups:

- **Session**: `session_id`, `user_intent`, `is_thesis_mode`, `skill_id`, `collaboration_mode` ("guided"|"collaborative"), `skill_packet`
- **Research**: `source_docs`, `search_results`, `needs_web_search`
- **Planning (HITL)**: `outline` (list of dicts with assertion titles), `outline_approved`, `slide_blueprint`, `slide_blueprint_approved`
- **Review (HITL)**: `slide_reviews`, `slide_review_required`, `slide_review_approved`
- **Content**: `slides_data` (writer+visual output per slide)
- **Style**: `style_id`, `style_config` (new system); `theme_config` (legacy fallback)
- **Rendering**: `slide_render_plans` (per-slide render instructions), `render_path` ("path_a"|"path_b"|"mixed"), `render_progress` (per-slide status for SSE)
- **Output**: `generated_assets`, `slide_files`, `pptx_path`
- **Flow control**: `current_status`, `current_agent`, `error`, `messages`

### Dual Rendering (backend/agents/renderer/paths.py)

- **Path A** (HTML→PPTX): `html2pptx_runner.js` via Node.js subprocess. For editorial/professional styles.
- **Path B** (AI Image→PPTX): Gemini image generation + python-pptx assembly. For illustrated styles.
- **Mixed**: Per-slide path selection via priority: slide `path_hint` > style default > `RENDER_PATH_DEFAULT` env var.

Script wrappers in `backend/services/script_wrappers/` bridge Python ↔ Node.js scripts in `huashu-slides/scripts/`.

### Style System

24 JSON configs in `backend/static/styles/` (tiers 1-3 + editorial). Registry in `backend/styles/registry.py`, recommender in `backend/styles/recommender.py`. Each style defines colors, typography, render paths, and a `base_style_prompt` for image generation.

### Frontend Wizard (frontend/src/App.tsx)

6 steps, state managed via top-level `useState()` in App.tsx, passed as props:

| Step | View | Purpose |
|------|------|---------|
| 0 | InputView | Enter topic or upload thesis document |
| 1 | ResearchView | SSE research progress |
| 2 | OutlineEditor | HITL outline approval/editing |
| 3 | BlueprintEditor | Per-slide blueprint review |
| 4 | StyleSelector → RenderPathSelector | Pick style, then rendering strategy |
| 5 | GenerationResultView | SSE generation progress + PPTX download |

SSE event types: `status`, `hitl`, `render_progress`, `complete`, `error`.

### Auth

JWT (HS256, 24h expiry) via `backend/auth/`. Endpoints: `/api/v1/auth/register`, `/login`, `/me`. Dependencies: `get_current_user()` (optional auth), `get_current_active_user()` (required auth).

### API (backend/main.py)

- `POST /api/v1/project/create` → `{session_id, status}` — accepts `{prompt, style_id?, style?}`
- `GET /api/v1/workflow/start/{session_id}` → SSE stream
- `GET /api/v1/workflow/resume/{session_id}` → SSE stream (post-outline, starts from Writer)
- `GET /api/v1/project/download/{session_id}` → PPTX file
- `GET /api/v1/styles/list` → style catalog
- `GET /api/v1/styles/{id}` → style detail
- `GET /api/v1/styles/samples/{id}` → style sample PNG
- `GET /api/v1/styles/recommend?intent=...` → recommendations

## Key Patterns

- **LLM response parsing**: `extract_json_payload()` and `strip_thinking_tags()` in `backend/agents/base.py` handle MiniMax's `<think>` tags and markdown fences.
- **SSE streaming**: FastAPI `StreamingResponse` + frontend `EventSource`. Always close EventSource in useEffect cleanup.
- **Assertion-Evidence slides**: Planner generates full-sentence titles (assertions), not topic labels. `OutlineSection.title` must be a sentence. `key_points` max 4 items.
- **Thesis mode**: `is_thesis_mode` flag enables academic-specific prompts and document chunking via `backend/services/document_parser.py`.
- **Collaboration modes**: "guided" (default, outline HITL only) vs "collaborative" (adds per-slide review HITL after render_preparation).
- **Skill runtime**: `backend/skills/runtime.py` provides `get_skill_runtime_packet()` which configures agent behavior per skill.

## Ports (non-standard to avoid conflicts)

| Service    | Port  |
|------------|-------|
| Backend    | 18000 |
| Frontend   | 15173 |
| PostgreSQL | 15432 |
| Redis      | 16379 |

## Language

The codebase mixes English (code, variable names) and Chinese (UI strings, prompts, style names, docs). LLM prompts are primarily in Chinese. Comments and code are in English.
