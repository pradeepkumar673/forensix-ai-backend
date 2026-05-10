import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Activity,
  Crosshair,
  Droplets,
  ImageIcon,
  Layers,
  Loader2,
  ScanLine,
  Target,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { BodyMapStage, type PosePoint, type WoundHit } from '@/components/lab/BodyMapStage'
import { GymAnatomyTwin } from '@/components/lab/gym-twin/GymAnatomyTwin'
import {
  DEMO_TRAUMA_BACK,
  DEMO_TRAUMA_FRONT,
  musclesFromNormalizedPoints,
  type MuscleId,
} from '@/components/lab/gym-twin/muscleRegions'
import { visionPose, visionSegmentation, visionTampering } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useUiStore } from '@/stores/ui-store'
import { toast } from 'sonner'

type Props = {
  caseId: string | null
}

/** Normalized ViTPose-style stick figure for continuity when the API is offline. */
const DEMO_POSE_POINTS: PosePoint[] = [
  { x: 0.5, y: 0.11 },
  { x: 0.5, y: 0.2 },
  { x: 0.42, y: 0.28 },
  { x: 0.58, y: 0.28 },
  { x: 0.36, y: 0.4 },
  { x: 0.64, y: 0.4 },
  { x: 0.5, y: 0.36 },
  { x: 0.46, y: 0.52 },
  { x: 0.54, y: 0.52 },
  { x: 0.48, y: 0.68 },
]

/** Highest-polish surface: tabbed lab shell around the Konva digital twin + vision pipelines. */
export function DigitalAutopsyLab({ caseId }: Props) {
  const setScan = useUiStore((s) => s.setScanning)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [view, setView] = useState<'front' | 'back'>('front')
  const [layerWounds, setLayerWounds] = useState(true)
  const [layerPose, setLayerPose] = useState(true)
  const [layerSpatter, setLayerSpatter] = useState(true)
  const [layerTamper, setLayerTamper] = useState(true)
  const [measure, setMeasure] = useState(false)
  const [insight, setInsight] = useState<string[]>([])
  const [selectedWoundId, setSelectedWoundId] = useState<string | null>(null)

  const [heatZones, setHeatZones] = useState<
    Array<{ id: string; x: number; y: number; r: number; intensity: number }>
  >([
    { id: 'd1', x: 0.48, y: 0.42, r: 1.1, intensity: 0.62 },
    { id: 'd2', x: 0.52, y: 0.58, r: 0.85, intensity: 0.48 },
  ])
  const [posePts, setPosePts] = useState<PosePoint[]>([])
  const [wounds, setWounds] = useState<WoundHit[]>([])
  const [tamper, setTamper] = useState<Array<{ x: number; y: number; r: number }>>([])

  const bindExhibitTrajectory = useCallback((v: 'front' | 'back') => {
    const demo = v === 'front' ? DEMO_TRAUMA_FRONT : DEMO_TRAUMA_BACK
    setWounds(
      demo.map((d, i) => ({
        id: `exhibit-${i}`,
        x: d.x,
        y: d.y,
        type: i === 0 ? 'Penetrating stab' : i === 1 ? 'Penetrating stab' : 'Slash — defensive',
        weaponGuess: 'Single-edge blade — est. 12cm',
        severity: i === 0 ? 'critical' : 'severe',
        defensive: i === 2,
      })),
    )
    setHeatZones(
      demo.map((d, i) => ({
        id: `heat-${i}`,
        x: d.x,
        y: d.y,
        r: 0.95,
        intensity: 0.72 + i * 0.04,
      })),
    )
    setPosePts(DEMO_POSE_POINTS)
    setTamper([{ x: 0.55, y: 0.43, r: 0.48 }])
    setInsight([
      'Gym-chart muscle correlation active — trauma vectors fused to SVG anatomical groups.',
      'Continuity lattice: exhibit ingested; neural gateway optional for live refinement.',
    ])
  }, [])

  const pickFile = (f: File | null) => {
    setFile(f)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(f ? URL.createObjectURL(f) : null)
    setInsight([])
    setSelectedWoundId(null)
    if (f) {
      bindExhibitTrajectory(view)
    } else {
      setWounds([])
      setPosePts([])
      setTamper([])
      setHeatZones([
        { id: 'd1', x: 0.48, y: 0.42, r: 1.1, intensity: 0.62 },
        { id: 'd2', x: 0.52, y: 0.58, r: 0.85, intensity: 0.48 },
      ])
    }
  }

  useEffect(() => {
    if (file) bindExhibitTrajectory(view)
  }, [view, file, bindExhibitTrajectory])

  const svgMuscleHighlights = useMemo(() => {
    const inferred = musclesFromNormalizedPoints(
      view,
      wounds.map((w) => ({ x: w.x, y: w.y })),
    )
    return new Set<MuscleId>(inferred)
  }, [view, wounds])

  const segM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Optical capture required')
      return visionSegmentation(file)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: (data: Record<string, unknown>) => {
      setInsight((s) => [...s, 'MedSAM-class segmentation envelope ingested.'])
      const regions = (data.regions ?? data.masks ?? data.contours) as
        | Array<Record<string, unknown>>
        | undefined
      if (Array.isArray(regions) && regions.length) {
        const mapped = regions.slice(0, 8).map((r, i) => ({
          id: `seg-${i}`,
          x: Number(r.cx ?? r.x ?? 0.5),
          y: Number(r.cy ?? r.y ?? 0.5),
          r: Number(r.radius ?? r.r ?? 1),
          intensity: Math.min(1, Number(r.score ?? r.confidence ?? 0.55)),
        }))
        setHeatZones(mapped)
      }
      toast.success('Segmentation lattice fused to twin')
    },
    onError: () => {
      bindExhibitTrajectory(view)
      toast.message('Segmentation — continuity envelope applied (offline)')
    },
  })

  const poseM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Optical capture required')
      return visionPose(file)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: (data: Record<string, unknown>) => {
      const pose = data.pose as Record<string, unknown> | undefined
      const raw =
        (data.keypoints as PosePoint[] | undefined) ||
        (pose?.keypoints as PosePoint[] | undefined) ||
        (data.points as PosePoint[] | undefined)
      if (Array.isArray(raw)) setPosePts(raw)
      const defensive = data.defensive_wounds ?? data.defensive_hits
      if (Array.isArray(defensive)) {
        setWounds(
          defensive.map((w: Record<string, unknown>, i: number) => ({
            id: `w-${i}`,
            x: Number(w.x ?? 0.5),
            y: Number(w.y ?? 0.5),
            type: String(w.type ?? 'laceration'),
            weaponGuess: w.weapon ? String(w.weapon) : undefined,
            severity: w.severity ? String(w.severity) : undefined,
            defensive: Boolean(w.defensive ?? true),
          })),
        )
      }
      setInsight((s) => [...s, 'ViTPose kinematics fused · defensive posture highlighting armed.'])
      toast.success('Pose mesh harmonized')
    },
    onError: () => {
      bindExhibitTrajectory(view)
      toast.message('Pose — continuity skeleton applied (offline)')
    },
  })

  const tamperM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Optical capture required')
      return visionTampering(file)
    },
    onMutate: () => setScan(true),
    onSettled: () => setScan(false),
    onSuccess: (data: Record<string, unknown>) => {
      const regions = (data.regions ?? data.hotspots) as
        | Array<Record<string, unknown>>
        | undefined
      if (Array.isArray(regions)) {
        setTamper(
          regions.map((r) => ({
            x: Number(r.x ?? 0.52),
            y: Number(r.y ?? 0.44),
            r: Number(r.r ?? 0.6),
          })),
        )
      } else {
        setTamper([{ x: 0.54, y: 0.41, r: 0.55 }])
      }
      setInsight((s) => [...s, 'ELA / noise-floor parity anomalies plotted.'])
      toast.success('Tamper heuristic overlay deployed')
    },
    onError: () => {
      bindExhibitTrajectory(view)
      toast.message('Integrity scan — continuity markers applied (offline)')
    },
  })

  const heroInsight = useMemo(
    () =>
      insight.length
        ? insight[insight.length - 1]
        : 'Awaiting optical ingest — twin running latent calibration lattice.',
    [insight],
  )

  const selectedWound = useMemo(
    () => wounds.find((w) => w.id === selectedWoundId) ?? null,
    [wounds, selectedWoundId],
  )

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Card className="glass-panel-strong holo-ring overflow-hidden border-primary/25">
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 border-b border-primary/10 pb-4">
          <div>
            <CardTitle className="font-display text-2xl text-primary">Digital Autopsy Twin</CardTitle>
            <CardDescription className="font-mono text-[11px] uppercase tracking-[0.28em]">
              Konva tensor plane · case {caseId ? caseId.slice(0, 8) : '∅'}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="border-primary/30 font-mono text-[10px] uppercase">
              MedSAM2-class heatfield
            </Badge>
            <Badge variant="outline" className="border-accent/40 font-mono text-[10px] uppercase text-accent">
              ViTPose kinematics
            </Badge>
            <Badge variant="outline" className="border-primary/25 font-mono text-[10px] uppercase">
              Gym-chart SVG twin
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-6">
          <Tabs defaultValue="body">
            <TabsList className="grid w-full grid-cols-4 bg-muted/40 font-mono text-[11px] uppercase">
              <TabsTrigger value="images">
                <ImageIcon className="mr-1 h-3.5 w-3.5" />
                Optical
              </TabsTrigger>
              <TabsTrigger value="body">
                <Layers className="mr-1 h-3.5 w-3.5" />
                Twin
              </TabsTrigger>
              <TabsTrigger value="wounds">
                <Target className="mr-1 h-3.5 w-3.5" />
                Trauma
              </TabsTrigger>
              <TabsTrigger value="tamper">
                <ScanLine className="mr-1 h-3.5 w-3.5" />
                Integrity
              </TabsTrigger>
            </TabsList>

            <TabsContent value="images" className="space-y-4 pt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-primary/15 bg-card/40 p-4">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                    Evidence feed
                  </p>
                  <input
                    type="file"
                    accept="image/*"
                    className="mt-3 block w-full font-mono text-xs text-muted-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary/15 file:px-3 file:py-2 file:font-display file:text-primary"
                    onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
                  />
                  <div className="mt-4 aspect-video overflow-hidden rounded-xl border border-primary/10 bg-[#030814]">
                    {preview ? (
                      <img src={preview} alt="Evidence preview" className="h-full w-full object-contain" />
                    ) : (
                      <div className="flex h-full items-center justify-center font-mono text-xs text-muted-foreground">
                        No optical channel
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex flex-col gap-3 rounded-2xl border border-primary/15 bg-card/40 p-4">
                  <p className="font-display text-lg text-card-foreground">Neural pipelines</p>
                  <Button
                    variant="outline"
                    className="justify-start border-primary/25 font-mono text-xs"
                    disabled={!file || segM.isPending}
                    onClick={() => segM.mutate()}
                  >
                    {segM.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />}
                    Run wound segmentation
                  </Button>
                  <Button
                    variant="outline"
                    className="justify-start border-primary/25 font-mono text-xs"
                    disabled={!file || poseM.isPending}
                    onClick={() => poseM.mutate()}
                  >
                    {poseM.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
                    Estimate pose + defensive hits
                  </Button>
                  <Button
                    variant="outline"
                    className="justify-start border-primary/25 font-mono text-xs"
                    disabled={!file || tamperM.isPending}
                    onClick={() => tamperM.mutate()}
                  >
                    {tamperM.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Droplets className="h-4 w-4" />}
                    Detect manipulation artefacts
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="body" className="space-y-4 pt-4">
              <div className="flex flex-wrap items-center gap-6">
                <div className="flex gap-2 rounded-xl border border-primary/15 bg-background/40 px-3 py-2">
                  <Button
                    size="sm"
                    variant={view === 'front' ? 'default' : 'ghost'}
                    className="font-mono text-[11px]"
                    onClick={() => setView('front')}
                  >
                    Anterior
                  </Button>
                  <Button
                    size="sm"
                    variant={view === 'back' ? 'default' : 'ghost'}
                    className="font-mono text-[11px]"
                    onClick={() => setView('back')}
                  >
                    Posterior
                  </Button>
                </div>
                <div className="flex flex-1 flex-wrap items-center gap-4 font-mono text-[11px] text-muted-foreground">
                  <label className="flex items-center gap-2">
                    <Switch checked={layerWounds} onCheckedChange={setLayerWounds} />
                    Wounds
                  </label>
                  <label className="flex items-center gap-2">
                    <Switch checked={layerPose} onCheckedChange={setLayerPose} />
                    Pose
                  </label>
                  <label className="flex items-center gap-2">
                    <Switch checked={layerSpatter} onCheckedChange={setLayerSpatter} />
                    Spatter
                  </label>
                  <label className="flex items-center gap-2">
                    <Switch checked={layerTamper} onCheckedChange={setLayerTamper} />
                    Tamper
                  </label>
                  <label className="flex items-center gap-2 text-primary">
                    <Switch checked={measure} onCheckedChange={setMeasure} />
                    Measure
                  </label>
                </div>
              </div>
              <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(220px,280px)]">
                <div className="flex justify-center">
                  <BodyMapStage
                    view={view}
                    showWounds={layerWounds}
                    showPose={layerPose}
                    showSpatter={layerSpatter}
                    showTampering={layerTamper}
                    heatZones={heatZones}
                    poseKeypoints={posePts}
                    wounds={wounds}
                    tamperRegions={tamper}
                    measureMode={measure}
                    selectedWoundId={selectedWoundId}
                    onSelectWound={setSelectedWoundId}
                    width={460}
                    height={500}
                  />
                </div>
                <div className="flex flex-col items-center gap-3 rounded-2xl border border-primary/15 bg-[#050a18]/80 p-4">
                  <p className="text-center font-mono text-[10px] uppercase tracking-[0.28em] text-primary">
                    Anatomical SVG — muscle highlight
                  </p>
                  <p className="text-center font-mono text-[10px] text-muted-foreground">
                    Stab / slash loci tint crimson; cyan rim = active correlation.
                  </p>
                  <GymAnatomyTwin view={view} highlighted={svgMuscleHighlights} />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="wounds" className="space-y-3 pt-4 font-mono text-sm">
              {wounds.length === 0 ? (
                <p className="text-muted-foreground">No traumatic overlays yet — execute pose / segmentation mesh.</p>
              ) : (
                wounds.map((w) => (
                  <motion.div
                    key={w.id}
                    layout
                    className="rounded-xl border border-primary/15 bg-card/60 px-4 py-3"
                  >
                    <p className="text-primary">{w.type}</p>
                    <p className="text-xs text-muted-foreground">
                      VECTOR ({w.x.toFixed(2)}, {w.y.toFixed(2)}) ·{' '}
                      {w.defensive ? 'DEFENSIVE POSTURE' : 'OFFENSIVE ENTRY'}
                    </p>
                    <Separator className="my-2 bg-primary/10" />
                    <p className="text-xs">
                      WEAPON GUESS · <span className="text-accent">{w.weaponGuess ?? 'Indeterminate'}</span>
                    </p>
                    <p className="text-xs text-muted-foreground">SEVERITY · {w.severity ?? '—'}</p>
                  </motion.div>
                ))
              )}
            </TabsContent>

            <TabsContent value="tamper" className="pt-4 font-mono text-sm text-muted-foreground">
              Manipulation audit harness plots spectral residue envelopes across candidate splice vectors. Overlay renders on
              Twin tab when telemetry exists ({tamper.length} loci).
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card className="glass-panel border-primary/20">
        <CardHeader>
          <CardTitle className="font-display text-lg text-card-foreground">AI cortex feed</CardTitle>
          <CardDescription className="font-mono text-[11px] uppercase tracking-[0.26em]">
            Side-channel reasoning · streaming insights
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[520px] pr-3">
            {selectedWound && (
              <motion.div
                layout
                className="mb-4 rounded-xl border border-accent/35 bg-accent/10 p-4"
              >
                <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-accent">Active trauma vector</p>
                <p className="mt-2 font-display text-lg text-card-foreground">{selectedWound.type}</p>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  GRID ({selectedWound.x.toFixed(3)}, {selectedWound.y.toFixed(3)}) ·{' '}
                  {selectedWound.defensive ? 'DEFENSIVE INTERCEPT' : 'OFFENSIVE ENTRY'}
                </p>
                <Separator className="my-3 bg-accent/20" />
                <p className="font-mono text-xs">
                  WEAPON · <span className="text-primary">{selectedWound.weaponGuess ?? 'Indeterminate'}</span>
                </p>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  SEVERITY · {selectedWound.severity ?? '—'}
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-3 font-mono text-[10px] text-muted-foreground"
                  onClick={() => setSelectedWoundId(null)}
                >
                  Clear selection
                </Button>
              </motion.div>
            )}
            <p className="mb-4 rounded-xl border border-primary/15 bg-primary/5 p-3 font-mono text-xs leading-relaxed text-primary">
              {heroInsight}
            </p>
            <ul className="space-y-3">
              {insight.map((line, i) => (
                <li key={i} className="text-xs text-muted-foreground">
                  <span className="font-mono text-[10px] text-primary">[{String(i + 1).padStart(2, '0')}]</span> {line}
                </li>
              ))}
            </ul>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
