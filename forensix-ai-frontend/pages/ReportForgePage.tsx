import { useMutation, useQuery } from '@tanstack/react-query'
import { FileSignature, Radiation } from 'lucide-react'
import { toast } from 'sonner'

import { ModelStatusRail } from '@/components/telemetry/ModelStatusRail'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

import { ForensicApiError, API_BASE_URL, generateReportPdf, listReports } from '@/lib/api'
import { useCaseStore } from '@/stores/case-store'

export default function ReportForgePage() {
  const active = useCaseStore((s) => s.cases.find((c) => c.id === s.activeCaseId))

  const prior = useQuery({
    queryKey: ['reports-list'],
    queryFn: listReports,
    refetchInterval: 120_000,
  })

  const exportPdf = useMutation({
    mutationFn: async () => {
      const body = {
        case_context: {
          case_id: active?.id ?? '00000000-0000-4000-8000-000000000000',
          title: active?.title ?? 'UNSIGNED DOSSIER',
          jurisdiction: active?.jurisdiction ?? '',
          synopsis: active?.synopsis ?? '',
          risk_band: active?.riskBand ?? 'medium',
          tags: active?.tags ?? [],
          generated_at: new Date().toISOString(),
        },
        risk_score: { overall_risk: 72, verdict: 'HIGH', notes: 'Seeded from Forge UI' },
        anomalies: { items: ['CCTV metadata drift', 'Secondary blood geometry'] },
        contradictions: { entries: ['Witness telemetry vs biometric lock'] },
        leads: { next: ['ELA sweep on Exhibit B', 'Suspect IMEI reconciliation'] },
        timeline_events: [{ t: 'discovery', note: 'Synthetic anchor for formatter' }],
      }
      return generateReportPdf(body)
    },
    onSuccess: async (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `forensix-${active?.code ?? 'CASE'}-${Date.now()}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('PDF envelope delivered')
      await prior.refetch()
    },
    onError: (e) => toast.error(e instanceof ForensicApiError ? e.message : 'Forge fault'),
  })

  const reports = ((prior.data as { reports?: string[] } | undefined)?.reports ?? [])

  return (
    <div className="space-y-10 px-6 py-12 pb-36">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-primary/92">Final report forge</p>
        <h1 className="mt-4 font-display text-4xl font-semibold">Court-ready PDF synthesis</h1>
        <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
          POST `/api/v1/report/generate` emits application/pdf. Wire additional sections from combined analysis payloads as
          you harden pipelines.
        </p>
      </header>

      <ModelStatusRail />

      <div className="grid gap-8 lg:grid-cols-2">
        <Card className="glass-panel-strong rounded-2xl border-primary/55">
          <CardHeader>
            <CardTitle className="flex items-center gap-3 font-display">
              <Radiation className="size-7 text-primary" />
              Live dossier surface
            </CardTitle>
            <CardDescription>Readable facsimile — typography + exhibits handled server-side.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5 rounded-xl border border-border/73 bg-muted/75 p-5 font-mono text-sm leading-relaxed text-muted-foreground">
            <PreviewRow label="Case" value={active?.title ?? 'No active dossier selected'} />
            <PreviewRow label="UUID" value={active?.id ?? '—'} />
            <PreviewRow label="Abstract" value={active?.synopsis || '—'} />
            <Separator className="bg-border/50" />
            <p className="text-[11px] uppercase tracking-[0.32em] text-primary">Embedding hooks</p>
            <ul className="list-inside list-disc space-y-2 text-[13px]">
              <li>Digital autopsy twin raster / SVG layer stack</li>
              <li>Knowledge graph atlas + metrics appendix</li>
              <li>Digital signature acknowledgement block</li>
            </ul>
          </CardContent>
        </Card>

        <Card className="glass-panel-strong rounded-2xl border-accent/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-3 font-display">
              <FileSignature className="size-7 text-accent" />
              Export controls
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <Button className="w-full py-10 text-lg" disabled={exportPdf.isPending} onClick={() => exportPdf.mutate()}>
              Forge PDF dossier
            </Button>
            <p className="font-mono text-[11px] text-muted-foreground">
              Endpoint {API_BASE_URL}/api/v1/report/generate
            </p>
            <Separator />
            <div>
              <p className="font-mono text-[11px] uppercase text-muted-foreground">Previously emitted PDFs</p>
              <ul className="mt-4 max-h-56 space-y-2 overflow-auto text-sm">
                {prior.isLoading && <li className="text-muted-foreground">Listing…</li>}
                {!prior.isLoading && reports.length === 0 && (
                  <li className="text-muted-foreground">No artefacts in outputs/</li>
                )}
                {reports.slice(0, 16).map((name: string) => (
                  <li key={name}>
                    <a
                      className="text-primary underline"
                      href={`${API_BASE_URL}/api/v1/report/download/${encodeURIComponent(name)}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {name}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-display text-[10px] uppercase tracking-[0.4em] text-primary/90">{label}</p>
      <p className="mt-2 text-foreground/92">{value}</p>
    </div>
  )
}
