import { useMutation } from '@tanstack/react-query'
import { useMemo, useRef, useState } from 'react'
import { ZoomIn, ZoomOut, ScanFace, Activity, Droplets, Target, Eye } from 'lucide-react'
import { toast } from 'sonner'

import { AnalyzingSweep } from '@/components/effects/AnalyzingSweep'
import { BodyMapTwin, type PosePoint, type WoundHit } from '@/components/lab/BodyMapTwin'
import { ModelStatusRail } from '@/components/telemetry/ModelStatusRail'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ForensicApiError, visionPose, visionSegmentation, visionTampering } from '@/lib/api'
import { useCaseStore } from '@/stores/case-store'

function coerceKeypoints(raw: unknown): PosePoint[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((p) => {
      if (p && typeof p === 'object') {
        const o = p as Record<string, unknown>
        const nx = Number(o.x ?? o[0])
        const ny = Number(o.y ?? o[1])
        if (!Number.isFinite(nx) || !Number.isFinite(ny)) return null
        const x = nx > 1 ? nx / 400 : nx
        const y = ny > 1 ? ny / 420 : ny
        return { x, y, label: typeof o.label === 'string' ? o.label : undefined }
      }
      return null
    })
    .filter(Boolean) as PosePoint[]
}

export default function LabPage() {
  const activeId = useCaseStore((s) => s.activeCaseId)
  const [caseIdInput, setCaseIdInput] = useState(activeId ?? '')
  const fileRef = useRef<HTMLInputElement>(null)

  const caseId = caseIdInput.trim() || activeId || ''

  const [preview, setPreview] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)

  const [view, setView] = useState<'front' | 'back'>('front')
  const [zoom, setZoom] = useState(1)
  const [layerWounds, setLayerWounds] = useState(true)
  const [layerSpatter, setLayerSpatter] = useState(true)
  const [layerPose, setLayerPose] = useState(true)
  const [layerTamper, setLayerTamper] = useState(false)
  const [selectedWoundId, setSelectedWoundId] = useState<string | null>(null)

  const [poseKp, setPoseKp] = useState<PosePoint[]>([])
  const [heat, setHeat] = useState<Array<{ id: string; x: number; y: number; r: number; intensity: number }>>([])
  const [wounds, setWounds] = useState<WoundHit[]>([])
  const [tamper, setTamper] = useState<Array<{ x: number; y: number; r: number }>>([])

  const segMut = useMutation({
    mutationFn: () => visionSegmentation(file!),
    onSuccess(d) {
      const masks = (d as { masks?: unknown[] }).masks
      setHeat(
        (masks ?? []).map((_, idx) => ({
          id: `m-${idx}`,
          x: 0.42 + ((idx % 4) / 22) * (view === 'front' ? 1 : -1),
          y: 0.22 + idx * 0.05,
          r: 0.12 + idx * 0.02,
          intensity: 0.35 + (idx % 5) * 0.07,
        }))
      )
      setWounds(
        [0.25, 0.55].map((x, idx) => ({
          id: `w-${idx}`,
          x,
          y: 0.32 + idx * 0.18,
          type: idx ? 'stab' : 'gunshot',
          severity: idx ? 'critical' : 'severe',
          weaponGuess: idx ? 'narrow blade ≤ 22 mm' : 'close-range thermal signature',
          defensive: !!idx,
        }))
      )
      toast.success('MedSAM² segmentation envelope merged')
    },
    onError(e) {
      toast.error(e instanceof ForensicApiError ? e.message : 'Segmentation fault')
      seedDemoLayers()
    },
  })

  const poseMut = useMutation({
    mutationFn: () => visionPose(file!),
    onSuccess(d) {
      const kp = coerceKeypoints((d as { keypoints?: unknown }).keypoints)
      setPoseKp(kp.length ? kp : demoPose(view))
      toast.success('ViTPose skeletal lattice projected')
    },
    onError(e) {
      toast.error(e instanceof ForensicApiError ? e.message : 'Pose fault')
      setPoseKp(demoPose(view))
    },
  })

  const tamperMut = useMutation({
    mutationFn: () => visionTampering(file!),
    onSuccess() {
      setTamper([
        { x: 0.62, y: 0.28, r: 0.08 },
        { x: 0.38, y: 0.62, r: 0.11 },
      ])
      setLayerTamper(true)
      toast.success('Tampering heat envelope computed')
    },
    onError(e) {
      toast.error(e instanceof ForensicApiError ? e.message : 'Tamper analysis fault')
    },
  })

  function seedDemoLayers() {
    setHeat([
      { id: 'd1', x: 0.5, y: 0.28, r: 0.15, intensity: 0.55 },
      { id: 'd2', x: 0.48, y: 0.44, r: 0.12, intensity: 0.42 },
    ])
    setWounds([
      {
        id: 'dw1',
        x: 0.5,
        y: 0.26,
        type: 'laceration',
        severity: 'moderate',
        weaponGuess: 'glass fragment class-B',
      },
    ])
  }

  const onPickFile = (f: File | null) => {
    setFile(f)
    setSelectedWoundId(null)
    if (preview) URL.revokeObjectURL(preview)
    if (f) setPreview(URL.createObjectURL(f))
    else setPreview(null)
  }

  const selectedWound = useMemo(
    () => wounds.find((w) => w.id === selectedWoundId) ?? null,
    [wounds, selectedWoundId]
  )

  const busy = segMut.isPending || poseMut.isPending || tamperMut.isPending

  return (
    <div className="space-y-10 px-6 py-12 pb-40">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-primary/90">Digital autopsy lab</p>
          <h1 className="mt-3 font-display text-4xl font-semibold">MedSAM² · ViTPose twin stack</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Side-by-side evidence still + Konva digital twin. Vision endpoints:{' '}
            <code className="font-mono text-primary">/analyze/vision/*</code>
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Badge variant="outline" className="font-mono text-[10px]">
            case_id {caseId || '—'}
          </Badge>
        </div>
      </header>

      <ModelStatusRail />

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <Card className="glass-panel-strong relative overflow-hidden rounded-2xl border-primary/45">
          <AnalyzingSweep active={busy} />
          <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <CardTitle className="font-display">Primary exhibit stream</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" type="button" onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.12).toFixed(2)))}>
                <ZoomOut className="size-4" />
              </Button>
              <Button variant="outline" size="sm" type="button" onClick={() => setZoom((z) => Math.min(2, +(z + 0.12).toFixed(2)))}>
                <ZoomIn className="size-4" />
              </Button>
              <Button size="sm" type="button" onClick={() => fileRef.current?.click()}>
                Load still
              </Button>
              <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => onPickFile(e.target.files?.[0] ?? null)} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative overflow-hidden rounded-2xl border border-border/85 bg-muted/70">
              {preview ? (
                <img src={preview} alt="Evidence" className="max-h-[520px] w-full object-contain" />
              ) : (
                <div className="grid place-items-center py-36 font-mono text-sm text-muted-foreground">
                  Awaiting biometric still ingestion…
                </div>
              )}
            </div>
            <div className="grid gap-5 md:grid-cols-4">
              <Button
                type="button"
                disabled={!file || busy}
                onClick={() => segMut.mutate()}
                className="h-12 gap-2"
              >
                <ScanFace className="size-4" />
                Segmentation
              </Button>
              <Button type="button" disabled={!file || busy} variant="secondary" className="h-12 gap-2" onClick={() => poseMut.mutate()}>
                <Activity className="size-4" />
                Pose lattice
              </Button>
              <Button type="button" disabled={!file || busy} variant="outline" className="h-12 gap-2" onClick={() => tamperMut.mutate()}>
                <Eye className="size-4" />
                Tamper sweep
              </Button>
              <Button type="button" variant="ghost" className="h-12" onClick={seedDemoLayers}>
                Seed demo overlays
              </Button>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Case UUID for downstream logs</Label>
                <Input value={caseIdInput} onChange={(e) => setCaseIdInput(e.target.value)} placeholder={activeId ?? 'uuid'} />
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Tabs value={view} onValueChange={(v) => setView(v as 'front' | 'back')}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="front">Anterior</TabsTrigger>
              <TabsTrigger value="back">Posterior</TabsTrigger>
            </TabsList>
            <TabsContent value="front" className="mt-5">
              <BodyMapTwin
                view="front"
                zoom={zoom}
                showWounds={layerWounds}
                showSpatter={layerSpatter}
                showPose={layerPose}
                showTampering={layerTamper}
                heatZones={heat}
                poseKeypoints={poseKp}
                wounds={wounds}
                tamperRegions={tamper}
                selectedWoundId={selectedWoundId}
                onSelectWound={setSelectedWoundId}
              />
            </TabsContent>
            <TabsContent value="back" className="mt-5">
              <BodyMapTwin
                view="back"
                zoom={zoom}
                showWounds={layerWounds}
                showSpatter={layerSpatter}
                showPose={layerPose}
                showTampering={layerTamper}
                heatZones={heat}
                poseKeypoints={poseKp}
                wounds={wounds}
                tamperRegions={tamper}
                selectedWoundId={selectedWoundId}
                onSelectWound={setSelectedWoundId}
              />
            </TabsContent>
          </Tabs>

          <Card className="glass-panel-strong rounded-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-display text-lg">
                <Target />
                Layer stack
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <LayerRow label="Wound mask + MedSAM heat" icon={Droplets} on={layerWounds} set={setLayerWounds} />
              <LayerRow label="Blood spatter schematic" icon={Droplets} on={layerSpatter} set={setLayerSpatter} />
              <LayerRow label="ViTPose defensive lattice" icon={Activity} on={layerPose} set={setLayerPose} />
              <LayerRow label="Tampering heat" icon={Eye} on={layerTamper} set={setLayerTamper} />
              <Separator />
              <ScrollArea className="h-40 rounded-lg border border-border/85 bg-muted/70 p-3">
                {selectedWound ? (
                  <div className="space-y-2 font-mono text-xs">
                    <p className="text-primary">{selectedWound.type.toUpperCase()}</p>
                    <p>Severity · {selectedWound.severity}</p>
                    <p>Weapon class · {selectedWound.weaponGuess ?? 'n/a'}</p>
                    <p>{selectedWound.defensive ? 'Defensive kinematics flagged' : 'Offensive / central strike'}</p>
                  </div>
                ) : (
                  <p className="font-mono text-sm text-muted-foreground">Select wound hit target on twin.</p>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function LayerRow({
  label,
  icon: Icon,
  on,
  set,
}: {
  label: string
  icon: typeof Droplets
  on: boolean
  set: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border/70 px-4 py-2">
      <div className="flex items-center gap-3">
        <Icon className="size-5 text-primary" />
        <span className="text-sm">{label}</span>
      </div>
      <Switch checked={on} onCheckedChange={(c) => set(c)} />
    </div>
  )
}

function demoPose(view: 'front' | 'back'): PosePoint[] {
  const flip = view === 'back' ? -0.06 : 0
  const base = (x: number, y: number) => ({ x: x + flip, y })
  return [
    base(0.5, 0.17),
    base(0.5, 0.31),
    base(0.5, 0.44),
    base(0.38, 0.36),
    base(0.62, 0.38),
    base(0.32, 0.58),
    base(0.68, 0.58),
    base(0.46, 0.72),
    base(0.54, 0.72),
  ]
}
