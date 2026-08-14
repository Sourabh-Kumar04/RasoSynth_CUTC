# ADR-003: Dependency Injection Container for Enterprise Service Management

**Status**: Accepted
**Date**: 2026-05-13
**Deciders**: Platform Team

### Context

The current implementation uses global mutable state (`router`, `orchestrator`, `db`, etc.) in `api/server.py`. This introduces:
- Race conditions in async contexts
- Testing complexity
- Hidden shared dependencies
- Lifecycle management issues
- Inconsistent initialization order

### Decision

Implemented a dependency injection container in `core/di/container.py`:

1. **ServiceContainer** class with:
   - Singleton, scoped, and transient lifetime management
   - Constructor injection for all dependencies
   - Circular dependency detection
   - Async-safe initialization
   - Graceful shutdown handling

2. **Application Factory** in `core/di/factory.py`:
   - Environment-aware app initialization
   - Modular startup lifecycle
   - Service registration and bootstrapping

3. **Lifecycle Management**:
   - Startup: Services initialized in dependency order
   - Shutdown: Cleanup callbacks executed in reverse order

### Consequences

- **Positive**:
  - Deterministic service initialization
  - Testable with mock services
  - Clear dependency graph
  - Async-safe operations
  - Proper resource cleanup

- **Negative**:
  - Additional abstraction layer
  - Learning curve for developers

- **Mitigation**:
  - Comprehensive documentation
  - Clear factory patterns

---

## ADR-004: Enterprise Observability with OpenTelemetry and Correlation IDs

**Status**: Accepted
**Date**: 2026-05-13
**Deciders**: Platform Team

### Context

Observability was limited to basic structured logging. Enterprise deployment requires:
- Distributed tracing across async boundaries
- Request correlation for debugging
- Provider-level performance metrics
- Circuit breaker state tracking
- Production debugging capabilities

### Decision

Enhanced observability in `core/observability.py`:

1. **OpenTelemetry Integration**:
   - Tracer provider with resource attributes
   - Span exporters (console, OTLP)
   - Trace context propagation

2. **Correlation ID System**:
   - `correlation_id_var` context variable
   - `trace_id_var` and `span_id_var` for trace context
   - Propagation across async boundaries

3. **Structured Logging Enhancement**:
   - Custom renderer with correlation fields
   - Service and environment metadata
   - JSON output format

4. **Decorators and Context Managers**:
   - `@traced` decorator for automatic span creation
   - `TracingContext` for manual tracing
   - `get_correlation_id()` for access

### Consequences

- **Positive**:
  - Full distributed trace visibility
  - Request-level debugging
  - Provider performance analysis
  - Production incident debugging

- **Negative**:
  - Additional overhead for tracing
  - OTLP endpoint required for production

- **Mitigation**:
  - Configurable via environment variables
  - Console exporter for development

---

## ADR-005: Enterprise Validation Framework with Security Hardening

**Status**: Accepted
**Date**: 2026-05-13
**Deciders**: Platform Team

### Context

Current API schemas lack deep validation, injection prevention, and semantic constraints needed for enterprise deployment.

### Decision

Created comprehensive validation in `core/validation/`:

1. **Security Validators** (`validators.py`):
   - Prompt injection detection
   - SQL injection prevention
   - Path traversal protection
   - HTML sanitization

2. **Custom Pydantic Types**:
   - `StrictString`: Injection-safe strings
   - `SafeFilename`: Path-safe filenames
   - `DomainName`: Validated domains
   - `LanguageCode`: ISO 639-1 codes
   - `ValidURL`: URL format validation

3. **Constraint Validation** (`limits.py`):
   - Dataset size limits
   - Budget constraints
   - Request body limits
   - Resource constraints

### Consequences

- **Positive**:
  - Comprehensive input validation
  - Security vulnerability prevention
  - Clear error messages

- **Negative**:
  - Additional validation overhead

---

## ADR-006: Provider Health Monitoring Framework

**Status**: Accepted
**Date**: 2026-05-13
**Deciders**: Platform Team

### Context

Provider reliability is critical for autonomous dataset generation. Need proactive health monitoring with circuit breaker integration.

### Decision

Implemented provider health monitoring in `core/health/__init__.py`:

1. **ProviderHealthMonitor**:
   - Periodic health checks
   - Latency tracking
   - Circuit breaker state management
   - Quota monitoring
   - Fallback event tracking

2. **ProviderMetrics**:
   - Request counts, success rates
   - Latency percentiles
   - Cost tracking
   - Fallback frequency

3. **Health Check Endpoints**:
   - `/health` - Liveness
   - `/health/ready` - Readiness with provider status

### Consequences

- **Positive**:
  - Proactive failure detection
  - Provider performance visibility
  - Automated circuit breaker

- **Negative**:
  - Additional monitoring overhead