# ForensiX AI — Neural Forensic Frontend

Production **dark-only** intelligence workspace for the **ForensiX FastAPI** backend.

**Stack:** React 18 · Vite · TypeScript · Tailwind CSS v4 · shadcn/ui (Radix) · Framer Motion 11 · TanStack Query v5 · Zustand · React Router v6.4+ · React Flow · Recharts · Konva · Lucide · Sonner.

**Charts:** Recharts powers gauges/radar/areas. **`@tremor/react`** targets Tailwind v3; this repo ships **`FxMetric`** — Tremor-equivalent metric tiles fully compatible with Tailwind v4.

---

## 1. Folder structure

```
forensix-ai-frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── components.json          # shadcn/ui
├── .env.example
├── public/
└── src/
    ├── main.tsx
    ├── index.css            # Design tokens, glass/scanline utilities
    ├── app/
    │   ├── providers.tsx    # QueryClient + Sonner
    │   ├── router.tsx       # createBrowserRouter routes
    │   ├── RequireAuth.tsx
    │   └── ShortcutsRoot.tsx
    ├── components/
    │   ├── command/         # ⌘K NeuralCommandPalette
    │   ├── dashboard/       # RiskGaugeCard (Recharts donut)
    │   ├── effects/         # CyberBackdrop, ScanningOverlay
    │   ├── lab/             # DigitalAutopsyLab, BodyMapStage (Konva twin)
    │   ├── layout/          # AppShell, Sidebar, TopBar
    │   ├── metrics/         # FxMetric (Tremor-style tiles)
    │   ├── oracle/          # ForensicOracle (assistant sheet)
    │   ├── ui/              # shadcn primitives
    │   ├── vault/           # EvidenceVaultDropzone
    │   └── workspace/       # KnowledgeGraphBoard, TimelineVertical
    ├── hooks/               # Keyboard shortcuts, responsive helpers
    ├── lib/
    │   ├── api.ts           # Axios clients → /api/v1/*
    │   ├── forensic-errors.ts
    │   ├── query-keys.ts
    │   └── utils.ts
    ├── pages/
    │   ├── LoginPage.tsx
    │   ├── DashboardPage.tsx
    │   ├── CasesPage.tsx
    │   ├── NewCasePage.tsx
    │   ├── VaultPage.tsx
    │   ├── LabPage.tsx
    │   ├── WorkspacePage.tsx
    │   └── ReportForgePage.tsx
    └── stores/
        ├── auth-store.ts
        ├── case-store.ts
        └── ui-store.ts
```

---

## 2. Setup instructions

```bash
cd forensix-ai-frontend
npm install
cp .env.example .env.local   # optional
npm run dev
```

- Dev UI: **http://localhost:5173**
- Production bundle:

```bash
npm run build && npm run preview
```

Typecheck only:

```bash
npm run lint
```

---

## 3. Connect to the backend

1. Run the API from **`forensix-ai-backend`** (example):

   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. Set **`VITE_API_BASE_URL`** in `.env.local` to that origin (default `http://127.0.0.1:8000`).

3. **CORS:** With the backend on `127.0.0.1` and Vite on `localhost`, enable the API’s dev CORS behavior (e.g. **`DEBUG=true`** so `allow_origin_regex` matches localhost / 127.0.0.1), or add explicit origins in **`CORS_ORIGINS`**.

4. Readiness and models:

   - `GET /health`, `GET /ready`, `GET /status/models`, `GET /api/v1/status`

5. Case dossiers are **persisted in the browser** (Zustand `persist`). Select an active case in the **top bar** before vault / lab / workspace flows.

---

## 4. Major components & surfaces

| Area | Components / behavior |
|------|----------------------|
| **Auth** | `LoginPage` — biometric-style ingress + optional access token |
| **Shell** | `AppShell`, `Sidebar`, `TopBar`, `CyberBackdrop`, `ScanningOverlay` |
| **Dashboard** | `RiskGaugeCard`, `FxMetric`, dossier table, readiness/model queries |
| **Cases** | `CasesPage`, `NewCasePage` — filters + rich metadata |
| **Vault** | `EvidenceVaultDropzone` — MIME-aware uploads + TanStack mutations |
| **Digital lab** | `DigitalAutopsyLab`, `BodyMapStage` — tabs, Konva twin, zoom/pan/measure, wound selection + inspector, vision API hooks |
| **Workspace** | Report highlights, `TimelineVertical`, `KnowledgeGraphBoard`, audio stress/transcribe, risk radar (Recharts) |
| **Oracle** | `ForensicOracle` — `/assistant/chat`, markdown, prompt chips |
| **Report forge** | `ReportForgePage` — preview + `POST /api/v1/report/generate` PDF download |
| **Navigation** | `NeuralCommandPalette` (⌘K), keyboard shortcuts in `ShortcutsRoot` / hooks |

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| **⌘/Ctrl + K** | Neural command palette |
| **⌥ + D** | Dashboard |
| **⌥ + L** | Digital autopsy lab |
| **⌥ + W** | Intelligence workspace |

---

© ForensiX — demonstration UX; align with your agency accreditation and evidence-handling policy before operational deployment.
