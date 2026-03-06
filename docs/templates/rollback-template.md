# Rollback Template

## Change Identification

- Requirement ID:
- PR:
- Merge commit:
- Release version:
- Owner:

## Trigger

- What failed:
- Detection source:
- Severity:
- Decision time:

## Blast Radius

- Affected systems:
- Affected users:
- Data impact:
- Security impact:

## Rollback Strategy

- Strategy type: revert / config change / traffic shift / hotfix
- Preconditions:
- Dependencies:

## Execution Steps

1. Freeze further deploys.
2. Capture current failure evidence.
3. Apply rollback action.
4. Restore previous known-good state.
5. Verify health checks, logs, metrics, and user flow.

## Concrete Commands or Actions

```text
Add the exact commands, dashboard links, feature flags, or deployment actions here.
```

## Verification

- CI or smoke checks:
- API verification:
- UI verification:
- Data verification:

## Communication

- Internal update sent:
- External update needed:
- Incident document link:

## Follow-up

- Root cause owner:
- Fix PR:
- Guardrail to prevent recurrence:
