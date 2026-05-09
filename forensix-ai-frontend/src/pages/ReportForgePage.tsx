import { useMutation, useQuery } from '@tanstack/react-query'
import { FileDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { generateReportPdf, getCombinedAnalysis } from '@/lib/api'
import { qk } from '@/lib/query-keys'
import { useActiveCase } from '@/stores/case-store'
import { toast } from 'sonner'

export default function ReportForgePage() {
  const active = useActiveCase()
  const caseId = active?.id ?? ''

  const combined = useQuery({
    queryKey: qk.combined(caseId),
    queryFn: () => getCombinedAnalysis(caseId),
    enabled: Boolean(caseId),
  })

  const pdfMut = useMutation({
    mutationFn: async () =>
      generateReportPdf({
        case_context: active,
        timeline_events: [],
        risk_score: {},
        anomalies: {},
        contradictions: {},
        leads: {},
        forensic_bundle: combined.data ?? {},
      }),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `forensix-report-${active?.referenceCode ?? caseId.slice(0, 8)}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('PDF lattice exported')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Card className="glass-panel-strong border-primary/25">
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4 border-b border-primary/10">
          <div>
            <CardTitle className="font-display text-2xl text-card-foreground">Final report forge</CardTitle>
            <CardDescription className="font-mono text-[11px] uppercase tracking-[0.26em]">
              Live juridical preview · POST `/api/v1/report/generate`
            </CardDescription>
          </div>
          <Button
            className="gap-2 bg-primary font-display text-primary-foreground hover:bg-primary/90"
            disabled={!caseId || pdfMut.isPending}
            type="button"
            onClick={() => pdfMut.mutate()}
          >
            <FileDown className="h-4 w-4" />
            Generate full PDF
          </Button>
        </CardHeader>
        <CardContent className="pt-6">
          <ScrollArea className="h-[640px] rounded-2xl border border-primary/15 bg-[#030814]/95 p-8 shadow-inner">
            <div className="font-display text-xs uppercase tracking-[0.4em] text-primary">
              Ministry-grade forensic memorandum
            </div>
            <h2 className="mt-4 font-display text-3xl font-semibold text-card-foreground">
              Subject dossier · {active?.referenceCode ?? 'UNBOUND'}
            </h2>
            <Separator className="my-6 bg-primary/20" />
            <section className="space-y-3 font-serif text-sm leading-relaxed text-muted-foreground">
              <p>
                <span className="text-primary">I. Synopsis — </span>
                {active?.summary || 'Executive narrative pending ingest.'}
              </p>
              <p>
                <span className="text-primary">II. Victim — </span>
                {active?.victimAlias ?? 'Redacted pending judicial order.'}
              </p>
              <p>
                <span className="text-primary">III. Scene — </span>
                {active?.sceneLocation ?? 'Coordinates sealed.'}
              </p>
              <p>
                <span className="text-primary">IV. Neural cortex excerpt — </span>
              </p>
              <pre className="whitespace-pre-wrap rounded-xl bg-background/70 p-4 font-mono text-[11px] text-muted-foreground">
                {combined.data
                  ? JSON.stringify(combined.data, null, 2).slice(0, 4000)
                  : 'Combined forensic envelope empty — execute upstream analyzers.'}
              </pre>
            </section>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card className="glass-panel border-primary/20">
        <CardHeader>
          <CardTitle className="font-display text-lg text-card-foreground">Export manifest</CardTitle>
          <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
            Bundles body twin snapshots, timelines, graphs once backend renderer configured.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 font-mono text-xs text-muted-foreground">
          <p>• Case metadata & investigator attribution</p>
          <p>• Combined analysis JSON (truncated in preview)</p>
          <p>• Risk / anomaly placeholders for downstream templates</p>
        </CardContent>
      </Card>
    </div>
  )
}
