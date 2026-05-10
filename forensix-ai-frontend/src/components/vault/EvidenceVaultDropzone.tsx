import { useCallback, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { CloudUpload, FileAudio, FileImage, FileText, Loader2, Shield } from 'lucide-react'
import { analyzeImages, analyzeReport, uploadDigitalEvidence, uploadImages, uploadReport, uploadStatements } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { qk } from '@/lib/query-keys'
import { cn } from '@/lib/utils'

type Props = {
  caseId: string | null
}

/** Routes uploads to the correct FastAPI /upload/* endpoints by MIME sniffing. */
export function EvidenceVaultDropzone({ caseId }: Props) {
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const ingest = useCallback(
    async (files: FileList | File[]) => {
      const list = [...files]
      if (!caseId) {
        toast.error('Attach an active dossier before vault ingest.')
        return
      }
      setBusy(true)
      setProgress(5)
      try {
        const imgs = list.filter((f) => f.type.startsWith('image/'))
        const audio = list.filter((f) => f.type.startsWith('audio/'))
        const reports = list.filter(
          (f) =>
            f.type.includes('pdf') ||
            f.type.includes('word') ||
            f.type.includes('document') ||
            f.type === 'text/plain',
        )
        const digital = list.filter(
          (f) =>
            !imgs.includes(f) &&
            !audio.includes(f) &&
            !reports.includes(f),
        )

        if (imgs.length) {
          await analyzeImages(imgs, caseId, (p) => setProgress(10 + p * 0.25))
          toast.success(`${imgs.length} optical capture(s) sealed and analysed`)
        }
        if (reports.length) {
          for (let i = 0; i < reports.length; i++) {
            const f = reports[i]!
            // Trigger analysis instead of simple upload so results are available in the workspace
            await analyzeReport(f, caseId, (p) =>
              setProgress(40 + ((i + p / 100) / reports.length) * 18),
            )
          }
          toast.success(`${reports.length} narrative artefact(s) vaulted and analysed`)
        }
        if (digital.length) {
          await uploadDigitalEvidence(digital, (p) => setProgress(60 + p * 0.2))
          toast.success(`${digital.length} binary artefact(s) routed`)
        }
        if (audio.length) {
          toast.message('Audio routed via statements vault adapter — transcribe in workspace.')
          await uploadStatements(audio, (p) => setProgress(80 + p * 0.15))
        }

        // Invalidate queries so workspace picks up new data
        queryClient.invalidateQueries({ queryKey: qk.combined(caseId) })
        queryClient.invalidateQueries({ queryKey: qk.timeline(caseId) })
        queryClient.invalidateQueries({ queryKey: qk.graph(caseId) })

        setProgress(100)
      } catch (e: unknown) {
        toast.error(e instanceof Error ? e.message : 'Vault ingest fault')
      } finally {
        setBusy(false)
        setTimeout(() => setProgress(0), 700)
      }
    },
    [caseId],
  )

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files?.length) void ingest(e.dataTransfer.files)
  }

  return (
    <motion.div
      layout
      onDragOver={(e) => e.preventDefault()}
      onDrop={onDrop}
      className={cn(
        'glass-panel-strong relative overflow-hidden rounded-2xl border border-dashed border-primary/35 p-10 text-center',
        busy && 'pointer-events-none opacity-80',
      )}
    >
      <div className="pointer-events-none absolute inset-0 opacity-[0.07] [background:radial-gradient(circle_at_50%_20%,rgba(0,245,255,0.45),transparent_55%)]" />
      <CloudUpload className="mx-auto h-12 w-12 text-primary/85" />
      <p className="mt-4 font-display text-xl text-card-foreground">Evidence ingest manifold</p>
      <p className="mx-auto mt-2 max-w-lg font-mono text-xs text-muted-foreground">
        Drag classified PDFs, imagery bundles, audio exhibits, or digital artefacts. Routing obeys MIME envelope
        validation server-side.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3 text-muted-foreground">
        <span className="flex items-center gap-1 rounded-full border border-primary/15 px-3 py-1 font-mono text-[11px]">
          <FileImage className="h-4 w-4 text-primary" /> Optical
        </span>
        <span className="flex items-center gap-1 rounded-full border border-primary/15 px-3 py-1 font-mono text-[11px]">
          <FileText className="h-4 w-4 text-primary" /> Narrative
        </span>
        <span className="flex items-center gap-1 rounded-full border border-primary/15 px-3 py-1 font-mono text-[11px]">
          <Shield className="h-4 w-4 text-primary" /> Binary
        </span>
        <span className="flex items-center gap-1 rounded-full border border-primary/15 px-3 py-1 font-mono text-[11px]">
          <FileAudio className="h-4 w-4 text-primary" /> Audio
        </span>
      </div>

      <input
        ref={fileRef}
        type="file"
        multiple
        className="hidden"
        disabled={busy || !caseId}
        onChange={(e) => e.target.files && void ingest(e.target.files)}
      />
      <Button
        type="button"
        variant="outline"
        disabled={busy || !caseId}
        className="mt-8 border-primary/35 bg-primary/10 font-display text-primary"
        onClick={() => fileRef.current?.click()}
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Browse vault staging'}
      </Button>

      {progress > 0 && (
        <div className="mx-auto mt-8 max-w-md space-y-2">
          <Progress value={progress} className="h-2 bg-muted/60" />
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-primary">Cryptographic sealing… {progress}%</p>
        </div>
      )}
    </motion.div>
  )
}
