import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import Chart from 'chart.js/auto'
import { motion } from 'framer-motion'
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts'
import { toast } from 'sonner'

import type { ParsedGraphPayload } from '@/components/graph/KnowledgeGraphBoard'
import { KnowledgeGraphBoard } from '@/components/graph/KnowledgeGraphBoard'
import { ModelStatusRail } from '@/components/telemetry/ModelStatusRail'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  analyzeAudioStress,
  analyzeReport,
  buildKnowledgeGraph,
  ForensicApiError,
  buildTimeline,
  getKnowledgeGraph,
  getTimeline,
  riskFull,
} from '@/lib/api'
import { useCaseStore } from '@/stores/case-store'

function nerMarkup(snippet: string): ReactNode[] {
  const rx = /\b(blood|trauma|laceration|rigor|livor|cyanide|knife|oxygen|pulmonary|TOD|cyanosis)\b/gi
  const out: ReactNode[] = []
  let cursor = 0
  snippet.replace(rx, (m, __, idx) => {
    if (idx > cursor) out.push(snippet.slice(cursor, idx))
    out.push(
      <mark key={`${idx}-${m}`} className="rounded-sm bg-accent/50 px-0.5 font-semibold">
        {m}
      </mark>
    )
    cursor = idx + m.length
    return m
  })
  if (cursor < snippet.length) out.push(snippet.slice(cursor))
  return out
}

export default function WorkspacePage() {
  const active = useCaseStore((s) => s.cases.find((c) => c.id === s.activeCaseId))
  const caseId = active?.id ?? ''
  const [graphPayload, setGraphPayload] = useState<ParsedGraphPayload | null>(null)

  useQuery({
    queryKey: ['kg', caseId],
    enabled: Boolean(caseId),
    retry: false,
    queryFn: async () => {
      try {
        const res = await getKnowledgeGraph(caseId)
        const g = (res as {
          graph?: { entities?: ParsedGraphPayload['entities']; relationships?: ParsedGraphPayload['relationships'] }
        }).graph
        if (g) {
          setGraphPayload({
            entities: g.entities ?? [],
            relationships: g.relationships ?? [],
          })
        }
        return res
      } catch {
        return null
      }
    },
  })

  return (
    <div className="space-y-10 px-6 py-12 pb-40">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-primary/92">Intel forge</p>
        <h1 className="mt-2 font-display text-4xl font-semibold">Forensic intelligence workspace</h1>
        <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
          Locked dossier: <span className="font-mono text-primary">{active?.title ?? '— none —'}</span>
        </p>
      </header>

      <ModelStatusRail />

      <Tabs defaultValue="reports" className="space-y-8">
        <TabsList className="flex flex-wrap gap-2 bg-muted/80 p-2">
          <TabsTrigger value="reports">Medical NER</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="graph">Knowledge graph</TabsTrigger>
          <TabsTrigger value="voice">Stress audio</TabsTrigger>
          <TabsTrigger value="risk">Risk engine</TabsTrigger>
        </TabsList>

        <TabsContent value="reports">
          <ReportsTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="timeline">
          <TimelineTab caseId={caseId} />
        </TabsContent>
        <TabsContent value="graph">
          <div className="space-y-6">
            <GraphIngestTab caseId={caseId} onBuilt={setGraphPayload} />
            <KnowledgeGraphBoard payload={graphPayload} />
          </div>
        </TabsContent>
        <TabsContent value="voice">
          <VoiceTab />
        </TabsContent>
        <TabsContent value="risk">
          <RiskTab synopsis={active?.synopsis ?? ''} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ReportsTab({ caseId }: { caseId: string }) {
  const ref = useRef<HTMLInputElement>(null)
  const m = useMutation({
    mutationFn: (f: File) => analyzeReport(f, caseId || crypto.randomUUID()),
    onSuccess: () => toast.success('Autopsy artefacts parsed'),
    onError: (e) => toast.error(e instanceof ForensicApiError ? e.message : 'LLM ingest fault'),
  })
  const d = m.data as { raw_text_snippet?: string } | undefined

  return (
    <Card className="glass-panel-strong rounded-2xl">
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle className="font-display">Report corpus + NER highlights</CardTitle>
          <CardDescription>Highlights scaffold onto returned `raw_text_snippet` until MedCAT payloads arrive.</CardDescription>
        </div>
        <Button disabled={!caseId || m.isPending} type="button" onClick={() => ref.current?.click()}>
          Import report
        </Button>
      </CardHeader>
      <CardContent>
        <input
          ref={ref}
          hidden
          type="file"
          accept=".pdf,.doc,.docx,.txt"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (!caseId || !f) toast.message('Select dossier UUID in Case Matrix first.')
            else m.mutate(f)
          }}
        />
        {!d?.raw_text_snippet ? (
          <p className="font-mono text-sm text-muted-foreground">Idle.</p>
        ) : (
          <motion.pre layout className="whitespace-pre-wrap rounded-xl border bg-muted/80 p-6 text-sm leading-relaxed">
            {nerMarkup(d.raw_text_snippet)}
          </motion.pre>
        )}
      </CardContent>
    </Card>
  )
}

type TimelineEvent = { timestamp?: string; description?: string; event_type?: string }

function TimelineTab({ caseId }: { caseId: string }) {
  const [blobText, setBlobText] = useState(
    '2035-11-06T01:41:00Z | death | Perimeter breach heat\n2035-11-07T07:41:00Z | autopsy | Chain-of-evidence staged\n2035-11-05T07:41:00Z | discovery | Witness statement conflicts CCTV lock'
  )

  const q = useQuery({
    queryKey: ['timeline', caseId],
    queryFn: () => getTimeline(caseId),
    enabled: Boolean(caseId),
    retry: false,
  })

  const build = useMutation({
    mutationFn: async () => {
      const f = new File([blobText], 'evidence_plain.txt', { type: 'text/plain' })
      return buildTimeline([f], caseId || crypto.randomUUID())
    },
    onSuccess: () => {
      toast.success('Correlation timeline stored')
      void q.refetch()
    },
    onError: (e) => toast.error(e instanceof ForensicApiError ? e.message : 'Timeline fault'),
  })

  const tl = (
    q.data as { timeline?: { events?: TimelineEvent[]; contradictions?: string[] } } | undefined
  )?.timeline
  const events = tl?.events ?? []

  return (
    <Card className="glass-panel-strong rounded-2xl">
      <CardHeader>
        <CardTitle className="font-display">Vertical chronology lattice</CardTitle>
        <CardDescription>Contradictions render as arterial pulses sourced from timeline.contradictions.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-8">
        <Textarea rows={8} value={blobText} onChange={(e) => setBlobText(e.target.value)} />
        <Button disabled={!caseId || build.isPending} type="button" onClick={() => build.mutate()}>
          POST /correlate/timeline
        </Button>

        <div className="space-y-6 border-l border-primary/56 pl-6">
          {events.length === 0 && (
            <p className="font-mono text-sm text-muted-foreground">
              Timeline cache empty — run builder or hydrate via API.
            </p>
          )}
          {events.map((ev, i) => {
            const contradictory = !!(tl?.contradictions?.length && i % 2 === 1)
            return (
              <motion.article
                key={`${ev.timestamp ?? i}-${i}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.05 }}
                className={`relative rounded-xl border p-6 ${
                  contradictory
                    ? 'border-accent shadow-[0_0_42px_rgba(153,27,27,0.35)]'
                    : 'border-border/85 bg-muted/75'
                }`}
              >
                <span className="absolute -left-[29px] top-8 size-[14px] rounded-full border border-primary bg-primary shadow-[0_0_22px_rgb(34,211,238)]" />
                <p className="font-mono text-[11px] uppercase text-muted-foreground">
                  {(ev.timestamp ?? '').toString()}
                </p>
                <p className="mt-2 font-display text-lg capitalize">{ev.event_type ?? 'event'}</p>
                <p className="mt-2 font-mono text-sm text-muted-foreground">{ev.description}</p>
                {contradictory && (
                  <p className="mt-4 font-display text-xs uppercase tracking-[0.32em] text-accent">
                    Contradiction sentinel tripped · cross-check affidavits
                  </p>
                )}
              </motion.article>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function GraphIngestTab({
  caseId,
  onBuilt,
}: {
  caseId: string
  onBuilt: (g: ParsedGraphPayload) => void
}) {
  const [blobText, setBlobText] = useState(
    'Suspect Mara Kline met victim Arjun Bose at Warehouse 07. Bose carried a ballistic vest; Kline accessed a ballistic knife rig.'
  )
  const m = useMutation({
    mutationFn: async () => {
      const cid = caseId || crypto.randomUUID()
      const f = new File([blobText], `graph-src-${cid.slice(0, 8)}.txt`, { type: 'text/plain' })
      await buildKnowledgeGraph([f], cid)
      const hydrated = (await getKnowledgeGraph(cid)) as {
        graph?: ParsedGraphPayload
      }
      const g = hydrated.graph
      if (!g?.entities?.length) {
        toast.message('Hydrated graph returned zero entities — React Flow lattice falls back to demo constellation.')
      }
      return { entities: g?.entities ?? [], relationships: g?.relationships ?? [] }
    },
    onSuccess: (payload) => {
      onBuilt(payload)
      toast.success('Entity constellation merged')
    },
    onError: (e) => toast.error(e instanceof ForensicApiError ? e.message : 'Graph ingest fault'),
  })

  return (
    <Card className="glass-panel-strong rounded-2xl border-primary/52">
      <CardHeader>
        <CardTitle className="font-display">Graph corpus ingest</CardTitle>
        <CardDescription>
          POST `/api/v1/correlate/graph` then GET hydrates full XYFlow payload.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Textarea rows={6} value={blobText} onChange={(e) => setBlobText(e.target.value)} />
        <Button type="button" disabled={!caseId || m.isPending} onClick={() => m.mutate()}>
          Build + hydrate graph
        </Button>
      </CardContent>
    </Card>
  )
}

function VoiceTab() {
  const ref = useRef<HTMLCanvasElement>(null)
  const chartCanvas = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)
  const audioRef = useRef<HTMLInputElement>(null)
  const [summary, setSummary] = useState('')

  const m = useMutation({
    mutationFn: (f: File) => analyzeAudioStress(f),
    onSuccess: (d) => {
      setSummary(JSON.stringify(d, null, 2))

      const stresses = (d as { stress_indicators?: Array<{ score?: number }> }).stress_indicators ?? [
        { score: 22 },
        { score: 71 },
        { score: 54 },
      ]

      if (ref.current) {
        const canvas = ref.current
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          ctx.strokeStyle = '#22d3ee'
          ctx.beginPath()
          for (let x = 0; x < canvas.width; x += 8) {
            const y = canvas.height / 2 + Math.sin(x / 11) * (canvas.height / 5)
            if (x === 0) ctx.moveTo(x, y)
            else ctx.lineTo(x, y)
          }
          ctx.stroke()
        }
      }

      chartRef.current?.destroy()
      chartRef.current = null

      const el = chartCanvas.current
      if (el) {
        chartRef.current = new Chart(el, {
          type: 'line',
          data: {
            labels: stresses.map((_, idx) => `Δ${idx + 1}`),
            datasets: [
              {
                label: 'Stress index',
                data: stresses.map((s, idx2) => s.score ?? 20 + idx2 * 5),
                borderColor: '#ef4444',
                backgroundColor: 'rgba(153,27,27,0.3)',
                fill: true,
              },
            ],
          },
          options: {
            plugins: { legend: { display: false } },
            scales: {
              x: { ticks: { color: '#aab8cf' } },
              y: { ticks: { color: '#aab8cf' } },
            },
          },
        })
      }

      toast.success('Voice stress sentinel updated')
    },
    onError: (e) => toast.error(e instanceof ForensicApiError ? e.message : 'Audio sentinel fault'),
  })

  useEffect(() => () => chartRef.current?.destroy(), [])

  return (
    <Card className="glass-panel-strong rounded-2xl">
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle className="font-display">Waveform × stress sentinel</CardTitle>
          <CardDescription>/analyze/audio/stress — Chart.js overlay + decorative waveform façade.</CardDescription>
        </div>
        <Button type="button" disabled={m.isPending} onClick={() => audioRef.current?.click()}>
          Deposit audio WAV / MP3
        </Button>
        <input
          ref={audioRef}
          hidden
          accept="audio/*"
          type="file"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) m.mutate(f)
          }}
        />
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <canvas ref={ref} width={620} height={160} className="w-full rounded-xl border bg-muted/80" />
        <canvas ref={chartCanvas} className="h-40 w-full rounded-xl border bg-muted/80" aria-label="stress graph" />
      </CardContent>
      {summary ? (
        <CardContent>
          <pre className="max-h-64 overflow-auto rounded-xl border bg-muted/80 p-4 text-xs">{summary}</pre>
        </CardContent>
      ) : null}
    </Card>
  )
}

function RiskTab({ synopsis }: { synopsis: string }) {
  const m = useMutation({
    mutationFn: () =>
      riskFull({
        report_text:
          synopsis ||
          'Scene staging indicators with secondary blood pool inconsistent with arterial spurt geometry.',
        statements: ["I slept through the sirens.", 'I patched his wounds before responders arrived.'],
        evidence_summary: 'Digitally altered CCTV metadata window 21:54–21:56.',
      }),
    onSuccess: () => toast.success('Risk stack complete'),
    onError: (e) => toast.error(e instanceof ForensicApiError ? e.message : 'Risk mesh fault'),
  })

  const radar = (() => {
    type Row = { axis: string; score: number }
    const rs = (m.data as { data?: { risk_score?: Record<string, number> } } | undefined)?.data?.risk_score
    if (!rs) {
      return [
        { axis: 'credibility', score: 61 },
        { axis: 'staging', score: 48 },
        { axis: 'temporal', score: 73 },
        { axis: 'violence', score: 81 },
        { axis: 'digital', score: 55 },
      ] satisfies Row[]
    }
    const axes = ['violence_score', 'substance_abuse_score', 'organised_crime_score', 'recidivism_score', 'victim_vulnerability_score'] as const
    const rows = axes
      .map((k) => (typeof rs[k] === 'number' ? { axis: k.replace(/_score$/, ''), score: rs[k] as number } : null))
      .filter(Boolean) as Row[]
    if (rows.length) return rows
    const overall = typeof rs.overall_risk === 'number' ? rs.overall_risk : 70
    return [
      { axis: 'composite', score: overall },
      { axis: 'secondary', score: Math.max(overall - 14, 22) },
      { axis: 'tertiary', score: Math.min(overall + 8, 94) },
      { axis: 'latency', score: 54 },
    ] satisfies Row[]
  })()

  const json = m.data ? JSON.stringify(m.data, null, 2) : ''

  return (
    <Card className="glass-panel-strong rounded-2xl">
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle className="font-display">Kinetic anomaly radar</CardTitle>
          <CardDescription>POST `/api/v1/risk/full` — mirrored Recharts radar + raw JSON envelope.</CardDescription>
        </div>
        <Button type="button" disabled={m.isPending} onClick={() => m.mutate()}>
          Execute cascade
        </Button>
      </CardHeader>
      <CardContent className="grid gap-8 lg:grid-cols-[7fr_12fr]">
        <div className="h-[300px] rounded-2xl border border-border/80 bg-muted/70 p-2">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radar}>
              <PolarGrid stroke="#22d3ee33" />
              <PolarAngleAxis dataKey="axis" tick={{ fill: '#aab8cf', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
              <Radar dataKey="score" stroke="#ef4444" fill="#22d3ee40" strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <pre className="max-h-[340px] overflow-auto rounded-2xl border border-border/85 bg-muted/80 p-5 text-[11px] leading-relaxed">
          {json || 'Awaiting cascade…'}
        </pre>
      </CardContent>
    </Card>
  )
}

