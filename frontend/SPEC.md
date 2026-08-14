# RasoDataset-Agent - Frontend Platform Specification

**Version**: 1.0.0
**Architecture**: Enterprise AI-Native Orchestration Platform

---

## 1. Concept & Vision

A production-grade AI-native frontend platform functioning as an **orchestration control center** for autonomous dataset engineering. The interface feels like a blend of Linear's precision, Datadog's observability depth, and LangSmith's AI workflow understanding.

The platform transforms complex distributed AI pipeline management into an intuitive, real-time, collaborative workspace where teams can orchestrate, monitor, and optimize autonomous dataset generation at scale.

---

## 2. Design Language

### Aesthetic Direction
**Reference**: Linear × Datadog × Vercel — dark-first, information-dense, with subtle AI-native flourishes

### Color Palette
```css
--background: #0a0a0f;
--background-secondary: #12121a;
--background-tertiary: #1a1a24;
--surface: #1e1e28;
--surface-hover: #252532;
--border: #2a2a3a;
--border-subtle: #1f1f2a;

--text-primary: #fafafa;
--text-secondary: #a0a0b0;
--text-muted: #606070;

--accent: #6366f1;        /* Indigo - primary actions */
--accent-hover: #818cf8;
--accent-muted: #4f46e5;

--success: #22c55e;
--warning: #f59e0b;
--error: #ef4444;
--info: #3b82f6;

--gradient-start: #6366f1;
--gradient-end: #8b5cf6;
```

### Typography
- **Primary**: Inter (variable)
- **Monospace**: JetBrains Mono (code, metrics)
- **Headings**: Inter, 600-700 weight

### Spatial System
- Base unit: 4px
- Component padding: 12px / 16px / 20px
- Section gaps: 24px / 32px / 48px
- Border radius: 6px (subtle), 8px (cards), 12px (modals)

### Motion Philosophy
- Micro-interactions: 150ms ease-out
- Page transitions: 200ms ease-in-out
- Loading states: Skeleton shimmer
- Real-time updates: Subtle pulse animations
- Charts: 400ms spring transitions

---

## 3. Layout & Structure

### Navigation Architecture
```
┌─────────────────────────────────────────────────────────────┐
│  Logo   │  Studio  │  Orchestration  │  Datasets  │  ⚙️   │
├─────────┴──────────┴─────────────────┴────────────┴────────┤
│ Sidebar │                    Main Content                   │
│  240px  │                   (fluid width)                   │
│         │                                                     │
│ Quick   │  ┌─────────────────────────────────────────────┐  │
│ Actions │  │           Context Header                    │  │
│         │  ├─────────────────────────────────────────────┤  │
│ Recent  │  │                                             │  │
│ Jobs    │  │              Primary View                   │  │
│         │  │                                             │  │
│ Provider│  │                                             │  │
│ Status  │  └─────────────────────────────────────────────┘  │
└─────────┴────────────────────────────────────────────────────┘
```

### Page Hierarchy
1. **Studio** (`/studio`) - Dataset generation workspace
2. **Orchestration** (`/orchestration`) - Workflow monitoring
3. **Datasets** (`/datasets`) - Dataset explorer
4. **Providers** (`/providers`) - Provider management
5. **Observability** (`/observability`) - Metrics & traces
6. **Research** (`/research`) - Benchmarking workspace
7. **Settings** (`/settings`) - Configuration

---

## 4. Core Modules

### 4.1 AI Dataset Generation Studio
**Path**: `/studio`
**Purpose**: Interactive workspace for dataset creation

Features:
- Natural language dataset specification
- Constraint builder with visual forms
- Provider selection with cost estimates
- Real-time schema preview
- Template library
- Workflow simulation

### 4.2 Real-Time Orchestration Dashboard
**Path**: `/orchestration`
**Purpose**: Live workflow monitoring

Features:
- Animated DAG visualization
- Live event stream
- Task timeline view
- Queue depth metrics
- Retry/failure analytics
- Bulkhead status

### 4.3 Multi-Provider Console
**Path**: `/providers`
**Purpose**: Provider management

Features:
- Health overview cards
- Latency/cost charts
- Circuit breaker states
- Routing policies
- Rate limit tracking

### 4.4 Dataset Explorer
**Path**: `/datasets`
**Purpose**: Browse and validate datasets

Features:
- Virtualized table view
- Streaming record preview
- Quality metrics
- Export controls
- Semantic search

### 4.5 Observability Dashboard
**Path**: `/observability`
**Purpose**: System telemetry

Features:
- Real-time metrics charts
- Distributed trace viewer
- Log aggregation
- Alert management

### 4.6 Research Workspace
**Path**: `/research`
**Purpose**: Benchmarking & experiments

Features:
- Experiment comparison
- Provider benchmarks
- Quality analytics

---

## 5. Component Inventory

### Navigation
- `TopNav` - Primary navigation bar
- `Sidebar` - Context-sensitive sidebar
- `CommandPalette` - ⌘K command interface

### Layout
- `PageHeader` - Page title + actions
- `Card` - Content container
- `Tabs` - View switching
- `SplitPane` - Resizable panels

### Data Display
- `DataTable` - Virtualized table
- `MetricCard` - Single metric display
- `Chart` - Recharts wrapper
- `StatusBadge` - State indicator
- `Timeline` - Event timeline
- `WorkflowGraph` - DAG visualization

### Forms
- `Input` - Text input
- `Select` - Dropdown
- `ConstraintBuilder` - Visual constraints
- `SchemaEditor` - JSON schema editor
- `ProviderSelector` - Multi-select providers

### Feedback
- `Skeleton` - Loading placeholder
- `Toast` - Notifications
- `Progress` - Job progress
- `StreamingLog` - Live log viewer

### Real-time
- `EventStream` - SSE handler
- `RealtimeBadge` - Live indicator
- `PulseIndicator` - Activity indicator

---

## 6. Technical Architecture

### Stack
- **Framework**: Next.js 14 (App Router)
- **UI**: React 18 + TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: Zustand (global) + TanStack Query (server)
- **Charts**: Recharts + Tremor
- **Animations**: Framer Motion
- **Forms**: React Hook Form + Zod

### Folder Structure
```
frontend/
├── app/                    # Next.js app router
│   ├── (auth)/           # Auth layout group
│   ├── (dashboard)/      # Main app layout
│   │   ├── studio/
│   │   ├── orchestration/
│   │   ├── datasets/
│   │   ├── providers/
│   │   ├── observability/
│   │   └── research/
│   └── api/              # API routes (if needed)
├── components/
│   ├── ui/              # shadcn components
│   ├── layout/          # Layout components
│   ├── studio/          # Studio module
│   ├── orchestration/    # Orchestration module
│   ├── datasets/         # Dataset module
│   ├── providers/        # Provider module
│   ├── observability/    # Observability module
│   └── research/         # Research module
├── lib/
│   ├── api/             # API client
│   ├── stores/          # Zustand stores
│   ├── hooks/           # Custom hooks
│   ├── utils/           # Utilities
│   └── streaming/       # SSE/WebSocket handlers
├── types/               # TypeScript types
└── public/             # Static assets
```

### API Integration
- **TanStack Query** for REST API
- **SSE** for real-time streams
- **WebSocket** for orchestration events
- Generated types from OpenAPI spec

### Authentication
- NextAuth.js with OAuth2
- JWT session management
- RBAC middleware

---

## 7. State Architecture

### Global Stores (Zustand)
```typescript
// Connection & streaming state
- useConnectionStore    // SSE/WebSocket connections
- useStreamingStore     // Active streams

// UI state
- useSidebarStore       // Sidebar collapse state
- useCommandPaletteStore // ⌘K modal

// Real-time data
- useJobStore          // Active jobs
- useMetricsStore     // Real-time metrics
- useProviderStore     // Provider states
```

### Server State (TanStack Query)
```typescript
// Query keys
- ['datasets']         // Dataset list
- ['dataset', id]      // Single dataset
- ['jobs']             // Job list
- ['job', id]          // Single job
- ['providers']        // Provider list
- ['metrics']          // Prometheus metrics
```

---

## 8. Streaming Architecture

### SSE Endpoints
```
GET /api/v1/stream/jobs/{job_id}/events
GET /api/v1/stream/orchestration
GET /api/v1/stream/metrics
```

### Event Types
```typescript
type StreamEvent =
  | { type: 'JOB_PROGRESS'; data: JobProgress }
  | { type: 'JOB_COMPLETE'; data: JobResult }
  | { type: 'JOB_ERROR'; data: Error }
  | { type: 'METRIC_UPDATE'; data: Metrics }
  | { type: 'PROVIDER_STATUS'; data: ProviderHealth }
  | { type: 'TRACE_EVENT'; data: Trace }
```

---

## 9. Performance Strategy

### Rendering
- Route-based code splitting
- React.lazy for heavy components
- Suspense boundaries
- Streaming SSR

### Data Fetching
- TanStack Query caching
- Infinite queries for lists
- Optimistic updates
- Background refetch

### Virtualization
- react-virtual for large lists
- Windowed rendering
- Intersection Observer

### Bundle
- Dynamic imports
- Tree shaking
- Edge runtime where possible
