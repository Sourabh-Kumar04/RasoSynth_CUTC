# Production Operations Runbooks

Complete operational runbooks for RasoDataset-Agent platform.

---

## Table of Contents

1. [Provider Outage Response](#1-provider-outage-response)
2. [Database Failure Recovery](#2-database-failure-recovery)
3. [Redis/Cache Failure](#3-rediscache-failure)
4. [Memory Leak Detection](#4-memory-leak-detection)
5. [Event Loop Starvation](#5-event-loop-starvation)
6. [Circuit Breaker Alert Response](#6-circuit-breaker-alert-response)
7. [Deployment Rollback](#7-deployment-rollback)
8. [Orchestration Deadlock](#8-orchestration-deadlock)
9. [Streaming Failure](#9-streaming-failure)
10. [Retry Storm](#10-retry-storm)
11. [Connection Pool Exhaustion](#11-connection-pool-exhaustion)
12. [Scaling Incident](#12-scaling-incident)
13. [Security Incident](#13-security-incident)

---

## 1. Provider Outage Response

### Symptoms
- High error rate on provider API calls (5xx)
- Circuit breakers opening
- Increased latency on affected provider
- Failed dataset generation jobs

### Diagnosis

```bash
# Check circuit breaker status
curl -s http://localhost:8000/api/v2/metrics | jq '.circuit_breakers'

# Check provider health
curl -s http://localhost:8000/api/v2/providers

# Review error logs
grep "provider" /var/log/ai-dataset-engineer/error.log | tail -100
```

### Severity Classification

| Severity | Impact | Response Time |
|----------|--------|---------------|
| P1 | All providers down | Immediate |
| P2 | Single provider down | < 15 min |
| P3 | Degraded performance | < 1 hour |
| P4 | Intermittent issues | < 4 hours |

### Mitigation Steps

1. **Identify affected provider**
   ```bash
   # Check which provider is failing
   grep "ProviderError" /var/log/ai-dataset-engineer/error.log | head -20
   ```

2. **Enable fallback routing**
   ```python
   # Configure fallback providers in config
   provider_priority: ["nvidia_nim", "anthropic_claude", "google_gemini"]
   ```

3. **Increase circuit breaker timeout**
   ```bash
   # Via runtime config
   curl -X POST http://localhost:8000/api/v2/config/circuit-breaker \
     -d '{"provider": "google", "timeout_seconds": 120}'
   ```

4. **Monitor fallback performance**
   ```bash
   # Watch metrics
   watch -n 5 'curl -s http://localhost:8000/api/v2/metrics'
   ```

### Recovery Steps

1. Monitor provider status pages
2. When provider recovers, gradually increase traffic
3. Reset circuit breaker: `POST /api/v2/config/circuit-breaker/reset`
4. Verify job completion rates normalize

### Escalation
- P1: Immediately page on-call, notify Slack #incidents
- P2: Notify Slack #platform, begin mitigation
- P3/P4: Handle during business hours

---

## 2. Database Failure Recovery

### Symptoms
- High query latency (>5s)
- Connection pool exhaustion
- "too many connections" errors
- Orchestration pipelines stalled

### Diagnosis

```bash
# Check database metrics
psql -h localhost -U postgres -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Check connection count
psql -h localhost -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check for long-running queries
psql -h localhost -U postgres -c "SELECT pid, duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC LIMIT 10;"
```

### Mitigation Steps

1. **Identify blocking queries**
   ```sql
   SELECT pg_blocking_pids(pid) as blocked_by, query FROM pg_stat_activity WHERE state = 'active';
   ```

2. **Terminate long-running queries** (if safe)
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '10 minutes';
   ```

3. **Scale connection pool** (temporary)
   ```bash
   # Edit max_connections in postgresql.conf or runtime
   ALTER SYSTEM SET max_connections = 200;
   ```

4. **Enable connection pooling**
   ```bash
   # Ensure PgBouncer is running
   systemctl status pgbouncer
   ```

### Recovery Steps

1. Monitor query performance
2. Verify connection count stabilizes
3. Check orchestration pipelines resume
4. Review slow query logs for root cause

---

## 3. Redis/Cache Failure

### Symptoms
- Increased database load
- Higher API latency
- Cache hit rate drops to 0%
- "Redis connection error" in logs

### Diagnosis

```bash
# Check Redis connectivity
redis-cli ping

# Check memory usage
redis-cli info memory

# Check for evicted keys
redis-cli info stats | grep evicted
```

### Mitigation Steps

1. **Verify Redis is running**
   ```bash
   systemctl status redis
   ```

2. **Check Redis logs**
   ```bash
   tail -100 /var/log/redis/redis.log
   ```

3. **Temporarily disable caching** (if Redis unavailable)
   ```bash
   # Set environment variable
   export CACHE_ENABLED=false
   systemctl restart ai-dataset-engineer
   ```

4. **Manual cache warmup** (after recovery)
   ```bash
   curl -X POST http://localhost:8000/api/v2/cache/warm
   ```

### Recovery Steps

1. Verify Redis healthy: `redis-cli ping`
2. Gradually re-enable caching
3. Monitor cache hit rate recovering
4. Warm cache with frequently accessed data

---

## 4. Memory Leak Detection

### Symptoms
- Memory usage continuously increasing
- OOM killer triggering
- Worker pods restarting
- Garbage collection overhead visible

### Diagnosis

```bash
# Check memory usage
ps aux | grep python | grep -v grep

# Use py-spy for profiling
py-spy top --pid $(pgrep -f "uvicorn")

# Check for memory growth pattern
curl -s http://localhost:8000/metrics | grep "process_resident_memory"
```

### Mitigation Steps

1. **Restart affected workers**
   ```bash
   kubectl rollout restart deployment/ai-dataset-engineer
   ```

2. **Force garbage collection** (temporary)
   ```python
   import gc
   gc.collect()
   ```

3. **Enable memory profiling**
   ```bash
   export PYTHONTRACEMALLOC=1
   export MEMORY_PROFILE=1
   ```

4. **Reduce batch sizes** (temporary)
   ```bash
   # Reduce concurrent processing
   export MAX_CONCURRENT_JOBS=5
   ```

### Recovery Steps

1. Identify leak source via profiling
2. Fix code or patch
3. Deploy fix
4. Monitor memory stability

---

## 5. Event Loop Starvation

### Symptoms
- API requests timing out
- Health checks failing
- Background tasks not completing
- High CPU but low throughput

### Diagnosis

```bash
# Check for blocking operations
grep -r "time.sleep" /opt/ai-dataset-engineer/ | grep -v async

# Profile async execution
python -c "
import asyncio
import time
start = time.time()
loop = asyncio.new_event_loop()
for _ in range(1000):
    loop.run_until_complete(asyncio.sleep(0))
print(f'1000 iterations: {time.time() - start:.2f}s')
"

# Check event loop lag
curl -s http://localhost:8000/metrics | grep event_loop_lag
```

### Mitigation Steps

1. **Identify blocking calls**
   ```python
   # Add to app startup
   import asyncio
   from asyncio import running_loop
   loop = running_loop()
   loop.set_debug(True)
   loop.slow_callback_duration = 0.1
   ```

2. **Restart service**
   ```bash
   systemctl restart ai-dataset-engineer
   ```

3. **Reduce concurrency**
   ```bash
   export UVICORN_WORKERS=2  # Reduce from 4
   systemctl restart ai-dataset-engineer
   ```

### Prevention
- Never use `time.sleep()` in async code
- Always use `asyncio.sleep()` or `await asyncio.sleep()`
- Profile async code before deployment

---

## 6. Circuit Breaker Alert Response

### Symptoms
- Alert: "Circuit breaker OPEN for provider X"
- High error rate on specific provider
- Fallback providers receiving extra load

### Diagnosis

```bash
# Check circuit breaker state
curl -s http://localhost:8000/api/v2/metrics | jq '.circuit_breakers'

# Review recent errors
grep "circuit" /var/log/ai-dataset-engineer/error.log | tail -50
```

### Mitigation Steps

1. **Identify provider health**
   ```bash
   curl -s http://localhost:8000/api/v2/providers/{provider}/health
   ```

2. **Check if issue is transient**
   - Look for rate limit responses (429)
   - Check provider status page

3. **Manual circuit breaker reset** (if provider recovered)
   ```bash
   curl -X POST http://localhost:8000/api/v2/config/circuit-breaker/reset \
     -d '{"provider": "google"}'
   ```

4. **Increase threshold** (if pattern is false positive)
   ```bash
   curl -X POST http://localhost:8000/api/v2/config/circuit-breaker \
     -d '{"provider": "google", "failure_threshold": 10}'
   ```

### Recovery Steps

1. Provider health restored
2. Monitor error rate decreasing
3. Verify fallback traffic decreasing
4. Reset circuit breaker when stable

---

## 7. Deployment Rollback

### Prerequisites
- Previous deployment version identified
- Database migrations are reversible (or no migrations)

### Rollback Steps

```bash
# 1. Identify current version
kubectl get deployment ai-dataset-engineer -o jsonpath='{.spec.template.spec.containers[0].image}'

# 2. Get deployment history
kubectl rollout history deployment/ai-dataset-engineer

# 3. Rollback to previous version
kubectl rollout undo deployment/ai-dataset-engineer

# 4. Verify rollback
kubectl rollout status deployment/ai-dataset-engineer

# 5. Check application health
curl http://localhost:8000/health
```

### Database Migration Rollback

```bash
# Check migration status
alembic history

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade {revision}
```

### Post-Rollback Validation

```bash
# Run smoke tests
pytest tests/smoke.py -v

# Check error rates
curl -s http://localhost:8000/metrics | jq '.error_rate'

# Verify critical functionality
curl -s http://localhost:8000/api/v2/datasets | jq '.datasets'
```

---

## 8. Orchestration Deadlock

### Symptoms
- Jobs stuck in "running" state indefinitely
- No progress updates
- Cancellation requests ignored
- Worker threads not responding

### Diagnosis

```bash
# Check stuck jobs
curl -s http://localhost:8000/api/v2/orchestration/jobs?status=running

# Check worker threads
ps -eLf | grep python | grep -v grep | wc -l

# Check for deadlocks in logs
grep -i "deadlock\|stuck\|hang" /var/log/ai-dataset-engineer/error.log
```

### Mitigation Steps

1. **Force job cancellation**
   ```bash
   curl -X DELETE http://localhost:8000/api/v2/orchestration/jobs/{job_id}
   ```

2. **Clear job from state**
   ```bash
   # Via admin API
   curl -X POST http://localhost:8000/admin/jobs/force-cleanup \
     -d '{"job_id": "xxx", "reason": "deadlock"}'
   ```

3. **Restart orchestration workers**
   ```bash
   kubectl rollout restart deployment/ai-dataset-engineer-worker
   ```

4. **Check for external dependencies**
   - Provider availability
   - Database connectivity
   - External API access

### Recovery Steps

1. Clear stuck jobs
2. Verify workers healthy
3. Restart orchestration pipeline
4. Monitor for recurrence

---

## 9. Streaming Failure

### Symptoms
- SSE connections dropping
- Clients receiving incomplete data
- "Connection reset" errors
- Streaming throughput dropped

### Diagnosis

```bash
# Check streaming metrics
curl -s http://localhost:8000/metrics | jq '.streaming'

# Check active SSE connections
curl -s http://localhost:8000/api/v2/metrics | jq '.sse_connections'

# Review streaming logs
grep -i "stream\|sse" /var/log/ai-dataset-engineer/error.log | tail -100
```

### Mitigation Steps

1. **Verify network stability**
   ```bash
   ping -c 10 provider-endpoint
   ```

2. **Check client reconnection logic**
   - Review client implementation
   - Ensure heartbeat mechanism active

3. **Increase timeout** (temporary)
   ```bash
   export SSE_TIMEOUT=300
   ```

4. **Disable streaming** (emergency fallback)
   ```bash
   export STREAMING_ENABLED=false
   systemctl restart ai-dataset-engineer
   ```

### Recovery Steps

1. Monitor streaming reconnection success rate
2. Check client receives buffered events
3. Verify data integrity after reconnection

---

## 10. Retry Storm

### Symptoms
- Rapid increase in API calls
- Provider rate limits triggered
- Error rate spiking
- "Too many retries" in logs

### Diagnosis

```bash
# Check retry metrics
curl -s http://localhost:8000/metrics | jq '.retries'

# Review retry pattern
grep "retry" /var/log/ai-dataset-engineer/error.log | tail -200 | \
  awk '{print $5}' | sort | uniq -c | sort -rn

# Check circuit breaker state
curl -s http://localhost:8000/metrics | jq '.circuit_breakers'
```

### Mitigation Steps

1. **Reduce retry aggressiveness**
   ```bash
   export RETRY_POLICY=conservative
   export MAX_RETRIES=1
   systemctl restart ai-dataset-engineer
   ```

2. **Implement exponential backoff**
   ```python
   # Ensure jitter is enabled
   retry_config = {
       "multiplier": 1.5,
       "min": 1,
       "max": 60,
       "jitter": True
   }
   ```

3. **Add circuit breaker for retry storms**
   - Monitor retry rate
   - Open circuit if retry rate > threshold

### Prevention
- Always use jitter in retry delays
- Set reasonable max retry limits
- Monitor retry rate as critical metric

---

## 11. Connection Pool Exhaustion

### Symptoms
- "Connection pool exhausted" errors
- New requests timing out
- Health checks failing
- Database operations blocked

### Diagnosis

```bash
# Check pool metrics
curl -s http://localhost:8000/metrics | jq '.connection_pools'

# Check active connections
psql -h localhost -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check for connection leaks
ps aux | grep postgres | wc -l
```

### Mitigation Steps

1. **Reduce load** (immediate)
   ```bash
   # Scale down workers
   kubectl scale deployment ai-dataset-engineer --replicas=2

   # Or scale up pool
   kubectl set env deployment/ai-dataset-engineer DB_POOL_SIZE=20
   ```

2. **Kill idle connections**
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' 
   AND state_change < NOW() - INTERVAL '10 minutes';
   ```

3. **Restart application** (if connections leaked)
   ```bash
   kubectl rollout restart deployment/ai-dataset-engineer
   ```

### Prevention
- Use connection pooling (PgBouncer)
- Implement connection timeout
- Monitor pool utilization
- Set pool limits per service

---

## 12. Scaling Incident

### Symptoms
- High latency spikes
- Queue depth increasing
- Resource utilization at 100%
- Health check failures

### Diagnosis

```bash
# Check current replicas
kubectl get deployments | grep ai-dataset

# Check resource usage
kubectl top pods | grep ai-dataset

# Check queue depth
curl -s http://localhost:8000/api/v2/metrics | jq '.queue_depth'
```

### Mitigation Steps

1. **Scale horizontally** (immediate)
   ```bash
   kubectl scale deployment ai-dataset-engineer --replicas=10

   # Or use autoscaler
   kubectl autoscale deployment ai-dataset-engineer \
     --min=5 --max=20 --cpu-percent=70
   ```

2. **Scale database** (if bottleneck)
   ```bash
   # Check DB metrics
   # If DB is bottleneck, scale read replicas
   ```

3. **Reduce incoming traffic** (emergency)
   ```bash
   # Enable rate limiting
   export RATE_LIMIT_ENABLED=true
   export RATE_LIMIT_RPS=100
   ```

4. **Queue drain** (if queue-based)
   ```bash
   # Check queue depth
   # Reduce production rate
   # Allow drain
   ```

### Recovery Steps

1. Verify latency returning to normal
2. Monitor queue depth decreasing
3. Scale down when stable
4. Review scaling thresholds

---

## 13. Security Incident

### Symptoms
- Unusual API patterns
- Authentication failures spike
- Suspicious access patterns
- Secret leakage alerts

### Response Steps

1. **Isolate affected systems**
   ```bash
   # Block suspicious IP
   iptables -A INPUT -s {ip} -j DROP

   # Revoke compromised API keys
   curl -X DELETE http://localhost:8000/api/v2/admin/api-keys/{key_id}
   ```

2. **Preserve evidence**
   ```bash
   # Capture logs
   cp /var/log/ai-dataset-engineer/*.log /backup/security-$(date +%Y%m%d)/

   # Capture network traffic
   tcpdump -i eth0 -w /backup/capture-$(date +%Y%m%d).pcap
   ```

3. **Notify security team**
   ```bash
   # Page security on-call
   pagerduty-cli incident create --service=security --severity=high

   # Notify Slack #security
   ```

4. **Rotate secrets**
   ```bash
   # Rotate all API keys
   vault write -f secret/rotate

   # Generate new credentials
   ```

5. **Review access logs**
   ```bash
   grep {suspicious_ip} /var/log/ai-dataset-engineer/access.log
   ```

### Recovery Steps

1. Verify fix deployed
2. Monitor for recurrence
3. Update WAF rules
4. Conduct post-incident review

---

## Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| On-Call Engineer | PagerDuty | Immediate |
| Platform Lead | Slack DM | < 15 min |
| Security Team | #security | Immediate |
| CTO | Slack DM | P1 only |

---

## Post-Incident Actions

For all incidents, complete within 48 hours:

1. Write incident report
2. Identify root cause
3. Create action items
4. Update runbooks
5. Schedule post-mortem

### Incident Report Template

```markdown
# Incident Report: {title}

**Date**: {date}
**Severity**: {P1-P4}
**Duration**: {X minutes}
**Affected**: {systems/users}

## Summary
{description}

## Root Cause
{cause}

## Timeline
- HH:MM - Event
- HH:MM - Alert received
- HH:MM - Mitigation started
- HH:MM - Resolution

## Impact
- Jobs failed: {count}
- Revenue impact: {amount}
- User impact: {description}

## Lessons Learned
{observations}

## Action Items
- [ ] {action} - Owner - Due date
```