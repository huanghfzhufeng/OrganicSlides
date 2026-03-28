# OrganicSlides Backlog

## 1. Purpose

This file is the working backlog for turning OrganicSlides into a stable, deployable, and maintainable product.

It complements:

- `docs/production-optimization-plan.md`
- `docs/production-todo.md`

Those two documents describe the long-range production plan.
This backlog is the short-cycle execution view for the core agent team.

## 2. Current Baseline (2026-03-23)

Current repo health from the latest audit:

- Frontend build passes: `frontend/npm run build`
- Frontend tests pass: `frontend/npm test -- --run`
- Backend unit tests pass: `./.venv/bin/pytest tests/unit -q`
- Backend integration tests pass: `./.venv/bin/pytest tests/integration -q`
- Frontend lint fails and is currently the clearest quality gate in the repo
- Runtime artifacts and uploaded files have leaked into version control
- README and TESTING docs are out of sync with the current repo layout
- The highest-value frontend risks are state reset leakage, incomplete retry reset, and stale SSE callback handling
- The highest-value backend and rendering risks are output-directory drift, render-path consistency, and legacy/orphan file cleanup

## 3. Product Goal

The near-term target is not "public launch".
The near-term target is a release candidate that satisfies all of the following:

- a fresh clone can be booted locally with documented steps
- prompt-only generation works end-to-end
- document-upload generation works end-to-end
- PPTX export is stable and recoverable
- lint, build, unit, integration, and smoke checks are green
- runtime artifacts are not committed to git
- docs match the actual code and startup flow

## 4. Backlog Rules

1. One backlog item equals one implementation slice.
2. One implementation slice should normally map to one branch and one review cycle.
3. No direct day-to-day development on `main`.
4. Every completed item must include code, tests, docs, and a short validation note.
5. A cleanup item is not complete until generated artifacts are removed from git tracking without breaking local workflows.
6. A stability item is not complete until the failure path has been exercised, not just the happy path.

## 5. Priority Legend

- `P0`: required for a stable baseline and first usable release candidate
- `P1`: required for product quality and delivery confidence
- `P2`: required for durable productionization

## 6. Prioritized Backlog

| ID | Priority | Owner | Slice | Done when |
| --- | --- | --- | --- | --- |
| `OS-001` | `P0` | `Lead` | Repair repo hygiene baseline: ignore `output/` and `backend/uploads/`, stop tracking runtime artifacts, and document the policy. | No runtime artifacts remain tracked, `.gitignore` is correct, and the cleanup is documented. |
| `OS-002` | `P0` | `Lead` | Align README, TESTING, startup scripts, and local run instructions with the actual repo state. | A new contributor can follow the docs without guessing missing steps or paths. |
| `OS-003` | `P0` | `QA/Review` | Define and document the required local release gate: lint, build, frontend tests, backend unit tests, backend integration tests. | One canonical validation list exists and is referenced by future work. |
| `OS-004` | `P0` | `Frontend` | Fix project reset and new-project state leakage in the app shell. | Starting a new project cannot show outline, blueprint, or error state from a previous run. |
| `OS-005` | `P0` | `Frontend` | Fix generation retry so logs, slides, progress, and completion state are fully reset. | Retrying generation never mixes old and new run state in the UI. |
| `OS-006` | `P0` | `Frontend` | Refactor `useSSE` callback handling to avoid stale closures and incomplete dependency management. | SSE consumers receive the latest handlers and retry behavior is explicit and testable. |
| `OS-007` | `P0` | `Frontend` | Replace boundary-layer `any` types in API and SSE handling with explicit response and event types. | Lint passes for the touched files and payload mismatches fail earlier. |
| `OS-008` | `P0` | `QA/Review` | Add frontend regression coverage for app reset, generation retry, and SSE-driven views. | The current highest-risk UI flows are covered by automated tests. |
| `OS-009` | `P1` | `Backend` | Unify the output directory and artifact contract across backend and renderer code. | There is one documented output strategy and no ambiguous root-vs-backend output path behavior. |
| `OS-010` | `P1` | `Rendering` | Enforce render-path preference through the full generation pipeline. | A selected render path is honored end-to-end or an explicit override is logged. |
| `OS-011` | `P1` | `Rendering` | Add render preflight validation and explicit failure states before export. | Invalid inputs fail early with actionable messages instead of silent degradation. |
| `OS-012` | `P1` | `Backend` | Verify and remove orphan or duplicate backend modules and legacy test remnants. | Legacy files are either deleted with proof or retained with documented ownership. |
| `OS-013` | `P2` | `Backend` | Replace process-local generation state with durable persistence for jobs, revisions, and events. | Generation can survive process restarts and state is queryable from durable storage. |
| `OS-014` | `P2` | `Backend` | Split synchronous API execution from background worker execution. | API request lifecycle is decoupled from long-running generation work. |
| `OS-015` | `P2` | `Rendering` | Move generated artifacts and previews to durable storage with retention rules. | Downloads and previews no longer depend on local ephemeral disk paths. |

## 7. Milestones

### M0: Baseline Stable

The repo is clean enough to support fast iteration.

Backlog items:

- `OS-001`
- `OS-002`
- `OS-003`

Exit criteria:

- runtime artifacts are not tracked
- docs match startup reality
- the local release gate is documented and repeatable

### M1: Main Flow Stable

The primary user path is reliable and regression-tested.

Backlog items:

- `OS-004`
- `OS-005`
- `OS-006`
- `OS-007`
- `OS-008`
- `OS-009`
- `OS-010`
- `OS-011`
- `OS-012`

Exit criteria:

- new project flow is clean
- retry flow is deterministic
- SSE behavior is stable
- render path behavior is explicit
- frontend and backend contracts are less fragile

### M2: Release Candidate

The system behaves like a product candidate rather than a demo.

Backlog items:

- `OS-013`
- `OS-014`
- `OS-015`

Exit criteria:

- generation state is durable
- worker execution is separated from the API plane
- artifacts are managed with production-style storage assumptions

## 8. Recommended First Sprint

Sprint goal:

- stabilize the engineering baseline
- stop the repo from getting dirtier
- remove the most obvious user-facing workflow bugs

Sprint scope:

- `OS-001`
- `OS-002`
- `OS-003`
- `OS-004`
- `OS-005`
- `OS-006`
- `OS-008`

Stretch goals:

- `OS-007`
- `OS-009`

## 9. Definition of Done

A backlog item is complete only when all of the following are true:

- implementation is merged or ready to merge
- affected tests are added or updated
- required local checks were run
- docs or comments were updated where the contract changed
- the change includes a short validation note
- known follow-ups are written down instead of being silently deferred
