# OrganicSlides Production Optimization Plan

## 1. Document Purpose

This document defines the productionization plan for OrganicSlides.

Target state:

- the system is not a demo
- the system is deployable for external users
- the system is observable, recoverable, testable, and scalable
- every requirement is delivered as an independent PR-sized unit

This plan is the master blueprint.
Execution details live in:

- `docs/production-test-plan.md`
- `docs/production-todo.md`

## 2. Delivery Rules

The following rules are mandatory for all future work:

1. One requirement equals one checkbox item.
2. One checkbox item equals one implementation slice.
3. One implementation slice equals one branch, one PR, one merge to `main`.
4. Do not bundle multiple requirements into one PR unless the todo item explicitly says they are inseparable.
5. A requirement can be checked only after code, tests, docs, and rollback notes are complete.
6. No direct commits to `main`.
7. Every PR must pass the required CI checks before merge.

Recommended branch naming:

- `codex/req-001-build-baseline`
- `codex/req-014-style-packet`

Required PR sections:

1. Requirement ID
2. Scope
3. User-facing impact
4. Technical changes
5. Tests executed
6. Risks
7. Rollback plan

## 3. Production Goals

### 3.1 Product Goals

- users can sign up, log in, create projects, generate decks, preview, download, and view history reliably
- style selection has visible impact on output quality
- generation quality is stable enough for repeated real-world use
- failures are visible, explainable, and recoverable

### 3.2 Engineering Goals

- zero known P0 defects
- zero known P1 defects before public launch
- build, typecheck, unit, integration, and end-to-end pipelines are green
- all long-running generation jobs survive process restarts
- task states and outputs are persisted outside process memory

### 3.3 Operational Goals

- production deployment supports external traffic
- observability covers logs, metrics, traces, and alerting
- storage does not rely on local ephemeral disk
- rate limiting, quotas, and abuse protection are in place

## 4. Core Problems to Solve

- [x] `REQ-001` Fix the broken engineering baseline: frontend build, frontend tests, backend tests, and type errors must all pass.
  Completion standard: `npm run build`, frontend tests, and backend tests all pass in CI.
  Validation completed on `2026-03-07` with `frontend/npm run build`, `frontend/npm test -- --run`, and `pytest -q`.

- [ ] `REQ-002` Remove demo-only runtime assumptions such as in-memory workflow persistence and process-local state.
  Completion standard: generation state survives process restart and can be resumed.

- [ ] `REQ-003` Make `huashu-slides` a runtime input instead of a static reference-only asset.
  Completion standard: style references, prompt constraints, and sample assets are injected into generation as structured data.

- [ ] `REQ-004` Replace silent quality degradation with explicit validation, retry, and fail-fast behavior.
  Completion standard: invalid writer or visual output is repaired or rejected; it is not silently replaced by generic slides without traceability.

- [ ] `REQ-005` Enforce render path preference and routing consistency.
  Completion standard: a user-selected render preference is honored all the way to rendering unless a controlled policy override is logged.

- [ ] `REQ-006` Standardize project, session, task, asset, and event persistence in durable storage.
  Completion standard: database becomes the source of truth for project lifecycle state.

- [ ] `REQ-007` Split the API plane from the generation worker plane.
  Completion standard: HTTP API no longer executes the full generation workload inline.

- [ ] `REQ-008` Move generated files and previews to object storage.
  Completion standard: downloads and previews work without relying on local disk paths.

- [ ] `REQ-009` Make authentication and authorization rules consistent across all project APIs, SSE endpoints, preview endpoints, and downloads.
  Completion standard: no project data is accessible without valid authorization.

- [ ] `REQ-010` Add production-grade observability and operational tooling.
  Completion standard: traces, metrics, structured logs, alerts, and admin troubleshooting views are available.

- [ ] `REQ-011` Add abuse protection, cost control, and quota enforcement.
  Completion standard: per-user concurrency, daily usage, upload limits, and generation budgets are enforced.

- [ ] `REQ-012` Establish release governance, rollback, and migration safety.
  Completion standard: every production deployment has rollback instructions and migration verification.

## 5. Target Architecture

### 5.1 Services

- API service
  Responsibility: auth, project APIs, history APIs, request validation, job submission, status queries

- Worker service
  Responsibility: researcher, planner, writer, visual, renderer, retries, quality gates

- PostgreSQL
  Responsibility: users, projects, job records, slide specs, render plans, asset metadata, audit events

- Redis
  Responsibility: queue, cache, transient locks, rate limiting, pub-sub

- Object storage
  Responsibility: PPTX files, slide thumbnails, generated images, input assets, exported previews

### 5.2 Data Model Direction

- `Project`
- `ProjectRevision`
- `GenerationJob`
- `SlideSpec`
- `RenderPlan`
- `GeneratedAsset`
- `JobEvent`
- `QualityGateResult`

### 5.3 Workflow Direction

1. User creates project.
2. API stores draft state.
3. API submits a job.
4. Worker loads structured `StylePacket` and `ResearchPacket`.
5. Worker generates `Outline`.
6. User approves outline.
7. Worker generates `SlideSpec`.
8. Worker generates `RenderPlan`.
9. Quality gate validates output.
10. Renderer produces assets and PPTX.
11. API exposes preview and download from durable storage.

## 6. Quality Architecture

- [ ] `REQ-013` Introduce structured schemas for `ResearchPacket`, `StylePacket`, `SlideSpec`, and `RenderPlan`.
  Completion standard: writer, visual, and renderer communicate with validated schemas only.

- [ ] `REQ-014` Build a `StylePacket` generator from `huashu-slides` style JSON, references, prompt constraints, and sample assets.
  Completion standard: selected style fully changes downstream prompts and validation behavior.

- [ ] `REQ-015` Add a writer quality gate.
  Completion standard: titles, bullet density, path hints, text lengths, and required fields are validated before visual generation.

- [ ] `REQ-016` Add a visual quality gate.
  Completion standard: path routing, HTML constraints, prompt structure, and style compliance are validated before rendering.

- [ ] `REQ-017` Add deterministic recovery paths.
  Completion standard: retry and fallback logic is explicit, logged, and measurable.

- [ ] `REQ-018` Add a golden dataset for output quality regression.
  Completion standard: representative prompts, styles, and expected quality criteria are versioned and testable.

## 7. Scalability and Reliability Architecture

- [ ] `REQ-019` Replace in-process execution with queue-based job dispatch.
  Completion standard: API request lifecycle is decoupled from full generation execution.

- [ ] `REQ-020` Add resumable jobs and idempotent workers.
  Completion standard: duplicate events and retries do not corrupt project state.

- [ ] `REQ-021` Add multi-step timeout and cancellation controls.
  Completion standard: long-running jobs can be cancelled safely and failed steps are recoverable.

- [ ] `REQ-022` Add object-storage-backed previews and artifact retention rules.
  Completion standard: assets have retention policy, metadata, and cleanup jobs.

- [ ] `REQ-023` Add production deployment topology and environment separation.
  Completion standard: dev, staging, and production have separate configs, storage, and secrets.

## 8. Security and Compliance Architecture

- [ ] `REQ-024` Standardize auth for API, SSE, preview, and downloads.
  Completion standard: all protected resources use one approved auth strategy.

- [ ] `REQ-025` Add input hardening for prompts, uploads, and generated HTML.
  Completion standard: file validation, content limits, and sanitization are enforced.

- [ ] `REQ-026` Add audit logs and sensitive-operation tracking.
  Completion standard: project access, generation starts, downloads, and admin actions are auditable.

- [ ] `REQ-027` Add rate limiting and anti-abuse policies.
  Completion standard: anonymous and authenticated limits are enforced and observable.

## 9. Productization Architecture

- [ ] `REQ-028` Add project revision history.
  Completion standard: users can inspect or restore previous outline/style/render states.

- [ ] `REQ-029` Add admin and support tooling.
  Completion standard: operators can inspect failed jobs, retry jobs, and review asset state.

- [ ] `REQ-030` Add user-facing failure transparency.
  Completion standard: users see actionable failure messages instead of generic generation errors.

- [ ] `REQ-031` Add quotas, billing hooks, and usage accounting.
  Completion standard: the system can measure and limit costly generation usage.

## 10. Exit Criteria for Public Launch

Public launch is allowed only when all launch-blocking requirements below are complete:

- [ ] `REQ-LAUNCH-001` Build, typecheck, unit, integration, and end-to-end pipelines are green.
- [ ] `REQ-LAUNCH-002` No open P0 defects.
- [ ] `REQ-LAUNCH-003` No open P1 defects.
- [ ] `REQ-LAUNCH-004` Durable persistence and restart recovery are verified.
- [ ] `REQ-LAUNCH-005` Object storage, backups, and restore procedures are verified.
- [ ] `REQ-LAUNCH-006` Monitoring, alerting, and incident runbooks are verified.
- [ ] `REQ-LAUNCH-007` Security review, auth review, and rate limiting review are complete.
- [ ] `REQ-LAUNCH-008` Load test and cost-control thresholds are verified.

## 11. Definition of Done

A requirement is complete only if all conditions below are true:

- code is merged into `main`
- related tests are added or updated
- CI is green
- docs are updated
- monitoring impact is considered
- rollback path is documented
- the requirement checkbox is checked in `docs/production-todo.md`
