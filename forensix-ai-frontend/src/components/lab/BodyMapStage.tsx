/**
 * Interactive 2D digital autopsy twin — Konva-backed silhouette, wound halos,
 * pose skeleton, tamper rings, zoom/pan, measurement line.
 */

import Konva from 'konva'
import { useCallback, useMemo, useRef, useState } from 'react'
import { Circle, Group, Layer, Line, Rect, Stage, Text } from 'react-konva'

export type PosePoint = { x: number; y: number; label?: string }

export type WoundHit = {
  id: string
  x: number
  y: number
  type: string
  weaponGuess?: string
  severity?: string
  defensive?: boolean
}

const POSE_EDGES: [number, number][] = [
  [0, 1],
  [1, 2],
  [1, 3],
  [2, 4],
  [3, 5],
  [1, 6],
  [6, 8],
  [6, 7],
  [7, 9],
]

function Silhouette({ view }: { view: 'front' | 'back' }) {
  const stroke = 'rgba(0,245,255,0.42)'
  const fill = 'rgba(8,14,28,0.88)'
  return (
    <Group listening={false}>
      <Circle x={200} y={88} radius={44} stroke={stroke} strokeWidth={2} fill={fill} />
      <Rect x={152} y={140} width={96} height={148} stroke={stroke} strokeWidth={2} fill={fill} rx={4} />
      <Rect x={96} y={158} width={56} height={26} stroke={stroke} strokeWidth={2} fill={fill} rx={3} />
      <Rect x={248} y={158} width={56} height={26} stroke={stroke} strokeWidth={2} fill={fill} rx={3} />
      <Rect x={168} y={292} width={32} height={102} stroke={stroke} strokeWidth={2} fill={fill} rx={3} />
      <Rect x={202} y={292} width={32} height={102} stroke={stroke} strokeWidth={2} fill={fill} rx={3} />
      {view === 'front' && (
        <Rect
          x={184}
          y={188}
          width={32}
          height={36}
          stroke="rgba(153,27,27,0.35)"
          strokeWidth={1}
          fill="transparent"
        />
      )}
    </Group>
  )
}

type Props = {
  view: 'front' | 'back'
  showWounds: boolean
  showPose: boolean
  showSpatter: boolean
  showTampering: boolean
  heatZones?: Array<{ id: string; x: number; y: number; r: number; intensity: number }>
  poseKeypoints?: PosePoint[]
  wounds?: WoundHit[]
  tamperRegions?: Array<{ x: number; y: number; r: number }>
  measureMode: boolean
  /** Selected wound id for halo + inspector binding */
  selectedWoundId?: string | null
  onSelectWound?: (id: string | null) => void
  width?: number
  height?: number
}

export function BodyMapStage({
  view,
  showWounds,
  showPose,
  showSpatter,
  showTampering,
  heatZones = [],
  poseKeypoints = [],
  wounds = [],
  tamperRegions = [],
  measureMode,
  selectedWoundId = null,
  onSelectWound,
  width = 440,
  height = 480,
}: Props) {
  const stageRef = useRef<Konva.Stage>(null)
  const [zoom, setZoom] = useState(1)
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 })
  const [measurePts, setMeasurePts] = useState<number[]>([])
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)

  const scaledPoints = useMemo(
    () => poseKeypoints.map((p) => ({ x: p.x * width, y: p.y * height, label: p.label })),
    [poseKeypoints, width, height],
  )

  const skeletonLines = useMemo(() => {
    if (!showPose || scaledPoints.length === 0) return []
    return POSE_EDGES.map(([a, b]) => {
      const pa = scaledPoints[a]
      const pb = scaledPoints[b]
      if (!pa || !pb) return null
      return [pa.x, pa.y, pb.x, pb.y] as number[]
    }).filter(Boolean) as number[][]
  }, [scaledPoints, showPose])

  const distLabel = useMemo(() => {
    if (measurePts.length !== 4) return ''
    const [x1, y1, x2, y2] = measurePts
    const px = Math.hypot(x2 - x1, y2 - y1)
    const cm = (px / width) * 175
    return `${cm.toFixed(1)} cm · ${px.toFixed(0)} px`
  }, [measurePts, width])

  const onWheel = useCallback(
    (e: Konva.KonvaEventObject<WheelEvent>) => {
      e.evt.preventDefault()
      const stage = stageRef.current
      if (!stage) return
      const scaleBy = 1.08
      const oldScale = zoom
      const pointer = stage.getPointerPosition()
      if (!pointer) return
      const direction = e.evt.deltaY > 0 ? -1 : 1
      const newScale = direction > 0 ? Math.min(oldScale * scaleBy, 3.2) : Math.max(oldScale / scaleBy, 0.55)
      const mousePointTo = {
        x: (pointer.x - stagePos.x) / oldScale,
        y: (pointer.y - stagePos.y) / oldScale,
      }
      const newPos = {
        x: pointer.x - mousePointTo.x * newScale,
        y: pointer.y - mousePointTo.y * newScale,
      }
      setZoom(newScale)
      setStagePos(newPos)
    },
    [zoom, stagePos],
  )

  const canvasClick = useCallback(
    (ev: Konva.KonvaEventObject<MouseEvent>) => {
      if (!measureMode) return
      const stage = stageRef.current
      if (!stage) return
      const p = stage.getRelativePointerPosition()
      if (!p) return
      const nx = (p.x - stagePos.x) / zoom
      const ny = (p.y - stagePos.y) / zoom
      setMeasurePts((prev) => {
        const next = [...prev, nx, ny]
        return next.length > 4 ? [nx, ny] : next
      })
    },
    [measureMode, stagePos, zoom],
  )

  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/25 bg-[#050a18]/90 holo-ring shadow-[0_0_48px_rgba(0,245,255,0.08)]">
      <div className="pointer-events-none absolute inset-0 grid-overlay opacity-80" />
      <Stage
        ref={stageRef}
        width={width}
        height={height}
        onWheel={onWheel}
        scaleX={zoom}
        scaleY={zoom}
        x={stagePos.x}
        y={stagePos.y}
        draggable={!measureMode}
        onDragEnd={(e) => setStagePos(e.target.position())}
        className="cursor-crosshair bg-transparent"
        onMouseMove={() => {
          const stage = stageRef.current
          if (!stage) return
          const p = stage.getRelativePointerPosition()
          if (!p) return
          const nx = (p.x - stagePos.x) / zoom
          const ny = (p.y - stagePos.y) / zoom
          setCursor({ x: nx, y: ny })
        }}
        onClick={canvasClick}
      >
        <Layer listening={false}>
          <Text
            text={view === 'front' ? 'ANTERIOR · DIGITAL TWIN' : 'POSTERIOR · DIGITAL TWIN'}
            x={14}
            y={12}
            fill="rgba(0,245,255,0.65)"
            fontSize={11}
            fontFamily="JetBrains Mono, monospace"
            letterSpacing={3}
          />
          <Silhouette view={view} />
        </Layer>

        <Layer listening={false}>
          {heatZones.map((z) => (
            <Circle
              key={z.id}
              x={z.x * width}
              y={z.y * height}
              radius={Math.max(z.r * width * 0.15, 7)}
              fill={`rgba(153,27,27,${0.14 + z.intensity * 0.45})`}
              stroke={`rgba(0,245,255,${0.35 + z.intensity * 0.28})`}
              strokeWidth={1.5}
            />
          ))}
          {showSpatter &&
            [
              [0.31, 0.17, 3.2],
              [0.69, 0.21, 2.6],
              [0.53, 0.37, 2.1],
              [0.42, 0.46, 2.9],
            ].map(([x, y, r], idx) => (
              <Circle
                key={`sp-${idx}`}
                x={(x as number) * width}
                y={(y as number) * height}
                radius={r as number}
                stroke="rgba(239,68,68,0.78)"
                fill="rgba(153,27,27,0.22)"
                strokeWidth={2}
              />
            ))}
        </Layer>

        {showTampering && tamperRegions.length > 0 && (
          <Layer listening={false}>
            {tamperRegions.map((t, idx) => (
              <Circle
                key={`t-${idx}`}
                x={t.x * width}
                y={t.y * height}
                radius={t.r * width * 0.2}
                fill="transparent"
                stroke="rgba(250,204,21,0.55)"
                strokeWidth={3}
                dash={[7, 7]}
              />
            ))}
          </Layer>
        )}

        {showPose && (
          <Layer listening={false}>
            {skeletonLines.map((pts, i) => (
              <Line
                key={i}
                points={pts}
                stroke={
                  wounds.some((w) => w.defensive)
                    ? 'rgba(0,245,255,0.96)'
                    : 'rgba(56,189,248,0.78)'
                }
                strokeWidth={3}
                shadowBlur={showWounds ? 14 : 0}
                shadowColor="rgba(0,245,255,1)"
              />
            ))}
            {scaledPoints.map((p, idx) => (
              <Circle
                key={`kp-${idx}`}
                x={p.x}
                y={p.y}
                radius={4}
                fill="#050810"
                stroke="#00f5ff"
                strokeWidth={2}
              />
            ))}
          </Layer>
        )}

        {measurePts.length === 4 && (
          <Layer listening={false}>
            <Line points={measurePts} stroke="rgba(0,245,255,0.85)" strokeWidth={2} dash={[4, 4]} />
            <Circle x={measurePts[0]} y={measurePts[1]} radius={5} fill="#00f5ff" />
            <Circle x={measurePts[2]} y={measurePts[3]} radius={5} fill="#991b1b" />
            <Text
              x={(measurePts[0] + measurePts[2]) / 2}
              y={(measurePts[1] + measurePts[3]) / 2 - 18}
              text={distLabel}
              fill="rgba(0,245,255,0.9)"
              fontSize={11}
              fontFamily="JetBrains Mono, monospace"
            />
          </Layer>
        )}

        {showWounds && (
          <Layer>
            {wounds.map((w) => {
              const px = w.x * width
              const py = w.y * height
              const active = selectedWoundId === w.id
              return (
                <Group
                  key={w.id}
                  onTap={(e) => {
                    e.cancelBubble = true
                    onSelectWound?.(active ? null : w.id)
                  }}
                  onClick={(e) => {
                    e.cancelBubble = true
                    onSelectWound?.(active ? null : w.id)
                  }}
                >
                  <Circle
                    x={px}
                    y={py}
                    radius={active ? 22 : 14}
                    fill={w.defensive ? 'rgba(0,245,255,0.16)' : 'rgba(153,27,27,0.35)'}
                    stroke={w.defensive ? '#00f5ff' : '#f87171'}
                    strokeWidth={active ? 3 : 2}
                    shadowBlur={active ? 22 : 0}
                    shadowColor="rgba(0,245,255,0.85)"
                  />
                  <Circle
                    x={px}
                    y={py}
                    radius={28}
                    fill="transparent"
                    stroke="transparent"
                  />
                </Group>
              )
            })}
          </Layer>
        )}
      </Stage>

      <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex justify-between font-mono text-[10px] text-muted-foreground">
        <span>
          POINTER {cursor ? `${cursor.x.toFixed(0)}, ${cursor.y.toFixed(0)}` : '—'} · ZOOM {(zoom * 100).toFixed(0)}%
        </span>
        <span className="text-primary/70">SCROLL · zoom · DRAG · pan</span>
      </div>
    </div>
  )
}
