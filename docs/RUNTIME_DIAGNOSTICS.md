# Runtime Diagnostics — RasoDataset-Agent
> Generated: 2026-06-11T08:24:00Z

## Docker Compose Status

| Service | Container | Status | Ports | Notes |
|---------|-----------|--------|-------|-------|
| app | rasodataset-agent-app-1 | ✅ Healthy | 0.0.0.0:8000→8000 | Rebuilt with latest fixes |
| frontend | rasodataset-agent-frontend-1 | ✅ Up | 0.0.0.0:3000→3000 | Node.js Next.js server |
| postgres | rasodataset-agent-postgres-1 | ✅ Healthy | 127.0.0.1:5432→5432 | Bound to localhost |
| redis | rasodataset-agent-redis-1 | ✅ Healthy | 127.0.0.1:6379→6379 | Bound to localhost |
| qdrant | rasodataset-agent-qdrant-1 | ✅ Up | 0.0.0.0:6333-6334 | No curl/wget in image |

## Health Check Results

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "database": true,
  "redis": true,
  "providers": {
    "google_gemini": "degraded",
    "anthropic": "unconfigured",
    "openai": "unconfigured",
    "nvidia": "healthy",
    "huggingface": "healthy",
    "ollama": "unconfigured"
  }
}
```

**Key improvement**: `redis: true` — the `cache.redis` property fix is now active.

## API Endpoint Status

| Endpoint | Status | Response |
|----------|--------|----------|
| GET /health | ✅ 200 | {"status":"healthy"...} |
| GET /jobs?limit=5 | ✅ 200 | Returns job list |
| GET /auth/csrf-token | ✅ 200 | Returns CSRF token |
| POST /jobs | ✅ 403 | CSRF required (correct behavior) |

## Networking

- **Backend**: 0.0.0.0:8000 (publicly accessible)
- **Frontend**: 216.128.153.159:3000 (publicly accessible)
- **Postgres**: 127.0.0.1:5432 (localhost only) — security fix applied
- **Redis**: 127.0.0.1:6379 (localhost only) — security fix applied
- **Qdrant**: 0.0.0.0:6333 (public, no auth) — monitored

## UFW Firewall Status

| Port | Action | From |
|------|--------|------|
| 22/tcp | ALLOW | Anywhere |
| 8000/tcp | ALLOW | Anywhere |
| 3000/tcp | ALLOW | Anywhere |
| 5432/tcp | NOT ALLOWED (localhost only) | Secure |
| 6379/tcp | NOT ALLOWED (localhost only) | Secure |

## Provider Health

| Provider | Status | Issue |
|----------|--------|-------|
| Google Gemini | Degraded | 429 Too Many Requests, 10/10 failures |
| NVIDIA NIM | Healthy | Working, occasional 429/404 |
| HuggingFace | Healthy | Working |
| Anthropic Claude | Unconfigured | No API key |
| OpenAI | Unconfigured | No API key |
| Ollama | Unconfigured | No local instance |

## Database

- PostgreSQL 16 running with 50 max connections
- Database: `dataset_engine`
- Tables initialized via `init.sql`
- Connection: `asyncpg` via `postgresql+asyncpg`

## Redis

- Redis 7.4.9 running in standalone mode
- AOF persistence enabled
- Max memory: 256MB with allkeys-lru eviction
- Security note: External attacks detected (POST/Host commands) before binding to localhost

## Container Resource Limits

| Service | Memory Limit | Memory Reservation |
|---------|-------------|-------------------|
| app | 2G | 512M |
| frontend | 512M | — |
| postgres | 1G | 256M |
| redis | 512M | 128M |
| qdrant | 2G | 512M |

## Observed Issues in Runtime

1. **Jobs stuck/failed**: Two jobs (`9eaed6b8`, `cf9119c0`) failed after rebuild (expected due to code change)
2. **Provider 429/404**: NVIDIA NIM receiving rate limits; Gemini completely degraded
3. **Frontend crypto error**: Next.js `crypto.subtle` TypeError in production build
4. **Qdrant no healthcheck**: Removed broken curl-based check; container running fine
