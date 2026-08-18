# Release Management

This document outlines the release lifecycle, versioning strategy, and deployment procedures for the RasoSynthTune platform.

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/) (SemVer):

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]

Example: v2.1.0-beta.1
```

### Version Components

| Component  | Description                                    | When to Bump |
|------------|-----------------------------------------------|--------------|
| `MAJOR`    | Breaking changes                               | Incompatible API changes |
| `MINOR`    | New features (backward compatible)            | New functionality |
| `PATCH`    | Bug fixes (backward compatible)               | Bug fixes |
| `-PRERELEASE` | Pre-release identifiers                   | Beta/Alpha releases |
| `+BUILD`   | Build metadata                                | Build-specific changes |

### Release Types

| Type       | Example      | Description                        |
|------------|--------------|------------------------------------|
| Major      | v2.0.0       | Breaking changes                  |
| Minor      | v1.2.0       | New features, backward compatible |
| Patch      | v1.1.1       | Bug fixes                          |
| Beta       | v1.2.0-beta  | Pre-release testing                |
| RC         | v1.2.0-rc.1  | Release candidate                  |

## Release Lifecycle

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  develop    │───►│  release/*  │───►│    main     │───►│ production  │
│ (integration)│    │ (stabilize) │    │ (tagged)    │    │ (deployed)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                         │
                         ▼
                   ┌─────────────┐
                   │  develop    │
                   │ (merge back)│
                   └─────────────┘
```

## Release Process

### Phase 1: Preparation

```bash
# 1. Update version in pyproject.toml
# Current: version = "1.0.0"
# New:    version = "1.1.0"

# 2. Update CHANGELOG.md
# Document all changes since last release

# 3. Run comprehensive tests
pytest tests/ -v
```

### Phase 2: Create Release Branch

```bash
# Create release branch from develop
git checkout develop
git pull origin develop
git checkout -b release/v1.1.0

# Update version
# Edit pyproject.toml to v1.1.0
git add pyproject.toml
git commit -m "chore: bump version to v1.1.0"
```

### Phase 3: Stabilization

During the release branch lifecycle:
- **Only bug fixes** allowed
- **No new features**
- **Critical fixes only**

```bash
# Fix a bug
git checkout -b hotfix/fix-description
# Fix, test, commit
git cherry-pick <commit-hash>  # To release branch
```

### Phase 4: Final Validation

```bash
# Run final tests
pytest tests/ --tb=short -v

# Run E2E tests
pytest tests/e2e/ -v

# Verify Docker build
docker build -t rasosynthtune:v1.1.0 .
```

### Phase 5: Merge to Production

```bash
# Merge release to main
git checkout main
git merge release/v1.1.0 --no-ff

# Create version tag
git tag -a v1.1.0 -m "Release v1.1.0"

# Push to origin
git push origin main --tags

# Merge back to develop
git checkout develop
git merge release/v1.1.0 --no-ff

# Delete release branch
git branch -d release/v1.1.0
git push origin --delete release/v1.1.0
```

## Hotfix Release

For critical production issues:

```bash
# Create hotfix from main
git checkout main
git checkout -b hotfix/critical-fix

# Fix and commit
git commit -m "fix(core): critical bug fix"

# Test thoroughly
pytest tests/production/ -v

# Merge to main
git checkout main
git merge hotfix/critical-fix --no-ff
git tag -a v1.0.1 -m "Hotfix v1.0.1"
git push origin main --tags

# Merge to develop
git checkout develop
git merge hotfix/critical-fix --no-ff

# Delete hotfix branch
git branch -d hotfix/critical-fix
```

## Deployment Environments

### Development (Develop Branch)
- **URL**: `https://dev.api.example.com`
- **Purpose**: Integration testing
- **Auto-deploy**: On push to `develop`

### Staging (Release Branch)
- **URL**: `https://staging.api.example.com`
- **Purpose**: QA and release candidate testing
- **Auto-deploy**: On push to `release/*`

### Production (Main Branch)
- **URL**: `https://api.example.com`
- **Purpose**: Live production traffic
- **Manual deploy**: Via GitHub Actions

## Rollback Procedures

### Quick Rollback (Hotfix)

```bash
# Revert last release tag
git revert <release-commit>
git push origin main

# Or rollback to previous tag
git checkout v1.0.0
git checkout -b hotfix/rollback-to-1.0.0
```

### Database Rollback

```bash
# Apply down migrations
alembic downgrade -1

# Run database restore if needed
psql < backup.sql
```

### Application Rollback

```bash
# Via ECS
aws ecs update-service --cluster prod --service api \
  --task-definition <previous-task-def> \
  --force-new-deployment

# Via Kubernetes
kubectl rollout undo deployment/api
```

## Release Checklist

- [ ] All tests passing
- [ ] E2E tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml
- [ ] Release notes drafted
- [ ] Security scan passed
- [ ] Performance benchmarks met
- [ ] DB migrations tested
- [ ] Rollback plan verified
- [ ] Stakeholders notified

## Automated Release Pipeline

```yaml
# .github/workflows/cd-production.yml
on:
  push:
    branches:
      - main

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/production/ -v

  deploy:
    needs: validate
    runs-on: ubuntu-latest
    environment: production
    steps:
      - run: ./deploy.sh production

  tag:
    needs: deploy
    runs-on: ubuntu-latest
    steps:
      - run: |
          VERSION=$(grep "^version" pyproject.toml | cut -d'=' -f2 | tr -d ' ')
          git tag -a "v$VERSION" -m "Release v$VERSION"
          git push --tags
```

## Release Communication

### Pre-Release
- Notify QA team for testing
- Update status page (if applicable)
- Brief stakeholders on expected timeline

### Post-Release
- Announce in #releases Slack channel
- Update CHANGELOG with release date
- Send release notes to stakeholders
- Update API documentation if needed