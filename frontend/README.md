# RasoSynthTune — Frontend

Next.js dashboard for the RasoSynthTune autonomous dataset synthesis and fine-tuning platform.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui (Radix primitives)
- **State**: Zustand (global) + TanStack Query (server state)
- **Charts**: Recharts
- **Animations**: Framer Motion
- **Package manager**: pnpm

## Getting Started

```bash
cd frontend
pnpm install
pnpm dev        # http://localhost:3000
```

### Environment

```bash
cp .env.local.example .env.local
# Set:
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Production Build

```bash
pnpm build
pnpm start
```

## Pages

| Route | Description |
|-------|-------------|
| `/orchestration` | Real-time workflow monitoring with animated DAG |
| `/studio` | AI-powered dataset generation workspace |
| `/quality` | Dataset quality dashboard — scores, diversity, hallucination |
| `/datasets` | Dataset explorer, validation, and export |
| `/finetune` | **Fine-Tune Studio** — launch PEFT/LoRA jobs, live loss chart, training log stream |
| `/review` | **Human Review Queue** — approve/reject/edit samples, keyboard shortcuts, bulk actions |
| `/providers` | Multi-provider health, latency, and cost analytics |
| `/observability` | System metrics, traces, and log aggregation |
| `/research` | Provider benchmarking and prompt optimization |
| `/settings` | Platform configuration |

## Project Structure

```
frontend/
├── app/
│   ├── (dashboard)/           # Main dashboard layout group
│   │   ├── datasets/          # Dataset explorer
│   │   ├── finetune/          # Fine-Tune Studio
│   │   ├── observability/     # Metrics & traces
│   │   ├── orchestration/     # Workflow monitoring
│   │   ├── providers/         # Provider management
│   │   ├── research/          # Benchmarking
│   │   ├── review/            # Human review queue
│   │   ├── settings/          # Configuration
│   │   └── studio/            # Dataset generation
│   ├── quality/               # Quality dashboard
│   ├── layout.tsx             # Root layout
│   └── page.tsx               # Root redirect
├── components/
│   ├── ui/                    # Radix/shadcn base components
│   ├── layout/                # TopNav, Sidebar
│   └── quality/               # Quality chart components
├── lib/
│   ├── api/                   # API client (client.ts)
│   ├── hooks/                 # Custom React hooks
│   ├── stores/                # Zustand stores
│   └── streaming/             # SSE/WebSocket helpers
└── types/
    └── api.ts                 # Shared API type definitions
```

## Design System

- **Theme**: Dark-first (`dark` class on `<html>`)
- **Brand colours**: Orange-500/600 (primary), Indigo/Accent (secondary)
- **Typography**: Inter (UI) · JetBrains Mono (code/logs)
- **CSS variables**: defined in `app/globals.css`, extended in `tailwind.config.ts`
- **Utilities**: `glass`, `glow`, `grid-bg`, `gradient-text`, `gradient-border`

## API Integration

All backend calls go through `lib/api/client.ts` (`APIClient` class):

- **REST** — `api.createFineTuneJob(...)`, `api.getReviewQueue(...)`, etc.
- **WebSocket** — native `WebSocket` for fine-tuning live log stream (`/api/finetune/jobs/{id}/stream`)
- **Demo mode** — toggle in the top nav; all calls fall back to `MockWebSocket` / in-memory data when enabled

## License

[PolyForm Noncommercial License 1.0.0 (CC BY-NC 4.0)](../LICENSE) — Strictly Non-Commercial Use Only.

