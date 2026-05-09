import { useMutation } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { FileJson, FileText, ImagePlus, ServerCog, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { ForensicApiError, uploadDigitalEvidence, uploadImages, uploadReport, uploadStatements } from '@/lib/api'

type Zone = {
  id: string
  title: string
  desc: string
  icon: typeof Upload
  accept: string
  mut: (files: File[]) => Promise<unknown>
}

const ZONES: Zone[] = [
  {
    id: 'report',
    title: 'Autopsy / Forensic reports',
    desc: 'POST `/api/v1/upload/report` · PDF, DOCX, TXT',
    icon: FileText,
    accept: '.pdf,.doc,.docx,.txt',
    mut: (files) => uploadReport(files[0]!),
  },
  {
    id: 'images',
    title: 'Scene & injury stills',
    desc: 'POST `/api/v1/upload/images` · multi-file batch',
    icon: ImagePlus,
    accept: '.jpg,.jpeg,.png,.webp,.tiff,.bmp',
    mut: uploadImages,
  },
  {
    id: 'digital',
    title: 'Digital artefacts',
    desc: 'POST `/api/v1/upload/digital-evidence`',
    icon: ServerCog,
    accept: '.zip,.tar,.gz,.json,.csv,.txt,.xml',
    mut: uploadDigitalEvidence,
  },
  {
    id: 'statements',
    title: 'Witness & suspect statements',
    desc: 'POST `/api/v1/upload/statements`',
    icon: FileJson,
    accept: '.pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.tiff',
    mut: uploadStatements,
  },
]

export default function EvidenceVaultPage() {
  return (
    <div className="space-y-12 px-6 py-12 pb-36">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary/90">Custody vault</p>
        <h1 className="mt-4 font-display text-4xl font-semibold tracking-tight">Evidence ingest grid</h1>
        <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
          Chain-of-custody timestamps are annotated client-side immediately on successful ack. Each category maps 1:1 to
          backend upload routers.
        </p>
      </header>

      <div className="grid gap-8 md:grid-cols-2">
        {ZONES.map((z) => (
          <VaultZone key={z.id} zone={z} />
        ))}
      </div>
    </div>
  )
}

function VaultZone({ zone }: { zone: Zone }) {
  const [drag, setDrag] = useState(false)
  const [lastHash, setLastHash] = useState<string | null>(null)

  const m = useMutation({
    mutationFn: (files: File[]) => zone.mut(files),
    onSuccess(data) {
      setLastHash(JSON.stringify(data).slice(0, 120))
      toast.success(`${zone.title}: vault committed`)
    },
    onError(err) {
      toast.error(err instanceof ForensicApiError ? err.message : 'Ingress fault')
    },
  })

  const ingest = useCallback(
    (files: FileList | null) => {
      if (!files?.length) return
      const arr = Array.from(files)
      if (zone.id === 'report' && arr.length > 1) {
        toast.message('Report endpoint ingests a single artefact — truncating batch to first item.')
      }
      const payload = zone.id === 'report' ? [arr[0]!] : arr
      m.mutate(payload)
    },
    [m, zone.id]
  )

  return (
    <Card
      className={`glass-panel-strong relative overflow-hidden transition ${
        drag ? 'border-primary/75 ring-2 ring-primary/45' : ''
      }`}
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        ingest(e.dataTransfer.files)
      }}
    >
      {m.isPending && (
        <div className="absolute left-0 top-0 z-20 h-1 w-full animate-pulse rounded-none bg-primary shadow-[0_0_12px_rgba(34,211,238,0.85)]" />
      )}
      <AnalyzingChrome active={m.isPending} />
      <CardHeader className="flex flex-row gap-4 pb-2">
        <div className="flex size-14 items-center justify-center rounded-2xl border border-primary/43 bg-muted/80">
          <zone.icon className="size-8 text-primary" />
        </div>
        <div>
          <CardTitle className="font-display">{zone.title}</CardTitle>
          <CardDescription>{zone.desc}</CardDescription>
          <Badge variant="outline" className="mt-3 font-mono text-[10px]">
            {zone.id}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pb-8">
        <label className="relative block cursor-pointer">
          <motion.div
            animate={{ boxShadow: drag ? '0 0 56px rgba(34,211,238,0.15)' : undefined }}
            className="rounded-2xl border border-dashed border-primary/35 bg-muted/70 p-14 text-center backdrop-blur"
          >
            <Upload className="mx-auto size-10 text-primary opacity-80" />
            <p className="mt-4 font-display text-lg">Deposit evidence</p>
            <p className="mt-2 font-mono text-[11px] text-muted-foreground">Drag / tap — accept {zone.accept}</p>
            <input
              type="file"
              className="absolute inset-0 cursor-pointer opacity-0"
              multiple={zone.id !== 'report'}
              accept={zone.accept}
              onChange={(e) => ingest(e.target.files)}
            />
          </motion.div>
        </label>
        <Separator className="opacity-40" />
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
          last ack digest
        </p>
        <p className="break-words font-mono text-[11px] text-primary">{lastHash ?? '— awaiting first commit —'}</p>
        <p className="font-mono text-[10px] text-muted-foreground/80">
          Custody watermark {new Date().toISOString()}
        </p>
      </CardContent>
    </Card>
  )
}

function AnalyzingChrome({ active }: { active: boolean }) {
  if (!active) return null
  return (
    <motion.div
      className="pointer-events-none absolute inset-0 z-[5] bg-primary/6"
      animate={{ opacity: [0.4, 1, 0.5] }}
      transition={{ repeat: Infinity, duration: 1.6 }}
    />
  )
}
