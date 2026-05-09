import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2, Network, ScrollText, ShieldAlert, Sparkles, Waves } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  Tooltip as RTooltip,
} from 'recharts'
import { KnowledgeGraphBoard } from '@/components/workspace/KnowledgeGraphBoard'
import { TimelineVertical } from '@/components/workspace/TimelineVertical'
import {
  buildKnowledgeGraph,
  audioStress,
  audioTranscribe,
  getCombinedAnalysis,
  getKnowledgeGraph,
  getTimeline,
  postTimeline,
  riskFull,
} from '@/lib/api'
import { qk } from '@/lib/query-keys'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useUiStore } from '@/stores/ui-store'
import { useActiveCase } from '@/stores/case-store'
import { toast } from 'sonner'

function highlightClinical(text: string) {
  const bits = text.split(/(\b(?:toxicology|hemorrhage|laceration|firearm|stab|blunt)\b)/gi)
  return bits.map((b, i) =>
    /^(toxicology|hemorrhage|laceration|firearm|stab|blunt)$/i.test(b) ? (
      <mark key={i} className="rounded bg-primary/25 px-1 text-primary">
        {b}
      </mark>
    ) : (
      <span key={i}>{b}</span>
    ),
  )
}

export default function WorkspacePage() {
  const active = useActiveCase()
  const caseId = active?.id ?? ''
  const setScan = useUiStore((s) => s.setScanning)

  const combined = useQuery({
    queryKey: qk.combined(caseId),
    queryFn: () => getCombinedAnalysis(caseId),
    enabled: Boolean(caseId),
  })

  const timeline = useQuery({
    queryKey: qk.timeline(caseId),
    queryFn: () => getTimeline(caseId),
    enabled: Boolean(caseId),
    retry: false,
  })

  const graph = useQuery({
    queryKey: qk.graph(caseId),
    queryFn: () => getKnowledgeGraph(caseId),
    enabled: Boolean(caseId),
    retry: false,
  })

  const [blobText, setBlobText] = useState(
    'Suspect arrived at warehouse 22:14. Victim discovered 23:02 with blunt cranial trauma.',
  )
  const [audioFile, setAudioFile] = useState<File | null>(null)

  const timelineMut = useMutation({
    mutationFn: async () => {
      const f = new File([blobText], 'timeline-src.txt', { type: 'text/plain' })
      return postTimeline([f], caseId)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: async () => {
      toast.success('Timeline fused')
      await timeline.refetch()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const graphMut = useMutation({
    mutationFn: async () => {
      const f = new File([blobText], 'graph-src.txt', { type: 'text/plain' })
      return buildKnowledgeGraph([f], caseId)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: async () => {
      toast.success('Graph crystallized')
      await graph.refetch()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const transcribeMut = useMutation({
    mutationFn: async () => {
      if (!audioFile) throw new Error('Attach audio exhibit')
      return audioTranscribe(audioFile)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: () => toast.success('Phoneme lattice decoded'),
    onError: (e: Error) => toast.error(e.message),
  })

  const stressMut = useMutation({
    mutationFn: async () => {
      if (!audioFile) throw new Error('Attach audio exhibit')
      return audioStress(audioFile)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: () => toast.success('Paralingual stress tensor evaluated'),
    onError: (e: Error) => toast.error(e.message),
  })

  const riskMut = useMutation({
    mutationFn: () =>
      riskFull({
        report_text: active?.summary ?? '',
        statements: [],
        evidence_summary: '',
        evidence_items: [],
        timeline_events: [],
        case_summary: {
          title: active?.title,
          reference: active?.referenceCode,
          jurisdiction: active?.jurisdiction,
        },
      }),
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: () => toast.success('Risk fusion completed'),
    onError: (e: Error) => toast.error(e.message),
  })

  const execSummary = useMemo(() => {
    const d = combined.data as Record<string, unknown> | null | undefined
    if (!d) return ''
    return String(d.executive_summary ?? d.summary ?? d.primary_hypothesis ?? '')
  }, [combined.data])

  const radarRows = useMemo(() => {
    const rs = riskMut.data?.data?.risk_score as Record<string, unknown> | undefined
    if (!rs) {
      return [
        { k: 'Violence', v: 62 },
        { k: 'Premeditation', v: 48 },
        { k: 'Staging', v: 55 },
        { k: 'Digital', v: 41 },
        { k: 'Trajectory', v: 58 },
      ]
    }
    const numericKeys = Object.entries(rs).filter(
      ([key, val]) =>
        typeof val === 'number' && !['overall_risk_score', 'overall'].includes(key.toLowerCase()),
    )
    if (!numericKeys.length) {
      return [{ k: 'Overall', v: Number(rs.overall_risk_score ?? rs.overall ?? 55) }]
    }
    return numericKeys.slice(0, 6).map(([k, v]) => ({ k: k.slice(0, 14), v: Number(v) }))
  }, [riskMut.data])

  const timelineEvents = useMemo(() => {
    const t = timeline.data as Record<string, unknown> | undefined
    const evs = (t?.events as Record<string, unknown>[]) ?? []
    return evs.map((e) => ({
      event_id: String(e.event_id ?? ''),
      description: String(e.description ?? ''),
      timestamp: e.timestamp ? String(e.timestamp) : null,
      event_type: String(e.event_type ?? ''),
    }))
  }, [timeline.data])

  const timelineContradictions = useMemo(() => {
    const t = timeline.data as Record<string, unknown> | undefined
    const raw = (t?.contradictions as unknown[]) ?? []
    return raw.map((c) => (typeof c === 'string' ? c : JSON.stringify(c)))
  }, [timeline.data])

  const graphEntities = useMemo(() => {
    const g = graph.data as Record<string, unknown> | undefined
    const inner = (g?.graph as Record<string, unknown>) ?? g
    const ents = (inner?.entities as Record<string, unknown>[]) ?? []
    return ents.map((e, idx) => ({
      entity_id: String(e.entity_id ?? e.id ?? `node-${idx}`),
      entity_type: String(e.entity_type ?? 'other'),
      label: String(e.label ?? 'unknown'),
      risk_score: typeof e.risk_score === 'number' ? e.risk_score : undefined,
    }))
  }, [graph.data])

  const graphRels = useMemo(() => {
    const g = graph.data as Record<string, unknown> | undefined
    const inner = (g?.graph as Record<string, unknown>) ?? g
    const rel = (inner?.relationships as Record<string, unknown>[]) ?? []
    return rel.map((r) => ({
      source_id: String(r.source_id ?? ''),
      target_id: String(r.target_id ?? ''),
      relation_type: String(r.relation_type ?? 'REL'),
      strength: typeof r.strength === 'number' ? r.strength : 0.6,
    }))
  }, [graph.data])

  const stressSeries = useMemo(() => {
    const d = stressMut.data as Record<string, unknown> | undefined
    const pts = (d?.timeline as Record<string, unknown>[]) ?? []
    if (pts.length) {
      return pts.map((p, i) => ({
        t: String(p.t ?? i),
        s: Number(p.stress ?? p.score ?? 0),
      }))
    }
    return Array.from({ length: 24 }).map((_, i) => ({
      t: `${i}s`,
      s: 35 + Math.sin(i / 3) * 12 + (i % 5) * 3,
    }))
  }, [stressMut.data])

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-primary">Forensic intelligence</p>
          <h1 className="font-display text-4xl font-semibold text-card-foreground">Workspace lattice</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Cross-domain reasoning harness — reports, chronologies, entity graphs, phonetics, and calibrated risk tensors.
          </p>
        </div>
        {!caseId && (
          <Badge variant="outline" className="border-amber-400/60 font-mono text-[10px] uppercase text-amber-200">
            Attach dossier · pipelines gated
          </Badge>
        )}
      </header>

      <Tabs defaultValue="report">
        <TabsList className="flex flex-wrap bg-muted/40 font-mono text-[11px] uppercase">
          <TabsTrigger value="report">
            <ScrollText className="mr-1 h-3.5 w-3.5" />
            Report
          </TabsTrigger>
          <TabsTrigger value="timeline">
            <Sparkles className="mr-1 h-3.5 w-3.5" />
            Timeline
          </TabsTrigger>
          <TabsTrigger value="graph">
            <Network className="mr-1 h-3.5 w-3.5" />
            Graph
          </TabsTrigger>
          <TabsTrigger value="voice">
            <Waves className="mr-1 h-3.5 w-3.5" />
            Voice
          </TabsTrigger>
          <TabsTrigger value="risk">
            <ShieldAlert className="mr-1 h-3.5 w-3.5" />
            Risk
          </TabsTrigger>
        </TabsList>

        <TabsContent value="report" className="space-y-4 pt-6">
          <Card className="glass-panel border-primary/20">
            <CardHeader>
              <CardTitle className="font-display text-lg">Medical / forensic extraction</CardTitle>
              <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
                Combined bundle · POST `/analyze/report` upstream hydrates this lattice
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {combined.isFetching ? (
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              ) : execSummary ? (
                <ScrollArea className="h-[420px] rounded-xl border border-primary/15 bg-card/60 p-4 font-mono text-sm leading-relaxed">
                  {highlightClinical(execSummary)}
                </ScrollArea>
              ) : (
                <p className="font-mono text-sm text-muted-foreground">
                  No aggregated cortex payload — run ingest analyzers for dossier{' '}
                  <span className="text-primary">{caseId.slice(0, 8) || '—'}</span>.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeline" className="space-y-4 pt-6">
          <Card className="glass-panel border-primary/20">
            <CardHeader className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <CardTitle className="font-display text-lg">Event chronology</CardTitle>
                <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
                  POST `/correlate/timeline` · contradiction pulses animate automatically
                </CardDescription>
              </div>
              <Button
                variant="outline"
                disabled={!caseId || timelineMut.isPending}
                className="border-primary/25 font-mono text-xs"
                type="button"
                onClick={() => timelineMut.mutate()}
              >
                {timelineMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Rebuild spine'}
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea rows={5} value={blobText} onChange={(e) => setBlobText(e.target.value)} className="font-mono text-xs" />
              <TimelineVertical events={timelineEvents} contradictions={timelineContradictions} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="graph" className="space-y-4 pt-6">
          <Card className="glass-panel border-primary/20">
            <CardHeader className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <CardTitle className="font-display text-lg">Knowledge constellation</CardTitle>
                <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
                  React Flow · EntityGraphResponse hydration
                </CardDescription>
              </div>
              <Button
                variant="outline"
                disabled={!caseId || graphMut.isPending}
                className="border-primary/25 font-mono text-xs"
                type="button"
                onClick={() => graphMut.mutate()}
              >
                {graphMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Compile graph'}
              </Button>
            </CardHeader>
            <CardContent>
              <KnowledgeGraphBoard
                key={`${graphEntities.length}-${graphRels.length}`}
                entities={graphEntities}
                relationships={graphRels}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="voice" className="space-y-4 pt-6">
          <Card className="glass-panel border-primary/20">
            <CardHeader>
              <CardTitle className="font-display text-lg">Waveform intelligence</CardTitle>
              <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
                `/analyze/audio/transcribe` · `/analyze/audio/stress`
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input type="file" accept="audio/*" className="font-mono text-xs" onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)} />
              <div className="flex flex-wrap gap-3">
                <Button variant="outline" disabled={!audioFile || transcribeMut.isPending} type="button" onClick={() => transcribeMut.mutate()}>
                  Transcribe
                </Button>
                <Button variant="outline" disabled={!audioFile || stressMut.isPending} type="button" onClick={() => stressMut.mutate()}>
                  Stress tensor
                </Button>
              </div>
              <div className="rounded-xl border border-primary/15 bg-[#040914] p-4">
                <div className="flex h-16 items-end gap-px">
                  {Array.from({ length: 48 }).map((_, i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-t bg-gradient-to-t from-primary/25 to-primary/60"
                      style={{ height: `${18 + ((i * 7) % 44)}px`, opacity: 0.35 + ((i * 13) % 65) / 100 }}
                    />
                  ))}
                </div>
                <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
                  Synthetic waveform façade · binds to live FFT hooks downstream
                </p>
              </div>
              <div className="h-52 rounded-xl border border-primary/15 bg-card/50 p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={stressSeries}>
                    <defs>
                      <linearGradient id="stressGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#991b1b" stopOpacity={0.9} />
                        <stop offset="95%" stopColor="#991b1b" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="t" hide />
                    <RTooltip contentStyle={{ background: '#0a1428', border: '1px solid rgba(0,245,255,0.25)' }} />
                    <Area type="monotone" dataKey="s" stroke="#991b1b" fillOpacity={1} fill="url(#stressGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <ScrollArea className="max-h-40 rounded-lg border border-primary/10 bg-background/60 p-3 font-mono text-xs">
                {(transcribeMut.data as Record<string, unknown> | undefined)?.text
                  ? String((transcribeMut.data as Record<string, unknown>).text)
                  : 'Transcript channel idle.'}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risk" className="space-y-4 pt-6">
          <Card className="glass-panel border-primary/20">
            <CardHeader className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <CardTitle className="font-display text-lg">Omni risk synthesis</CardTitle>
                <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
                  POST `/risk/full` — animated radar + fallback telemetry when partial
                </CardDescription>
              </div>
              <Button variant="outline" disabled={!caseId || riskMut.isPending} type="button" onClick={() => riskMut.mutate()}>
                {riskMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Execute fusion'}
              </Button>
            </CardHeader>
            <CardContent className="grid gap-6 lg:grid-cols-2">
              <div className="h-72 rounded-xl border border-primary/15 bg-card/60 p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="78%" data={radarRows}>
                    <PolarGrid stroke="rgba(0,245,255,0.2)" />
                    <PolarAngleAxis dataKey="k" tick={{ fill: '#8ba4c7', fontSize: 11 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#5f7394', fontSize: 10 }} />
                    <Radar name="Risk" dataKey="v" stroke="#00f5ff" fill="#00f5ff" fillOpacity={0.35} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <ScrollArea className="h-72 rounded-xl border border-primary/15 bg-background/70 p-4 font-mono text-xs">
                <pre className="whitespace-pre-wrap text-muted-foreground">
                  {riskMut.data ? JSON.stringify(riskMut.data, null, 2) : 'Risk manifold idle.'}
                </pre>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
