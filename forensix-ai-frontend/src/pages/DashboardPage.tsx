import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Cpu, GitBranch, Radar } from 'lucide-react'
import { Link } from 'react-router-dom'
import { RiskGaugeCard } from '@/components/dashboard/RiskGaugeCard'
import { FxMetric } from '@/components/metrics/FxMetric'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { qk } from '@/lib/query-keys'
import { getModelStatus } from '@/lib/api'
import { riskNumeric, useCaseStore } from '@/stores/case-store'
import { useUiStore } from '@/stores/ui-store'

export default function DashboardPage() {
  const cases = useCaseStore((s) => s.cases)
  const scanning = useUiStore((s) => s.scanning)
  const models = useQuery({ queryKey: qk.models, queryFn: getModelStatus })

  const contradictions = cases.reduce((n, c) => n + (c.riskBand === 'high' || c.riskBand === 'critical' ? 1 : 0), 0)
  const avgRisk =
    cases.length === 0 ? 32 : Math.round(cases.reduce((s, c) => s + riskNumeric(c), 0) / cases.length)

  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-primary">Command deck</p>
          <h1 className="font-display text-4xl font-semibold text-card-foreground">Global forensic posture</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Unified lattice across neural inference gateways, HF spectral analysts, and investigator dossiers.
          </p>
        </div>
        <Badge variant="outline" className="border-primary/30 font-mono text-[10px] uppercase text-emerald-400/90">
          Mesh · synchronized
        </Badge>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <RiskGaugeCard title="Composite risk index" value={avgRisk} subtitle="Derived from active dossier bands" />
        <Card className="glass-panel border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Cpu className="h-5 w-5 text-primary" />
              Model lattice
            </CardTitle>
            <CardDescription className="font-mono text-[11px] uppercase tracking-[0.2em]">
              Provider · {models.data?.llm_provider ?? '…'}
            </CardDescription>
          </CardHeader>
          <CardContent className="font-mono text-xs text-muted-foreground">
            <p>Vision HF · {models.data?.vision_enabled ? 'armed' : 'disarmed'}</p>
            <p className="mt-1">Audio HF · {models.data?.audio_enabled ? 'armed' : 'disarmed'}</p>
            <p className="mt-2 text-[10px] text-primary/80">
              Loaded · {(models.data?.loaded_hf_models ?? []).join(', ') || '—'}
            </p>
          </CardContent>
        </Card>
        <Card className="glass-panel border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <GitBranch className="h-5 w-5 text-primary" />
              Active dossiers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-display text-4xl font-semibold text-card-foreground">{cases.length}</p>
            <p className="font-mono text-[11px] text-muted-foreground">Cases mirrored client-side vault</p>
          </CardContent>
        </Card>
        <Card className="glass-panel border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Radar className="h-5 w-5 text-accent" />
              Contradiction pressure
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-display text-4xl font-semibold text-accent">{contradictions}</p>
            <p className="font-mono text-[11px] text-muted-foreground">High / critical risk dossiers</p>
          </CardContent>
        </Card>
        <FxMetric
          title="Pending analyses"
          metric={scanning ? 'LIVE' : 'IDLE'}
          subtitle={scanning ? 'Neural mesh executing vision/audio pipelines' : 'Awaiting operator enqueue'}
          delta={scanning ? 'Spectral inference active' : 'Queue depth · 0'}
          deltaTrend={scanning ? 'up' : 'neutral'}
          className="border-primary/25 bg-gradient-to-br from-card/90 to-primary/[0.03]"
        />
      </div>

      <Card className="glass-panel-strong border-primary/25">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="font-display text-xl">Recent cases</CardTitle>
            <CardDescription className="font-mono text-[11px] uppercase tracking-[0.26em]">
              Chromatic encoding reflects synthetic risk band
            </CardDescription>
          </div>
          <Link
            to="/cases/new"
            className="flex items-center gap-1 font-mono text-xs text-primary hover:underline"
          >
            Instantiate dossier <ArrowUpRight className="h-4 w-4" />
          </Link>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-primary/15 hover:bg-transparent">
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Reference</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Title</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Status</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Risk</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Opened</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cases.slice(0, 8).map((c) => (
                <TableRow key={c.id} className="border-primary/10 hover:bg-primary/5">
                  <TableCell className="font-mono text-xs text-primary">{c.referenceCode}</TableCell>
                  <TableCell className="font-display text-sm">{c.title}</TableCell>
                  <TableCell className="font-mono text-xs uppercase text-muted-foreground">{c.status}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={
                        c.riskBand === 'critical'
                          ? 'border-accent text-accent'
                          : c.riskBand === 'high'
                            ? 'border-amber-400 text-amber-300'
                            : 'border-primary/35 text-primary'
                      }
                    >
                      {c.riskBand}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-muted-foreground">
                    {c.openedAt.slice(0, 10)}
                  </TableCell>
                </TableRow>
              ))}
              {cases.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-10 text-center font-mono text-sm text-muted-foreground">
                    No dossiers — spawn one via Case Registry.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
