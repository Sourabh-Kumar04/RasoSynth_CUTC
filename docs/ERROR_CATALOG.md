# Error Catalog — RasoDataset-Agent

> Date: 2026-06-11 | Commit: da8d6b92

## Summary
- **P0 (Critical)**: 1 open issue
- **P1 (Major)**: 4 open issues
- **P2 (Moderate)**: 6 open issues
- **P3 (Minor)**: 3 open issues

---

## P0 — Critical

### #EO-001: Frontend `crypto.subtle` TypeError in Production
- **Status**: 🔴 Open
- **Location**: `frontend/` (Next.js 14 server-side)
- **Error**: `TypeError: Cannot read properties of null (reading 'digest')`
- **Impact**: Frontend crashes on every request, users cannot reliably use the app
- **Evidence**: Container logs show repeated crashes at `next-server` runtime
- **Root Cause**: `crypto.subtle` is a Web Crypto API that does not exist in Node.js server environment. Likely used by `next-auth@4.24.7` or a hash function in SSR.
- **Fix**: Polyfill or ensure `crypto.subtle` usage only on client-side.

---

## P1 — Major

### #EO-002: Google Gemini Provider Completely Degraded
- **Status**: 🟡 Mitigated (with retry logic)
- **Location**: `providers/google_gemini.py`
- **Error**: `429 Too Many Requests` — 10/10 recent failures
- **Impact**: Primary provider unavailable, falling back to NVIDIA NIM
- **Evidence**: Health check shows `"google_gemini": "degraded"`; logs: `Skipping unhealthy provider google_gemini: 10/10 recent failures`
- **Root Cause**: Gemini API key has exceeded rate limit quota.
- **Fix Applied**: Exponential backoff with jitter (3 retries). Monitor quota.

### #EO-003: NVIDIA NIM 404 Not Found Errors
- **Status**: 🟡 Mitigated (with endpoint rotation)
- **Location**: `providers/nvidia_nim.py`
- **Error**: `404 Not Found` — model not available on endpoint
- **Impact**: Failed API requests, unnecessary retries
- **Evidence**: Logs: `HTTP/1.1 404 Not Found` at `integrate.api.nvidia.com/v1/chat/completions`
- **Root Cause**: Requested model not found at current endpoint. Endpoint/model mismatch.
- **Fix Applied**: Endpoint fallback rotation + model fallback (3 endpoints, all SUPPORTED_MODELS).

### #EO-004: NVIDIA NIM 429 Rate Limiting
- **Status**: 🟡 Mitigated (with retry logic)
- **Location**: `providers/nvidia_nim.py`
- **Error**: `429 Too Many Requests`
- **Impact**: Pipeline requests slowed, risk of cascading failures
- **Evidence**: Hundreds of `HTTP/1.1 429 Too Many Requests` in logs
- **Root Cause**: Exceeded NVIDIA NIM API request quota.
- **Note**: OpenAI SDK retries automatically, but adds latency.

### #EO-005: Raw Dataset Prompt Leaking into Search URLs
- **Status**: ✅ Fixed (commit 570f56f1, 0910c8ac)
- **Location**: `pipeline/discovery.py`
- **Impact**: Search engines (GitHub, PubMed, ArXiv) receiving 1281+ char URLs, causing 422/429
- **Evidence**: Logs: `api.semanticscholar.org/...?query=Cybersecurity+operations%2C+...+Dataset+Name%3A...`
- **Root Cause**: `target_domain` parameter contained full raw prompt instead of short domain.
- **Fix Applied**: Hardened guard in `discover()`: detects instruction headers, trims to ≤100 chars, uses santised query.

---

## P2 — Moderate

### #EO-006: Qdrant Healthcheck Failing (False Negative)
- **Status**: ✅ Fixed (commit da8d6b92)
- **Location**: `docker-compose.yml`
- **Error**: `OCI runtime exec failed: curl: executable file not found in $PATH`
- **Impact**: Qdrant falsely showing as unhealthy in Docker
- **Fix Applied**: Commented out broken curl-based healthcheck. Qdrant runs fine without it.

### #EO-007: Qdrant Exposed Without Authentication
- **Status**: 🔴 Open
- **Location**: `docker-compose.yml` port mapping
- **Impact**: `0.0.0.0:6333` publicly accessible without auth
- **Fix Strategy**: Bind to 127.0.0.1 or add Qdrant API key.

### #EO-008: Next.js Frontend Build Error: `crypto.subtle`
- **Status**: 🔴 Open
- **Location**: `frontend/` Next.js production build
- **Error**: `TypeError: Cannot read properties of null (reading 'digest')`
- **Impact**: Server-side rendering crashes, frontend partially broken
- **Evidence**: Frontend container logs

### #EO-009: Jobs Lost Their Progress After Rebuild
- **Status**: 🔴 Open (by design / expected)
- **Location**: `/app/outputs` volume, in-memory `Job` objects
- **Impact**: 2 jobs (`9eaed6b8`, `cf9119c0`) reset to 0 progress after container rebuild
- **Root Cause**: Job progress/state not fully persisted to database; loaded from memory on restart
- **Fix Strategy**: Ensure job state is persisted to PostgreSQL before container restarts.

### #EO-010: UTF-8 Decode Errors in Console Output
- **Status**: 🔴 Open
- **Location**: `pipeline/discovery.py` LLM output processing
- **Error**: Characters like → (U+2192) cause terminal encoding issues
- **Impact**: Minor log degradation, not functional

### #EO-011: API Response: Redis Warning vs Error Mismatch
- **Status**: 🔴 Open
- **Location**: `api/server.py` health check
- **Issue**: Health response shows `"redis": false` even though Redis connection might succeed later
- **Fix Strategy**: Make health check more forgiving or add connection retry.

---

## P3 — Minor

### #EO-012: Deprecated Server Files Still Exist
- **Status**: 🟡 Noted
- **Files**: `api/server_v2.py`, `api/server_production.py`, `api/server_standalone.py`
- **Impact**: Confusion; risk of accidentally using wrong entry point
- **Fix Strategy**: Delete deprecated files or move to `archive/`.

### #EO-013: Health Uptime Always 0.0
- **Status**: 🟡 Noted
- **Location**: `api/server.py` health endpoint
- **Issue**: `"uptime_seconds": 0.0` — not being populated
- **Impact**: Makes uptime monitoring useless
- **Fix Strategy**: Track process start time and calculate delta.

### #EO-014: Container Memory Limits May Be Too Tight
- **Status**: 🟡 Noted
- **Location**: `docker-compose.yml`
- **Issue**: `app` limited to 2G, frontend to 512M — may cause OOM during heavy LLM processing
- **Fix Strategy**: Monitor for OOM and increase if needed.
