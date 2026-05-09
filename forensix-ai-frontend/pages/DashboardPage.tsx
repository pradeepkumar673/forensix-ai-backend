import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from 'recharts'
import { Activity, Cpu, Radar as RadarIcon, ThermometerSun } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ModelStatusRail } from '@/components/telemetry/ModelStatusRail'
import { ShortcutHint } from '@/components/layout/AppShell'
import { NeuralBackdrop } from '@/components/effects/NeuralBackdrop'
import { API_BASE_URL, riskFull } from '@/lib/api'
import { useCaseStore } from '@/stores/case-store'

const anomalySeries = [
  { window: '-18h', anomalies: 14 },
  { window: '-12h', anomalies: 18 },
  { window: '-6h', anomalies: 31 },
  { window: 'now', anomalies: 42 },
]

const radarDemo = [
  { axis: 'Violence', score: 78 },
  { axis: 'Staging', score: 61 },
  { axis: 'Evidence', score: 44 },
  { axis: 'Credibility', score: 71 },
  { axis: 'Weapon', score: 82 },
  { axis: 'Digital', score: 53 },
]

export default function DashboardPage() {
  const cases = useCaseStore((s) => s.cases)
  const active = useCaseStore((s) => s.activeCaseId)

  const riskWarm = useQuery({
    queryKey: ['dashboard-risk-warm'],
    queryFn: async () =>
      riskFull({
        report_text:
          'High-velocity blood spatter documented on north wall. Livor mortis fixed over dependent surfaces.',
        statements: ["I never left the harbour unit before midnight.", 'I was at the clinic until dawn.'],
        evidence_summary: 'Blade consistent with serrated kitchen class. Glass shard on boot sole.',
        timeline_events: [{ t: 'discovery', note: 'Victim found 03:41' }],
        evidence_items: [{ type: 'photo', description: 'north wall', timestamp: '2035-03-11T03:30:00Z' }],
      }),
    staleTime: 60_000,
  })

  type RiskEnvelope = { verdict?: string; overall_risk?: number }
  const envelope = (riskWarm.data as { data?: { risk_score?: RiskEnvelope } } | undefined)?.data?.risk_score
  const verdict = String(envelope?.verdict ?? 'LATENT')
  const gauge = Number(envelope?.overall_risk ?? 64)

  return (
    <div className="relative px-6 py-12 pb-32">
      <NeuralBackdrop className="opacity-[0.22]" />

      <div className="relative z-10 mx-auto max-w-[1540px] space-y-10">
        <header className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-primary/95">Command deck</p>
            <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight text-foreground">
              Global custody awareness
            </h1>
            <p className="mt-3 max-w-2xl font-mono text-sm leading-relaxed text-muted-foreground">
              Mesh root <span className="text-primary">{API_BASE_URL}</span>.{' '}
              <ShortcutHint shortcut="⌘ K">Neural routing palette</ShortcutHint>
            </p>
          </div>
          <Input
            className="h-12 max-w-xl rounded-xl border-primary/65 bg-muted/80 font-mono text-sm"
            placeholder="Vector probe shortcut ( ⌘ K )"
            readOnly
            onFocus={(e) => e.target.blur()}
          />
        </header>

        <ModelStatusRail />

        <div className="grid gap-6 xl:grid-cols-12">
          <motion.section layout className="glass-panel-strong col-span-12 p-10 xl:col-span-7">
            <Badge className="border-accent/70 bg-accent/35 font-mono text-[10px] uppercase text-accent-foreground">
              Incident band warmup
            </Badge>
            <div className="mt-10 grid gap-8 md:grid-cols-12 md:items-end">
              <div className="md:col-span-4">
                <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
                  Composite gauge
                </p>
                <p className="font-display text-[4.85rem] font-semibold tracking-tighter text-primary">
                  {riskWarm.isFetching ? '…' : gauge.toFixed(1)}
                </p>
                <p className="mt-4 font-display text-xs uppercase tracking-[0.55em] text-accent">verdict {verdict}</p>
              </div>
              <div className="h-56 rounded-2xl border border-primary/50 bg-muted/90 p-1 md:col-span-8">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={anomalySeries} margin={{ left: -18, right: 4 }}>
                    <defs>
                      <linearGradient id="anomG" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgb(34,211,238)" stopOpacity={0.9} />
                        <stop offset="100%" stopColor="rgb(153,27,27)" stopOpacity={0.5} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 6" strokeOpacity={0.12} stroke="#22d3ee60" vertical={false} />
                    <XAxis dataKey="window" tick={{ fill: '#9ca3af', fontFamily: 'JetBrains Mono', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ background: '#0f172af2', border: '1px solid rgba(34,211,238,0.35)' }}
                    />
                    <Area type="monotone" dataKey="anomalies" stroke="#f87171" strokeWidth={2} fill="url(#anomG)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </motion.section>

          <Card className="glass-panel-strong col-span-12 border-primary/50 xl:col-span-5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-display">
                <ThermometerSun />
                Incident radar
              </CardTitle>
              <CardDescription>Seeded dimensions — swap with live risk breakdown per dossier.</CardDescription>
            </CardHeader>
            <CardContent className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarDemo}>
                  <PolarGrid stroke="#22d3ee33" />
                  <PolarAngleAxis dataKey="axis" tick={{ fill: '#aab8cf', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
                  <Radar dataKey="score" stroke="#ef4444" fill="#22d3ee35" strokeWidth={2} dot={{ r: 3, stroke: '#22d3ee' }} />
                </RadarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        <section className="glass-panel-strong grid gap-1 overflow-hidden rounded-2xl border border-border/80 p-1 sm:grid-cols-6 lg:grid-cols-12">
          {Array.from({ length: 12 }).map((_, i) => {
            const c = cases[i]
            if (!c) {
              return <div key={`g-${String(i)}`} className="rounded-xl bg-muted/70 p-10" aria-hidden />
            }
            const band =
              c.riskBand === 'critical'
                ? 'bg-accent'
                : c.riskBand === 'high'
                  ? 'bg-orange-600/80'
                  : c.riskBand === 'medium'
                    ? 'bg-amber-500/70'
                    : 'bg-primary/45'
            return (
              <motion.div
                key={c.id}
                initial={{ opacity: 0.3 }}
                animate={{ opacity: 1 }}
                className={`rounded-xl p-8 text-center ${band}`}
              >
                <p className="font-display text-lg font-semibold text-primary-foreground">{c.code.slice(0, 5)}</p>
                <RadarIcon className="mx-auto mt-4 size-4 text-primary-foreground/90" />
              </motion.div>
            )
          })}
        </section>

        <section className="grid gap-6 lg:grid-cols-[7fr_5fr]">
          <Card className="glass-panel-strong rounded-2xl">
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>Recent dossiers</CardTitle>
                <CardDescription>
                  Local custody mesh — each row maps to `case_id` for FastAPI envelopes.
                </CardDescription>
              </div>
              <Badge variant="outline" className="shrink-0 font-mono text-xs">
                {cases.length} open
              </Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              {cases.length === 0 && (
                <p className="font-mono text-sm text-muted-foreground">
                  Cold boot. Create a dossier in <Link className="text-primary underline" to="/cases">Case Matrix</Link>.
                </p>
              )}
              {cases.slice(0, 8).map((c) => (
                <Link key={c.id} to="/cases">
                  <motion.article
                    whileHover={{ x: 4 }}
                    className="flex items-center justify-between rounded-xl border border-transparent bg-muted/75 p-4 transition hover:border-primary/45"
                  >
                    <div>
                      <p className="font-display text-lg">{c.title}</p>
                      <p className="font-mono text-[11px] uppercase text-muted-foreground">{c.code}</p>
                    </div>
                    <Badge>{c.riskBand}</Badge>
                  </motion.article>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card className="glass-panel-strong rounded-2xl border-primary/45">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-display">
                <Cpu />
                Telemetry bus
              </CardTitle>
              <CardDescription>Active UUID lock for downstream POST bodies.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 font-mono text-xs">
              <div>
                <p className="text-muted-foreground">Active case_id</p>
                <p className="mt-2 break-all rounded-lg border border-border/80 bg-muted/80 p-3 text-primary">
                  {active ?? '— select in Case Matrix —'}
                </p>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Activity className="size-4 text-primary" />
                Live risk warm query {riskWarm.isError ? 'degraded' : 'nominal'}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
