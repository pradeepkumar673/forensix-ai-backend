# ForensiX AI — Neural Forensic Frontend (Vite)

Production-grade cyber-forensic operator shell for the FastAPI backend in `forensix-ai-backend/`. This client maps **every** versioned router under `/api/v1` (`upload`, `analyze`, `correlate`, `risk`, `assistant`, `report`) plus system probes (`/health`, `/status/models`, `/api/v1/status`).

## Stack

| Layer | Choice |
|--------|--------|
| Runtime | React 18 + TypeScript |
| Bundler | Vite 6 |
| Routing | React Router 6 |
| Server state | TanStack Query v5 |
| Client state | Zustand (+ `persist` for cases & sessions) |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) |
| Components | Existing shadcn/Radix kit in `components/ui/` |
| Motion | Framer Motion |
| Graph | `@xyflow/react` (Knowledge Graph showcase) |
| Body twin | Konva + `react-konva` (Digital Autopsy Lab) |
| Charts | Recharts + Chart.js |

## Prerequisites

1. **Backend** running (default `http://127.0.0.1:8000`). From the backend repo: install Python deps and `uvicorn` per that project’s README.
2. Ensure backend **CORS** includes your frontend origin (`http://localhost:5173` during `npm run dev`). This is configured in `forensix-ai-backend` via `CORS_ORIGINS`.
3. **Node.js 18+** and npm.

## Setup

```bash
cd forensix-ai-frontend
cp .env.example .env
# edit .env → VITE_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Production bundle:

```bash
npm run build
npm run preview   # serves ./dist locally
```

## Environment

| Variable | Meaning |
|-----------|---------|
| `VITE_API_BASE_URL` | FastAPI root (**no** `/api/v1` suffix). Defaults to `http://127.0.0.1:8000` if unset.

## Backend integration cheatsheet

- **Models / LLM routing**: GET `/status/models` → surfaced in **Model Status Rail** (`llm_provider: featherless | ollama`, vision/audio flags, warmed HF checkpoints).
- **Uploads**: `POST /api/v1/upload/report|images|digital-evidence|statements`.
- **Analysis**: report + time-of-death JSON, bulk images, `/analyze/combined`, vision (`segmentation`, `pose`, `tampering`), audio stress/transcribe.
- **Correlation**: timeline build/fetch, knowledge graph build/fetch/metrics/HTML, contradiction sweep, timeline validation.
- **Risk**: `/risk/score|anomalies|contradictions|leads|full`.
- **Oracle**: `/assistant/chat` (+ SSE stream endpoint wired for future use).
- **Reports**: `/api/v1/report/generate` returns **PDF blob**; `/report/list` + `/report/download/{file}` linked in **Report Forge**.

Errors are normalized into in-universe copy via `ForensicApiError` (e.g. “Neural analysis mesh offline…” for 503-class faults).

## Case IDs

FastAPI endpoints expect **`case_id` UUIDs**. The frontend **Case Matrix** (Zustand + `localStorage`) issues valid `crypto.randomUUID()` values — set **Active lock** before hitting analysis/correlation forms so query params align with backend envelopes.

## Operator UX

| Shortcut | Action |
|----------|--------|
| `⌘/Ctrl + K` | Neural command palette (route jumps) |
| `⌘/Ctrl + Enter` | Toggle **Forensic Oracle** sheet |
| Persistent orb | Opens Oracle while collapsed |

Dark “obsidian lab” visuals live in `src/index.css`: glass panels, holographic trims (`holo-edge`), scanlines utility, neon + **crimson `#991b1b`** accents, Inter / Space Grotesk / JetBrains Mono.

## Project map (high-signal)

```
components/
  ui/               # shadcn primitives (subset excluded from TSC if unused)
  graph/KnowledgeGraphBoard.tsx   # xyflow constellation
  lab/BodyMapTwin.tsx             # Konva anterior/posterior twin
  oracle/OraclePanel.tsx          # Assistant UX
hooks/useGlobalShortcuts.ts
lib/api.ts                       # Axios wrappers for FastAPI surface
pages/                           # Routed screens (Login … Report Forge)
providers/AppProviders.tsx       # TanStack Query client
stores/case-store.ts             # Dossiers
stores/session-store.ts          # Operator + assistant session ids
src/main.tsx · src/App.tsx · src/index.css
```

## Troubleshooting

- **`/openapi.json` 404**: backend ships docs only when `DEBUG=true`.
- **`OPTIONS` failures**: widen `CORS_ORIGINS`.
- **`422` UUID errors**: pick an active dossier or paste a UUID in lab/workspace forms.
- **Graph build succeeds but XYFlow empty**: POST `/correlate/graph` returns a summary envelope — the UI hydrates via GET `/correlate/graph/{case_id}` immediately after ingestion.

---

ForensiX — *NEXUS-9 workstation build.* Chain integrity starts at the ingress layer.
