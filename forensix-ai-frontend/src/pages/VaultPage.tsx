import { EvidenceVaultDropzone } from '@/components/vault/EvidenceVaultDropzone'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useCaseStore } from '@/stores/case-store'

export default function VaultPage() {
  const activeId = useCaseStore((s) => s.activeCaseId)

  return (
    <div className="space-y-8">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-primary">Evidence vault</p>
        <h1 className="font-display text-4xl font-semibold text-card-foreground">Ingest manifold</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Bulk optical / narrative / binary staging routes through hardened FastAPI MIME sentries. Bind an active dossier
          before ingest.
        </p>
      </header>

      <EvidenceVaultDropzone caseId={activeId} />

      <Card className="glass-panel border-primary/20">
        <CardHeader>
          <CardTitle className="font-display text-lg">Retention doctrine</CardTitle>
          <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
            Server persists under `/uploads/*` — mirror hashes client-side in downstream builds.
          </CardDescription>
        </CardHeader>
        <CardContent className="font-mono text-xs leading-relaxed text-muted-foreground">
          PDF / DOCX / TXT · Optical captures JPEG–WEBP · Digital artefacts ZIP / logs / dumps · Audio routed via
          statements lane pending dedicated `/upload/audio` spine.
        </CardContent>
      </Card>
    </div>
  )
}
