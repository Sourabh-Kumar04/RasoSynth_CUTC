# Branching Strategy

This document describes the Git branching architecture for the RasoDataset-Agent platform.

## Overview

The branching strategy follows a modified GitFlow model optimized for:
- Rapid experimentation
- Stable production releases
- Isolated feature development
- Provider integration development
- Infrastructure testing
- Frontend/backend parallel work

## Branch Structure

```
                    ┌─────────────────────────────────────────┐
                    │              main                       │
                    │   (protected, production-ready)        │
                    └──────────────┬────────────────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     │        develop             │
                     │  (integration branch)      │
                     └──────────────┬────────────┘
                                    │
     ┌──────────────────────────────┼──────────────────────────────┐
     │                              │                              │
     ▼                              ▼                              ▼
┌─────────┐                  ┌─────────────┐               ┌─────────┐
│feature/*│                  │provider/*   │               │infra/*  │
│         │                  │             │               │         │
└────┬────┘                  └──────┬──────┘               └────┬────┘
     │                              │                              │
     └──────────────┬───────────────┴────────────────┬──────────┘
                    │                              │
                    ▼                              ▼
            ┌──────────────────────┐      ┌────────────────┐
            │   release/<version>  │      │  hotfix/*      │
            │                      │      │                │
            └──────────┬───────────┘      └───────┬────────┘
                       │                          │
                       ▼                          ▼
                  ┌─────────┐              ┌─────────────┐
                  │  main   │              │ main+develop│
                  └─────────┘              └─────────────┘
```

## Branch Types

### 1. Production Branch (`main`)

**Purpose**: Stable production-ready code

**Rules**:
- No direct commits
- Protected branch (branch protection enabled)
- PR-only merges with required reviews
- All CI checks must pass
- Signed commits preferred

**Merged from**:
- Release branches
- Hotfix branches

### 2. Development Integration Branch (`develop`)

**Purpose**: Active development integration

**Contains**:
- Latest stable development state
- Integrated frontend/backend changes
- Orchestration integration testing

**Rules**:
- No direct commits
- Protected branch
- PR-based workflow

**Merged from**:
- Feature branches
- Provider branches
- Frontend branches
- Research branches
- Hotfix branches

### 3. Feature Branches

**Naming**: `feature/<feature-name>`

**Examples**:
- `feature/provider-hot-switching`
- `feature/checkpoint-recovery`
- `feature/deepseek-provider`
- `feature/failover-dashboard`

**Purpose**:
- Isolated feature development
- Safe experimentation
- Independent testing

**Lifecycle**:
1. Create from `develop`
2. Develop feature
3. PR to `develop`
4. Delete after merge

**CI Trigger**:
- Lint + type check
- Unit tests
- Integration tests

### 4. Provider Integration Branches

**Naming**: `provider/<provider-name>`

**Examples**:
- `provider/deepseek`
- `provider/groq`
- `provider/openrouter`
- `provider/together-ai`
- `provider/ollama`

**Purpose**:
- Isolated provider adapter development
- Provider-specific debugging
- Capability testing
- API compatibility validation

**CI Trigger**:
- Provider adapter tests
- API compatibility tests
- Schema validation

### 5. Infrastructure Branches

**Naming**: `infra/<purpose>`

**Examples**:
- `infra/google-cloud-deployment`
- `infra/kubernetes`
- `infra/redis-optimization`
- `infra/observability-stack`
- `infra/distributed-workers`

**Purpose**:
- Deployment engineering
- Infrastructure migration
- Distributed systems work
- DevOps changes

**CI Trigger**:
- Docker validation
- Terraform validation
- Kubernetes manifest validation
- Security scanning

### 6. Frontend/UI Branches

**Naming**: `frontend/<feature>`

**Examples**:
- `frontend/provider-dashboard`
- `frontend/checkpoint-timeline`
- `frontend/orchestration-ui`
- `frontend/observability-dashboard`

**Purpose**:
- Isolated UI work
- Frontend experimentation
- UX redesigns
- Dashboard improvements

**CI Trigger**:
- Frontend build
- Frontend tests
- Frontend lint

### 7. Research & Experimental Branches

**Naming**: `research/<experiment>`

**Examples**:
- `research/agentic-routing`
- `research/self-improving-orchestrator`
- `research/autonomous-provider-selection`
- `research/ai-driven-failover`

**Purpose**:
- AI experimentation
- Prototype systems
- Unstable experimental logic
- Advanced orchestration research

**Rules**:
- Should NOT directly merge into production
- Test in isolation
- May be archived or deleted

**CI Trigger**:
- Basic lint + type check
- Experimental tests (if any)

### 8. Hotfix Branches

**Naming**: `hotfix/<issue>`

**Examples**:
- `hotfix/security-patch`
- `hotfix/checkpoint-corruption`
- `hotfix/provider-timeout`

**Purpose**:
- Emergency production fixes
- Security patches
- Urgent bug fixes

**Rules**:
- Must merge into both `main` and `develop`
- Requires expedited review
- Must pass critical path tests

**CI Trigger**:
- Hotfix validation
- Security scan
- Production smoke tests

### 9. Release Branches

**Naming**: `release/<version>`

**Examples**:
- `release/v1.0`
- `release/v1.1`
- `release/v2.0`

**Purpose**:
- Stabilization before production
- Final QA
- Deployment validation
- Release candidate testing

**Rules**:
- Create from `develop`
- Only bug fixes allowed
- Version bump commits
- Merge to `main` when ready
- Tag with version

**CI Trigger**:
- Full test suite
- E2E tests
- Staging deployment

## Workflows

### Feature Development Flow

```bash
# 1. Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/my-new-feature

# 2. Develop and commit (conventional commits)
git commit -m "feat(api): add new endpoint"

# 3. Push and create PR
git push -u origin feature/my-new-feature
# Create PR to develop with required reviews

# 4. After approval, squash merge to develop
# 5. Delete feature branch
git branch -d feature/my-new-feature
git push origin --delete feature/my-new-feature
```

### Production Release Flow

```bash
# 1. Create release branch from develop
git checkout develop
git pull origin develop
git checkout -b release/v1.1.0

# 2. Update version in pyproject.toml
# Bump version, commit

# 3. Run final QA and testing
# Fix any issues found

# 4. Merge to main
git checkout main
git merge release/v1.1.0
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin main --tags

# 5. Merge back to develop
git checkout develop
git merge release/v1.1.0

# 6. Delete release branch
git branch -d release/v1.1.0
```

### Hotfix Flow

```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/security-patch

# 2. Fix the issue
git commit -m "fix(core): patch security vulnerability"

# 3. Merge to main
git checkout main
git merge hotfix/security-patch
git tag -a v1.0.1 -m "Hotfix v1.0.1"
git push origin main --tags

# 4. Merge to develop
git checkout develop
git merge hotfix/security-patch

# 5. Delete hotfix branch
git branch -d hotfix/security-patch
```

## CI/CD Pipeline Mapping

| Branch Type     | Workflow File        | Environment        |
|-----------------|--------------------|-------------------|
| `feature/*`     | ci-feature.yml     | Ephemeral preview |
| `provider/*`    | ci-provider.yml    | Preview           |
| `frontend/*`    | ci-frontend.yml    | Preview           |
| `research/*`    | ci-feature.yml     | Preview           |
| `infra/*`       | ci-infra.yml       | Preview           |
| `develop`       | ci-develop.yml     | Staging           |
| `release/*`     | ci-release.yml     | Pre-production    |
| `hotfix/*`      | ci-hotfix.yml      | Production        |
| `main`          | cd-production.yml | Production        |

## Environment Strategy

| Branch           | Environment   | Purpose                          |
|------------------|---------------|----------------------------------|
| `feature/*`      | Ephemeral     | Preview deployments per PR      |
| `provider/*`     | Ephemeral     | Provider-specific testing       |
| `frontend/*`     | Ephemeral     | UI preview deployments           |
| `research/*`     | Experimental  | Isolated testing                |
| `infra/*`        | Sandbox       | Infrastructure validation       |
| `develop`        | Staging       | Integration testing             |
| `release/*`      | Pre-production| Release candidate testing      |
| `main`           | Production    | Live deployment                 |

## Branch Protection Rules

### `main` (Production)
- Require PR reviews (2 approvals)
- Require CI passing
- Require signed commits (optional)
- Prevent force push
- Require linear history (optional)

### `develop` (Integration)
- Require PR reviews (1 approval)
- Require CI passing
- Prevent force push

### `release/*`
- Require PR reviews
- Require CI passing
- Prevent force push until merged

## Best Practices

1. **Small, focused PRs**: Keep changes atomic and reviewable
2. **Up-to-date branches**: Rebase on develop before creating PR
3. **Descriptive names**: Use clear, semantic branch names
4. **Clean history**: Use squash merges for features
5. **Delete old branches**: Remove merged branches promptly
6. **Test locally**: Run tests before pushing
7. **Review own code**: Self-review before requesting others

## Automation

### Automatic Actions

- **Preview deployments**: Every PR gets ephemeral environment
- **Branch protection**: Automatic on main/develop
- **Issue linking**: Auto-linked in PR comments
- **Changelog generation**: Auto-generated on release
- **Version tagging**: Auto-tagged on main merge

### Commit Validation

- **Commit message linting**: Enforced via pre-commit
- **Conventional commits**: Required format
- **Scope validation**: Allowed scopes defined