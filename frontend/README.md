# RasoDataset-Agent - Frontend Platform

Enterprise-grade AI-native frontend for autonomous dataset generation and orchestration.

## Features

- **AI Dataset Generation Studio** - Natural language dataset creation with AI-assisted configuration
- **Real-Time Orchestration Dashboard** - Live workflow monitoring with animated DAG visualization
- **Multi-Provider Management Console** - Provider health, latency, and cost analytics
- **Dataset Explorer** - Browse, validate, and export generated datasets
- **Observability Dashboard** - System metrics, traces, and log aggregation
- **Research & Benchmarking** - Provider performance analysis and quality tracking

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **UI**: React 18 + TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: Zustand (global) + TanStack Query (server)
- **Charts**: Recharts + Tremor
- **Animations**: Framer Motion

## Getting Started

### Prerequisites

- Node.js 18+
- pnpm or npm

### Installation

```bash
cd frontend
pnpm install
```

### Development

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000)

### Build

```bash
pnpm build
pnpm start
```

## Project Structure

```
frontend/
├── app/                    # Next.js app router
│   ├── (dashboard)/       # Main app layout group
│   │   ├── studio/       # Dataset generation studio
│   │   ├── orchestration/ # Workflow monitoring
│   │   ├── datasets/     # Dataset explorer
│   │   ├── providers/     # Provider management
│   │   ├── observability/ # Metrics & traces
│   │   ├── research/      # Benchmarking
│   │   └── settings/      # Configuration
│   └── layout.tsx         # Root layout
├── components/
│   ├── ui/               # Base UI components
│   ├── layout/           # Layout components
│   └── */               # Feature-specific components
├── lib/
│   ├── api/             # API client
│   ├── stores/          # Zustand stores
│   ├── hooks/           # Custom hooks
│   └── utils/           # Utilities
└── types/               # TypeScript types
```

## Environment Variables

Create `.env.local` based on `.env.local.example`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Key Pages

| Route | Description |
|-------|-------------|
| `/orchestration` | Real-time workflow monitoring dashboard |
| `/studio` | AI-powered dataset generation workspace |
| `/datasets` | Dataset explorer and validation |
| `/providers` | Multi-provider management console |
| `/observability` | System metrics and tracing |
| `/research` | Provider benchmarking and experiments |
| `/settings` | Platform configuration |

## Design System

- **Theme**: Dark-first with AI-native accents
- **Colors**: Indigo primary (#6366f1), success green, warning amber, error red
- **Typography**: Inter for UI, JetBrains Mono for code
- **Components**: Based on shadcn/ui with custom styling

## API Integration

The frontend integrates with the backend via:

- **REST API** via `lib/api/client.ts`
- **SSE Streaming** via `lib/api/sse.ts`
- **TanStack Query** hooks via `lib/hooks/use-api.ts`

## License

MIT
