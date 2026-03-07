# OrganicSlides Production TODO

## 1. Workflow Rules

This file is the execution tracker.

Rules:

1. Each checkbox item is one requirement.
2. Each requirement is implemented on its own branch.
3. Each requirement is submitted as its own PR.
4. Each requirement is merged to `main` before the next dependent requirement is checked.
5. A checkbox is checked only after merge to `main`.

Branch template:

- `codex/<requirement-id>-<short-name>`

Examples:

- `codex/req-001-build-baseline`
- `codex/req-002-ci-branch-protection`
- `codex/req-003-release-templates`
- `codex/req-014-style-packet`

## 2. Phase 0: Governance and Baseline

- [x] `REQ-001` Repair frontend build, frontend tests, backend tests, and type errors.
- [x] `REQ-002` Define required CI checks and enforce branch protection for `main`.
  Validation completed on `2026-03-07` with protected checks `frontend-build`, `frontend-tests`, and `backend-tests`.
- [x] `REQ-003` Add PR template, rollback template, and release checklist template.
  Added `.github/pull_request_template.md`, `docs/templates/rollback-template.md`, and `docs/templates/release-checklist-template.md` on `2026-03-07`.

## 3. Phase 1: Correctness and Runtime Stability

- [x] `REQ-004` Replace `MemorySaver` and process-local workflow state with durable persistence.
  Validation completed on `2026-03-07` with durable PostgreSQL-backed workflow state, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-005` Standardize project, revision, job, and event persistence in PostgreSQL.
  Validation completed on `2026-03-07` with PostgreSQL-backed project revisions, generation jobs, job events, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-006` Remove Redis-as-source-of-truth session assumptions.
  Validation completed on `2026-03-07` with PostgreSQL-only workflow state reads, optional Redis startup, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-007` Unify auth and authorization behavior across API, SSE, preview, and download flows.
  Validation completed on `2026-03-07` with project access tokens across API, SSE, and downloads, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-008` Enforce render path preference through the entire generation pipeline.
  Validation completed on `2026-03-07` with end-to-end render path enforcement in style state, Visual, RenderPrep, and Renderer, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-009` Replace silent generic fallbacks with explicit repair, retry, or failure states.
  Validation completed on `2026-03-07` with explicit repair/failure handling in Planner, Writer, Visual, workflow error routing, SSE failure events, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.

## 4. Phase 2: Generation Quality Core

- [x] `REQ-010` Introduce validated runtime schemas for `ResearchPacket`, `StylePacket`, `SlideSpec`, and `RenderPlan`.
  Validation completed on `2026-03-07` with Pydantic runtime schemas wired into state initialization, Researcher, Planner, Writer, Visual, RenderPrep, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-011` Build the `StylePacket` assembler from style JSON, references, prompt constraints, and sample assets.
  Validation completed on `2026-03-07` with assembled StylePacket references/constraints/assets, tracked huashu reference sources, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-012` Upgrade researcher retrieval so `huashu-slides` references are actually retrievable for Chinese and English prompts.
  Validation completed on `2026-03-07` with bilingual query expansion for huashu references and uploaded docs, `tests/unit/test_reference_retrieval.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-013` Inject `StylePacket` into planner prompts and validation.
  Validation completed on `2026-03-07` with StylePacket-driven planner context, style-aware outline validation/repair, `tests/unit/test_planner_style_packet.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-014` Inject `StylePacket` into writer prompts and validation.
  Validation completed on `2026-03-07` with StylePacket-driven writer context, path-aware writer validation, `tests/unit/test_writer_style_packet.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-015` Inject `StylePacket` into visual prompts and validation.
  Validation completed on `2026-03-07` with StylePacket-driven visual context, style-aware render-path and Path B prompt validation, `tests/unit/test_visual_style_packet.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-016` Add writer quality gate and repair loop.
  Validation completed on `2026-03-07` with writer quality gates for outline-title preservation, bullet density, Path B render-title limits, automatic repair via `tests/unit/test_writer_quality_gate.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-017` Add visual quality gate and repair loop.
  Validation completed on `2026-03-07` with visual quality gates for render-path policy, Path A HTML integrity, Path B prompt depth, automatic repair via `tests/unit/test_visual_quality_gate.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-018` Add renderer preflight validation for assets, prompts, HTML, and routing.
  Validation completed on `2026-03-07` with renderer preflight checks in render preparation and renderer dispatch, covering route consistency, local asset existence, HTML inputs, prompt readiness via `tests/unit/test_renderer_preflight.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.

## 5. Phase 3: Service Architecture and Scalability

- [x] `REQ-019` Split API service and worker service.
  Validation completed on `2026-03-07` with a dedicated `worker_app`, API-to-worker dispatch, persisted SSE event streaming, updated `docker-compose` topology, `tests/unit/test_generation_tracking.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-020` Add queue-based job dispatch and worker consumption.
  Validation completed on `2026-03-07` with database-backed job enqueueing, worker queue polling/claiming, updated worker topology/docs, `tests/unit/test_generation_tracking.py`, `tests/integration/test_styles_api.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-021` Make jobs resumable and idempotent.
  Validation completed on `2026-03-07` with stale job reclamation, heartbeat refresh, idempotent job reuse for completed workflow phases, fixed HITL SSE termination, `tests/unit/test_generation_tracking.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-022` Move generated artifacts, thumbnails, and previews to object storage.
  Validation completed on `2026-03-07` with object storage abstraction, renderer uploads for presentations/slides/thumbnails, asset proxy API, MinIO compose topology, `tests/unit/test_object_storage.py`, `tests/integration/test_styles_api.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-023` Add asset retention, cleanup, and metadata jobs.
  Validation completed on `2026-03-07` with stored asset metadata, worker cleanup loop for expired objects, retention settings, `tests/unit/test_asset_cleanup.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-024` Add staging and production environment separation.
  Validation completed on `2026-03-07` with environment-specific settings validation, staging/production env templates, standalone compose files, production frontend image, `tests/unit/test_settings_envs.py`, compose config checks, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.

## 6. Phase 4: Product and User Experience

- [x] `REQ-025` Add project revision history and restore capability.
  Validation completed on `2026-03-07` with project revision history and restore APIs, active-job restore guards, frontend revision client methods, `tests/integration/test_styles_api.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-026` Add transparent user-facing failure reasons and retry actions.
  Validation completed on `2026-03-07` with structured worker failure payloads, failure summary and retry APIs, in-app retry actions for research/generation flows, `tests/integration/test_styles_api.py`, `tests/unit/test_generation_tracking.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [x] `REQ-027` Improve preview quality and history consistency.
  Validation completed on `2026-03-07` with persisted project preview assembly, preview hydration API, revision preview summaries, corrected render-progress event fields, `tests/integration/test_styles_api.py`, `tests/unit/test_asset_cleanup.py`, `tests/unit/test_project_preview.py`, `pytest -q`, `frontend/npm run build`, and `frontend/npm test -- --run`.
- [ ] `REQ-028` Add operator/admin tooling for failed jobs and support actions.

## 7. Phase 5: Security, Cost Control, and Operations

- [ ] `REQ-029` Add rate limiting and abuse protection policies.
- [ ] `REQ-030` Add quota and concurrency controls per user.
- [ ] `REQ-031` Add audit logs for access, generation, preview, and download operations.
- [ ] `REQ-032` Add monitoring, tracing, metrics, logs, and alert rules.
- [ ] `REQ-033` Add backup, restore, and migration verification workflows.

## 8. Phase 6: Test and Release Readiness

- [ ] `REQ-034` Build the complete static, unit, contract, and integration CI pipeline.
- [ ] `REQ-035` Build the complete end-to-end test suite for the primary user flows.
- [ ] `REQ-036` Build the golden quality regression suite.
- [ ] `REQ-037` Run load, restart recovery, and timeout/cancellation validation.
- [ ] `REQ-038` Run security verification and release review.
- [ ] `REQ-039` Complete staging canary validation.
- [ ] `REQ-040` Approve public launch on `main`.

## 9. Per-Requirement Completion Checklist

Use this checklist before marking any item complete:

- [ ] code implemented
- [ ] tests added or updated
- [ ] CI green
- [ ] docs updated
- [ ] rollback path written in PR
- [ ] PR approved
- [ ] PR merged to `main`
- [ ] todo item checked
