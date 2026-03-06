# OrganicSlides x huashu-slides - Integration TODO

## Phase 1: Style System Foundation

### 1.1 Style Resources (skills-engineer)
- [x] Create `backend/static/styles/` directory structure
- [x] Create JSON config for each of 24 styles (18 illustration + 6 editorial)
- [x] Copy style sample images to `backend/static/styles/samples/`
- [x] Verify huashu-slides script environments (uv, node, python-pptx, pptxgenjs, playwright)
- [x] Write `docs/setup-huashu-deps.md`

### 1.2 Style API (backend-engineer)
- [x] Extend `backend/state.py` theme_config for style_id + full params
- [x] Create `backend/styles/registry.py` - StyleRegistry class
- [x] Create `backend/styles/recommender.py` - StyleRecommender
- [x] Add `GET /api/v1/styles` endpoint
- [x] Add `GET /api/v1/styles/{id}/sample` endpoint
- [x] Add `GET /api/v1/styles/recommend` endpoint
- [x] Add `POST /api/v1/project/style` endpoint (style selection after creation)
- [x] Modify `POST /api/v1/project/create` for style_id
- [x] Add GEMINI_API_KEY, SKILL_SCRIPTS_DIR, etc. to config.py

### 1.3 Style Gallery UI (frontend-engineer)
- [x] Add getStyles(), getStyleSample(), getStyleRecommendations() to api/client.ts
- [x] Rewrite StyleSelector.tsx with tier grouping, real previews, recommendations
- [x] Modify App.tsx to pass style_id to createProject
- [x] Add Style type definition

### 1.4 Prompt Redesign Doc (agent-architect)
- [x] Read all huashu-slides reference files
- [x] Read all current agent prompts
- [x] Write `docs/agent-prompt-redesign.md` with input/output schema changes

### 1.5 Test Framework (functional-tester)
- [x] Set up pytest with tests/unit, tests/integration, tests/e2e
- [x] Write style JSON data validation tests (14 tests)
- [x] Write style API endpoint tests (16 tests)
- [x] Write StyleSelector component test

### 1.6 Baseline Evaluation (agent-tester)
- [x] Read all agent code and prompts
- [x] Create `tests/agent_eval/` evaluation framework
- [x] Define 3 test themes
- [x] Write `docs/agent-baseline-report.md`

---

## Phase 2: Agent Prompts + Rendering Pipeline

### 2.1 Agent Prompt Refactor (agent-architect)
- [x] Planner: assertion-evidence titles, visual_type field, ≤4 bullets
- [x] Writer: image_prompt field, path_hint field, content density rules
- [x] Visual: design decision maker role, render_path output
- [x] Researcher: real web search (DuckDuckGo), knowledge base search
- [x] Update validation tools for new fields

### 2.2 Rendering Pipeline (backend-engineer)
- [x] Create `backend/agents/renderer/paths.py` (path_a, path_b routing)
- [x] Create `backend/services/image_generator.py` (Gemini wrapper)
- [x] Create `backend/services/pptx_assembler.py` (combine paths)
- [x] Modify `backend/agents/renderer/agent.py` for dual path + parallel rendering
- [x] Add SSE render_progress events

### 2.3 LangGraph Adjustments (agent-architect)
- [x] Add render_preparation node after Visual agent
- [x] Support parallel rendering via asyncio.gather
- [x] Add render_progress SSE event type

### 2.4 Script Wrappers (skills-engineer)
- [x] Create `backend/services/script_wrappers/image_gen.py`
- [x] Create `backend/services/script_wrappers/html_converter.py`
- [x] Create `backend/services/script_wrappers/slide_creator.py`
- [x] Add parameter validation and error handling to each

### 2.5 Phase 2 Tests (functional-tester)
- [x] Unit tests for image_generator.py (mock Gemini)
- [x] Unit tests for script wrappers (33 tests)
- [x] Integration tests for pptx_assembler.py (12 tests)
- [x] Integration tests for render paths
- [x] SSE event format tests

### 2.6 Prompt Evaluation (agent-tester)
- [x] Compare new vs old prompts on 3 test themes
- [x] Verify visual_type, image_prompt, path_hint fields
- [x] Write `docs/agent-improvement-report.md`

---

## Phase 3: Full Integration + Polish

### 3.1 Generation UI Upgrade (frontend-engineer)
- [x] ResearchView: real stats from SSE
- [x] GenerationResultView: per-slide progress cards, path labels, thumbnails
- [x] Add render path selection UI (RenderPathSelector.tsx)
- [x] Handle render_progress SSE events

### 3.2 API Completion (backend-engineer)
- [x] Complete SSE event structure with real data
- [x] Add per-slide and overall timeouts (asyncio.wait_for + semaphore)
- [x] Optimize parallel rendering (semaphore limit 3, streaming results)
- [x] Add render_path_preference to project creation
- [x] Add thumbnail generation (320x180 JPEG)

### 3.3 Error Handling (agent-architect)
- [x] Implement fallback: Path B → Path A → basic python-pptx → error
- [x] Add retry logic (1 retry on transient errors)
- [x] Agent-level fallbacks (Visual fails → default paths)
- [x] Enrich error SSE events

### 3.4 Documentation (skills-engineer)
- [x] Write `docs/user-guide.md`
- [x] Update README.md
- [x] Write `docs/style-selection-guide.md`

### 3.5 E2E Tests (functional-tester)
- [ ] Full workflow test (input → style → generate → download) — 19 test stubs written
- [ ] Test all 3 render paths — stubs ready
- [ ] Error scenario tests — stubs ready
- [ ] SSE event flow tests — stubs ready

### 3.6 Quality Verification (agent-tester)
- [ ] Test 5 themes x 3 styles = 15 combinations — framework ready
- [ ] Verify PPTX compatibility
- [ ] Write `docs/final-quality-report.md`

---

## Dependency Chain

```
Phase 1: 1.1 → 1.2 → 1.3 (sequential)           ✅ COMPLETE
          1.4, 1.5, 1.6 (parallel, independent)   ✅ COMPLETE

Phase 2: 2.1 ← 1.4 (prompt doc)                   ✅ COMPLETE
          2.2 ← 1.2 (style system)                 ✅ COMPLETE
          2.3 ← 2.1 (prompts done)                 ✅ COMPLETE
          2.4 ← 1.1 (resources ready)              ✅ COMPLETE
          2.5 ← 2.2 + 2.4                          ✅ COMPLETE
          2.6 ← 2.1                                ✅ COMPLETE

Phase 3: 3.1 ← 2.2 + 2.3                          ✅ COMPLETE
          3.2 ← 2.2                                ✅ COMPLETE
          3.3 ← 2.1 + 2.3                          ✅ COMPLETE
          3.4 ← 2.4                                ✅ COMPLETE
          3.5 ← 3.1 + 3.2                          ⏳ STUBS READY
          3.6 ← 3.3                                ⏳ FRAMEWORK READY
```

## Summary

- **16/18 tasks COMPLETE** (all implementation tasks)
- **2/18 tasks PENDING** (finalization: E2E tests + quality verification — prep work done)
- **94 tests written** across unit, integration, and E2E layers
- **24 styles** integrated (18 illustration + 6 editorial)
- **Dual rendering paths** (Path A: HTML→PPTX, Path B: AI Image→PPTX)
- **4 bugs fixed** by lead during integration (recommender type error, style timing gap, render_path_preference, fallback parameter type)
