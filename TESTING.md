# Testing Framework

This document describes the test surface that currently exists in OrganicSlides and the most useful ways to run it.

## Test Map

### Backend Unit Tests (`tests/unit/`)

The unit suite is no longer limited to style JSON validation. It now covers multiple backend seams, including:

- style data and render-path validation
- workflow state helpers and runtime schemas
- project preview and access-token helpers
- object storage and stored-asset cleanup jobs
- renderer preflight checks and script-wrapper behavior
- planner, writer, and visual quality/style packet helpers

Representative files:

- `tests/unit/test_style_data.py`
- `tests/unit/test_render_path_preference.py`
- `tests/unit/test_script_wrappers.py`
- `tests/unit/test_asset_cleanup.py`
- `tests/unit/test_workflow_state_helpers.py`

### Backend Integration Tests (`tests/integration/`)

The integration suite covers more than the styles API:

- `tests/integration/test_styles_api.py`
  Exercises API behavior with patched runtime dependencies.
- `tests/integration/test_rendering_pipeline.py`
  Covers Path A / Path B wrapper integration and PPTX assembly flows.

### Backend E2E Scaffolds (`tests/e2e/`)

`tests/e2e/test_full_workflow.py` exists today. Per `tests/e2e/README.md`, these tests are scaffold-style end-to-end checks built around mock SSE event data so the full workflow contract can be exercised before every dependency is fully live.

### Agent Evaluation Harness (`tests/agent_eval/`)

This repo also includes evaluation helpers for theme and output comparison work:

- `tests/agent_eval/evaluation_runner.py`
- `tests/agent_eval/evaluator.py`
- `tests/agent_eval/final_quality_tester.py`
- `tests/agent_eval/test_themes.py`

These are not part of the day-to-day frontend/backend smoke path, but they are part of the repo's broader quality toolset.

### Frontend Tests (`frontend/src/__tests__/`)

Frontend tests currently use Vitest + React Testing Library. The committed suite is still small and focused:

- `frontend/src/__tests__/StyleSelector.test.tsx`
- `frontend/src/__tests__/setup.ts`

## Running Tests

### Backend Setup

```bash
pip3 install --break-system-packages -r tests/requirements-test.txt
pip3 install --break-system-packages -r backend/requirements.txt
```

If you use the project virtualenv, substitute the repo-local interpreter, for example:

```bash
.venv/bin/pytest tests/unit -q
```

### Backend Commands

Run the full backend suite:

```bash
pytest tests/ -v
```

Run only unit tests:

```bash
pytest tests/unit/ -v
```

Run only integration tests:

```bash
pytest tests/integration/ -v
```

Run only E2E scaffolds:

```bash
pytest tests/e2e/ -v
```

Run coverage:

```bash
pytest tests/ --cov=backend --cov-report=html
```

### Frontend Commands

```bash
cd frontend
npm install
npm test
```

Run once in CI-style mode:

```bash
cd frontend
npm test -- --run
```

Run the Vitest UI:

```bash
cd frontend
npm run test:ui
```

Run frontend coverage:

```bash
cd frontend
npm run test:coverage
```

### Fast Verification Commands

These are the most useful cleanup/refactor gates:

```bash
cd frontend && npm run build
cd frontend && npm test -- --run
pytest tests/unit -q
pytest tests/integration -q
```

## Current Test Structure

```text
tests/
├── unit/            # backend units and helper contracts
├── integration/     # API + rendering pipeline integration
├── e2e/             # scaffold workflow tests with mocked SSE/event flows
└── agent_eval/      # evaluation harnesses and comparison tooling

frontend/src/__tests__/
├── setup.ts
└── StyleSelector.test.tsx
```

## Notes

- `pytest.ini` defines `unit`, `integration`, and `e2e` markers.
- Frontend tests run in `jsdom` and use React Testing Library.
- The E2E suite is not "future only" anymore, but it is still scaffold-oriented rather than a browser-driven production E2E harness.
- Integration tests mix `TestClient`, temp files, and mocked subprocess/runtime dependencies depending on the suite.
