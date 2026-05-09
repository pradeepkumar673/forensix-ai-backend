/**
 * Interactive 2D digital autopsy twin (front / back).
 * Renders silhouette in Konva, overlays MedSAM-style heat zones + ViTPose-style skeleton links.
 */

import Konva from 'konva'
import { useMemo, useRef, useState } from 'react'
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

/** COCO-ish leg lines for illustrative skeleton overlay */
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

type Props = {
  view: 'front' | 'back'
  zoom: number
  showWounds: boolean
  showSpatter?: boolean
  showPose: boolean
  showTampering: boolean
  heatZones?: Array<{ id: string; x: number; y: number; r: number; intensity: number }>
  poseKeypoints?: PosePoint[]
  wounds?: WoundHit[]
  tamperRegions?: Array<{ x: number; y: number; r: number }>
  selectedWoundId: string | null
  onSelectWound?: (id: string | null) => void
  width?: number
  height?: number
}

function Silhouette({ view }: { view: 'front' | 'back' }) {
  const stroke = 'rgba(34,211,238,0.35)'
  const fill = 'rgba(15,23,42,0.75)'

  if (view === 'back') {
    return (
      <Group listening={false}>
        <Circle x={200} y={85} radius={42} stroke={stroke} strokeWidth={2} fill={fill} />
        <Rect x={154} y={138} width={92} height={140} stroke={stroke} strokeWidth={2} fill={fill} />
        <Rect x={100} y={155} width={52} height={22} stroke={stroke} strokeWidth={2} fill={fill} />
        <Rect x={248} y={155} width={52} height={22} stroke={stroke} strokeWidth={2} fill={fill} />
        <Rect x={173} y={285} width={28} height={95} stroke={stroke} strokeWidth={2} fill={fill} />
        <Rect x={201} y={285} width={28} height={95} stroke={stroke} strokeWidth={2} fill={fill} />
      </Group>
    )
  }

  return (
    <Group listening={false}>
      <Circle x={200} y={85} radius={42} stroke={stroke} strokeWidth={2} fill={fill} />
      <Rect x={154} y={138} width={92} height={140} stroke={stroke} strokeWidth={2} fill={fill} />
      <Rect x={100} y={155} width={52} height={22} stroke={stroke} strokeWidth={2} fill={fill} />
      <Rect x={248} y={155} width={52} height={22} stroke={stroke} strokeWidth={2} fill={fill} />
      <Rect x={173} y={285} width={28} height={95} stroke={stroke} strokeWidth={2} fill={fill} />
      <Rect x={201} y={285} width={28} height={95} stroke={stroke} strokeWidth={2} fill={fill} />
    </Group>
  )
}

export function BodyMapTwin({
  view,
  zoom,
  showWounds,
  showSpatter,
  showPose,
  showTampering,
  poseKeypoints = [],
  heatZones = [],
  wounds = [],
  tamperRegions = [],
  selectedWoundId,
  onSelectWound,
  width = 400,
  height = 420,
}: Props) {
  const stageRef = useRef<Konva.Stage>(null)
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)

  const scaledPoints = useMemo(() => {
    return poseKeypoints.map((p) => ({
      x: p.x * width,
      y: p.y * height,
      label: p.label,
    }))
  }, [poseKeypoints, width, height])

  const skeletonLines = useMemo(() => {
    if (!showPose || scaledPoints.length === 0) return []
    return POSE_EDGES.map(([a, b]) => {
      const pa = scaledPoints[a]
      const pb = scaledPoints[b]
      if (!pa || !pb) return null
      return [pa.x, pa.y, pb.x, pb.y] as number[]
    }).filter(Boolean) as number[][]
  }, [scaledPoints, showPose])

  return (
    <div className="relative overflow-hidden rounded-xl border border-border/70 bg-muted/60">
      <Stage
        ref={stageRef}
        width={width}
        height={height}
        scaleX={zoom}
        scaleY={zoom}
        onWheel={(e) => {
          e.evt.preventDefault()
        }}
        className="mx-auto cursor-crosshair"
        onMouseMove={(e) => {
          const p = stageRef.current?.getRelativePointerPosition()
          if (!p) return
          const inv = Math.max(zoom, 0.001)
          setCursor({ x: p.x / inv, y: p.y / inv })
        }}
      >
        <Layer listening={false}>
          <Text
            text={view === 'front' ? 'ANTERIOR' : 'POSTERIOR'}
            x={12}
            y={10}
            fill="rgba(34,211,238,0.6)"
            fontSize={11}
            fontFamily="JetBrains Mono, monospace"
            letterSpacing={3}
          />
        </Layer>
        <Layer listening={false}>
          <Silhouette view={view} />
        </Layer>

        {/* MedSAM-inspired heat halo */}
        {heatZones.map((z) => (
          <Layer key={z.id} listening={false}>
            <Circle
              x={z.x * width}
              y={z.y * height}
              radius={Math.max(z.r * width * 0.15, 6)}
              fill={`rgba(153,27,27,${0.12 + z.intensity * 0.45})`}
              stroke={`rgba(34,211,238,${0.35 + z.intensity * 0.3})`}
              strokeWidth={1.5}
            />
          </Layer>
        ))}

        {showSpatter && (
          <Layer listening={false}>
            {[
              [0.32, 0.18, 3],
              [0.68, 0.22, 2.5],
              [0.54, 0.36, 2],
              [0.41, 0.44, 2.8],
            ].map(([x, y, r], idx) => (
              <Circle
                key={`sp-${idx}`}
                x={(x as number) * width}
                y={(y as number) * height}
                radius={(r as number)}
                stroke="rgba(239,68,68,0.85)"
                fill="rgba(153,27,27,0.22)"
                strokeWidth={2}
              />
            ))}
          </Layer>
        )}

        {showTampering &&
          tamperRegions.map((t, idx) => (
            <Layer key={`t-${idx}`} listening={false}>
              <Circle
                x={t.x * width}
                y={t.y * height}
                radius={t.r * width * 0.2}
                fill="transparent"
                stroke="rgba(250,204,21,0.55)"
                strokeWidth={3}
                dash={[6, 6]}
              />
            </Layer>
          ))}

        {showPose && (
          <Layer listening={false}>
            {skeletonLines.map((pts, i) => (
              <Line
                key={i}
                points={pts}
                stroke={
                  wounds.some((w) => w.defensive)
                    ? 'rgba(34,211,238,0.95)'
                    : 'rgba(56,189,248,0.75)'
                }
                strokeWidth={3}
                shadowBlur={showWounds ? 10 : 0}
                shadowColor="rgb(34,211,238)"
              />
            ))}
            {scaledPoints.map((p, idx) => (
              <Circle
                key={`kp-${idx}`}
                x={p.x}
                y={p.y}
                radius={4}
                fill="rgba(15,23,42,1)"
                stroke="rgba(34,211,238,1)"
                strokeWidth={2}
              />
            ))}
          </Layer>
        )}

        {/* Wounds + hit targets */}
        {showWounds && (
          <Layer>
            {wounds.map((w) => {
              const px = w.x * width
              const py = w.y * height
              const active = selectedWoundId === w.id
              return (
                <Group key={w.id}>
                  <Circle
                    x={px}
                    y={py}
                    radius={active ? 16 : 12}
                    fill={
                      w.defensive
                        ? 'rgba(34,211,238,0.22)'
                        : 'rgba(153,27,27,0.32)'
                    }
                    stroke={active ? 'rgb(34,211,238)' : 'rgba(239,68,68,0.75)'}
                    strokeWidth={2}
                    listening
                    shadowBlur={active ? 12 : 0}
                    shadowColor="rgb(34,211,238)"
                    onTap={() => onSelectWound?.(active ? null : w.id)}
                    onClick={() => onSelectWound?.(active ? null : w.id)}
                  />
                  <Circle
                    x={px}
                    y={py}
                    radius={22}
                    fill="transparent"
                    stroke="transparent"
                    listening
                    onTap={() => onSelectWound?.(active ? null : w.id)}
                    onClick={() => onSelectWound?.(active ? null : w.id)}
                  />
                </Group>
              )
            })}
          </Layer>
        )}
      </Stage>

      {cursor && (
        <div className="pointer-events-none absolute bottom-3 right-4 font-mono text-[10px] text-muted-foreground">
          XYZ↦ {cursor.x.toFixed(0)}, {cursor.y.toFixed(0)} · SCALE {zoom.toFixed(2)}× ·{' '}
          <span className="text-accent">classified grid</span>
        </div>
      )}
    </div>
  )
}
