# Release Checklist Template

## Release Metadata

- Release name:
- Date:
- Owner:
- Included requirement IDs:
- Deployment target:

## Pre-Release

- [ ] Scope is frozen
- [ ] Linked PRs are merged to `main`
- [ ] Required CI checks are green
- [ ] Migration steps are reviewed
- [ ] Rollback template is prepared
- [ ] Release notes are prepared
- [ ] On-call or owner is available during release window

## Deployment

- [ ] Release tag or deployment artifact is created
- [ ] Environment variables and secrets are verified
- [ ] Deployment started
- [ ] Deployment completed without platform errors

## Post-Deployment Verification

- [ ] Health endpoints are green
- [ ] Core user flows are verified
- [ ] Error rate is normal
- [ ] Queue, worker, and storage health are normal
- [ ] Monitoring dashboards are checked
- [ ] Alerts are quiet or understood

## Rollback Decision Gate

- [ ] Rollback not required
- [ ] If rollback is required, trigger documented rollback immediately

## Sign-off

- [ ] Engineering sign-off
- [ ] Operator sign-off
- [ ] Release recorded in changelog or release notes
