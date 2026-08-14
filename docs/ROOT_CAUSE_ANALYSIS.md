# Root Cause Analysis — RasoDataset-Agent

## Issue #EO-001: Frontend `crypto.subtle` TypeError

| Field | Detail |
|-------|--------|
| **Severity** | P0 — Critical |
| **Component** | Next.js 14 Frontend (Production Build) |
| **Component Location** | `frontend/` |
| **Root Cause** | `crypto.subtle` (Web Crypto API) used in server environment where `crypto` global exists but `subtle` is `null` in Node.js 20 |
| **Evidence** | Container log: `TypeError: Cannot read properties of null (reading 'digest')` at `next-server.prod.js:12:18520` |
| **Impact** | Every SSR page request crashes the Next.js server process, frontend unusable |
| **Affected Files** | `frontend/` (likely `next-auth` or crypto hash call in a page/component) |
| **Fix Strategy** | Guard `crypto.subtle` usage to client-side only; add polyfill; or downgrade next-auth |

## Issue #EO-002: Google Gemini Provider Degraded

| Field | Detail |
|-------|--------|
| **Severity** | P1 |
| **Component** | `providers/google_gemini.py` |
| **Root Cause** | API quota exhausted (10/10 consecutive 429s) |
| **Evidence** | `Skipping unhealthy provider google_gemini: 10/10 recent failures` |
| **Impact** | Primary provider skipped; increased load on NVIDIA NIM |
| **Fix Strategy** | Monitor quota; enable billing; implement smarter circuit breaker |

## Issue #EO-003: NVIDIA NIM 404 Errors

| Field | Detail |
|-------|--------|
| **Severity** | P1 |
| **Component** | `providers/nvidia_nim.py` |
| **Root Cause** | Requested model slug not found at `integrate.api.nvidia.com/v1/chat/completions` |
| **Evidence** | Multiple `HTTP/1.1 404 Not Found` in logs |
| **Impact** | Wasted requests, unnecessary latency |
| **Fix Strategy** | Endpoint/model rotation (already applied in commit f94e0c6) |

## Issue #EO-004: NVIDIA NIM 429 Rate Limiting

| Field | Detail |
|-------|--------|
| **Severity** | P1 |
| **Component** | `providers/nvidia_nim.py` |
| **Root Cause** | Too many requests to free/limited NVIDIA NIM tier |
| **Evidence** | Hundreds of `HTTP/1.1 429 Too Many Requests` |
| **Impact** | Queue backs up, slow pipeline |
| **Fix Strategy** | Reduce concurrency; add per-provider rate limits; use tiered keys |

## Issue #EO-005: Raw Prompt Leakage (Fixed)

| Field | Detail |
|-------|--------|
| **Severity** | P0 (was P0, now fixed) |
| **Component** | `pipeline/discovery.py` |
| **Root Cause** | `target_domain` config parameter received full 1281-char raw prompt instead of short domain. `_generate_search_queries()` concatenated sanitized query with raw prompt. |
| **Evidence** | GitHub API returning `422 Unprocessable Entity`; PubMed/ArXiv returning `429 Too Many Requests`; URLs contained `Dataset+Name%3A`, `Goal%3A` |
| **Impact** | All search engines rate-limiting/banning long abusive queries. Pipeline jobs stalled in discovery. |
| **Fix Applied** | Commit `0910c8ac` + `570f56f1`: Hardened `target_domain` guard; removed dangerous strip prefixes; capped queries at ≤100 chars; tightened LLM prompt. |
| **Verification** | URLs now short and clean; no `Dataset Name:` in any request log. |

## Issue #EO-006: Qdrant False Unhealthy (Fixed)

| Field | Detail |
|-------|--------|
| **Severity** | P2 |
| **Component** | `docker-compose.yml` qdrant healthcheck |
| **Root Cause** | `qdrant/qdrant:latest` image has no `curl` binary. Healthcheck used `CMD curl -f ...`. |
| **Evidence** | `OCI runtime exec failed: exec: "curl": executable file not found in $PATH` |
| **Fix Applied** | Commit `da8d6b92`: Removed unsupported curl check. Container shows `Up` status correctly. |

## Issue #EO-007: Redis/Postgres Exposed (Fixed)

| Field | Detail |
|-------|--------|
| **Severity** | P0 — Security |
| **Component** | `docker-compose.yml` port bindings |
| **Root Cause** | Redis (`0.0.0.0:6379`) and Postgres (`0.0.0.0:5432`) exposed to any IP. |
| **Evidence** | Redis logs: `SECURITY ATTACK detected`; UFW allowed all connections. |
| **Fix Applied** | Commit `da8d6b92`: Changed to `127.0.0.1:6379:6379` and `127.0.0.1:5432:5432`. |
