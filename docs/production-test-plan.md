# OrganicSlides Production Test Plan

## 1. Document Purpose

This document defines how OrganicSlides will be validated before and after production release.

Testing goals:

- prevent regressions
- protect generation quality
- verify production readiness
- make every requirement mergeable by itself

## 2. Mandatory Test Gates Per PR

Every requirement PR must declare and execute the relevant test set.

Current protected checks on `main`:

- [x] `CI-CHECK-001` `frontend-build`
- [x] `CI-CHECK-002` `frontend-tests`
- [x] `CI-CHECK-003` `backend-tests`
  Validation completed on `2026-03-07` and enforced through GitHub branch protection on `main`.

- [ ] `TEST-GATE-001` Lint and typecheck must pass for changed code.
  Completion standard: no ignored failures, no skipped type errors.

- [ ] `TEST-GATE-002` Unit tests for changed business logic must pass.
  Completion standard: new logic is covered by deterministic tests.

- [ ] `TEST-GATE-003` Contract tests must pass when API shape or event shape changes.
  Completion standard: frontend and backend agree on schemas.

- [ ] `TEST-GATE-004` Integration tests must pass when storage, queue, auth, or rendering behavior changes.
  Completion standard: changed dependencies are exercised together.

- [ ] `TEST-GATE-005` End-to-end tests must pass for user-facing flows when UI workflow changes.
  Completion standard: affected flows are green in CI.

- [ ] `TEST-GATE-006` Golden quality checks must pass when prompt, style, or rendering logic changes.
  Completion standard: quality regression threshold is not exceeded.

## 3. Test Layers

### 3.1 Static Validation

- [ ] `TEST-001` ESLint coverage for frontend and shared TypeScript code.
- [ ] `TEST-002` TypeScript strict build gate.
- [ ] `TEST-003` Ruff or equivalent Python lint gate.
- [ ] `TEST-004` Python type checking for critical backend modules.

### 3.2 Unit Tests

- [ ] `TEST-005` State schema tests for `ResearchPacket`, `StylePacket`, `SlideSpec`, and `RenderPlan`.
- [ ] `TEST-006` Planner normalization and outline validation tests.
- [ ] `TEST-007` Writer content validation and repair tests.
- [ ] `TEST-008` Visual route decision and HTML rule validation tests.
- [ ] `TEST-009` Renderer prompt assembly and asset resolution tests.
- [ ] `TEST-010` Auth helper and permission rule tests.
- [ ] `TEST-011` Rate limit, quota, and cost-policy tests.

### 3.3 Contract Tests

- [ ] `TEST-012` REST API schema tests for auth, projects, styles, uploads, previews, downloads, and history.
- [ ] `TEST-013` SSE event schema tests for job lifecycle, per-slide progress, failure events, and completion events.
- [ ] `TEST-014` Object storage metadata contract tests.

### 3.4 Integration Tests

- [ ] `TEST-015` Postgres persistence tests for project lifecycle and revision history.
- [ ] `TEST-016` Redis queue and lock behavior tests.
- [ ] `TEST-017` Worker retry and idempotency tests.
- [ ] `TEST-018` Auth integration tests across API, preview, SSE, and download endpoints.
- [ ] `TEST-019` Rendering pipeline integration tests for `path_a`, `path_b`, and mixed mode.
- [ ] `TEST-020` Asset persistence tests with object storage or MinIO.

### 3.5 End-to-End Tests

- [ ] `TEST-021` User registration and login flow.
- [ ] `TEST-022` Project creation and outline approval flow.
- [ ] `TEST-023` Style selection and render path selection flow.
- [ ] `TEST-024` Thesis upload and generation flow.
- [ ] `TEST-025` Preview and download flow.
- [ ] `TEST-026` History and project revisit flow.
- [ ] `TEST-027` Failure and retry flow.

### 3.6 Quality Regression Tests

- [ ] `TEST-028` Golden prompt set for general business topics.
- [ ] `TEST-029` Golden prompt set for thesis-defense topics.
- [ ] `TEST-030` Golden prompt set for illustration-heavy styles.
- [ ] `TEST-031` Golden prompt set for editorial styles.
- [ ] `TEST-032` Regression scoring for title quality, density, style adherence, and render path correctness.

### 3.7 Performance and Reliability Tests

- [ ] `TEST-033` Queue throughput and worker concurrency tests.
- [ ] `TEST-034` Load test for project creation, status polling, preview, and download APIs.
- [ ] `TEST-035` Long-running job timeout and cancellation tests.
- [ ] `TEST-036` Restart recovery tests for in-flight jobs.
- [ ] `TEST-037` Storage cleanup and retention job tests.

### 3.8 Security Tests

- [ ] `TEST-038` Authorization bypass tests.
- [ ] `TEST-039` Upload validation and malicious file rejection tests.
- [ ] `TEST-040` Prompt injection and unsafe HTML handling tests.
- [ ] `TEST-041` Rate limiting and abuse scenario tests.
- [ ] `TEST-042` Secret and config exposure checks.

### 3.9 Release Verification

- [ ] `TEST-043` Database migration forward test.
- [ ] `TEST-044` Database migration rollback test.
- [ ] `TEST-045` Backup and restore verification.
- [ ] `TEST-046` Staging smoke test after deployment.
- [ ] `TEST-047` Production canary verification.

## 4. Quality Scorecard

Every quality-sensitive PR must record a scorecard.

- [ ] `QS-001` Assertion-title compliance
- [ ] `QS-002` Bullet density compliance
- [ ] `QS-003` Style adherence
- [ ] `QS-004` Render path correctness
- [ ] `QS-005` Chinese text legibility
- [ ] `QS-006` Asset generation success rate
- [ ] `QS-007` End-to-end success rate

Recommended release threshold:

- no metric below target for launch-blocking scenarios
- no new regression above agreed threshold on golden cases

## 5. Environment Strategy

- [ ] `ENV-TEST-001` Local environment for fast unit and component tests.
- [ ] `ENV-TEST-002` CI environment for deterministic full validation.
- [ ] `ENV-TEST-003` Staging environment with production-like storage and queue topology.
- [ ] `ENV-TEST-004` Production canary environment for controlled verification.

## 6. Test Data Strategy

- [ ] `DATA-TEST-001` Versioned fixture set for small deterministic prompts.
- [ ] `DATA-TEST-002` Versioned thesis sample documents.
- [ ] `DATA-TEST-003` Versioned style fixture set.
- [ ] `DATA-TEST-004` Versioned golden output review checklist.

## 7. Merge Policy

A PR is mergeable only when:

1. all applicable test gates are green
2. no blocked reviewer comments remain
3. rollback plan is written
4. the related item in `docs/production-todo.md` is checked
