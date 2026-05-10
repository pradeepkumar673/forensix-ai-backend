/**
 * Anatomical zones for the digital autopsy SVG (gym-chart style, front / back).
 * Normalized hit boxes map Konva wound coords (0–1) → muscle ids for highlight sync.
 */

export type MuscleId =
  | 'neck'
  | 'chest'
  | 'abs'
  | 'left_shoulder'
  | 'right_shoulder'
  | 'left_biceps'
  | 'right_biceps'
  | 'left_forearm'
  | 'right_forearm'
  | 'left_quad'
  | 'right_quad'
  | 'left_calf'
  | 'right_calf'
  | 'back_upper'
  | 'back_lower'
  | 'glutes'

/** (xmin, ymin, xmax, ymax) in normalized twin space — front view */
export const FRONT_MUSCLE_BOUNDS: Record<MuscleId, [number, number, number, number]> = {
  neck: [0.42, 0.06, 0.58, 0.14],
  chest: [0.34, 0.14, 0.66, 0.32],
  abs: [0.38, 0.32, 0.62, 0.46],
  left_shoulder: [0.22, 0.14, 0.38, 0.26],
  right_shoulder: [0.62, 0.14, 0.78, 0.26],
  left_biceps: [0.18, 0.26, 0.34, 0.4],
  right_biceps: [0.66, 0.26, 0.82, 0.4],
  left_forearm: [0.14, 0.4, 0.32, 0.56],
  right_forearm: [0.68, 0.4, 0.86, 0.56],
  left_quad: [0.36, 0.46, 0.48, 0.72],
  right_quad: [0.52, 0.46, 0.64, 0.72],
  left_calf: [0.38, 0.72, 0.48, 0.94],
  right_calf: [0.52, 0.72, 0.62, 0.94],
  back_upper: [0, 0, 0, 0],
  back_lower: [0, 0, 0, 0],
  glutes: [0, 0, 0, 0],
}

export const BACK_MUSCLE_BOUNDS: Record<MuscleId, [number, number, number, number]> = {
  ...FRONT_MUSCLE_BOUNDS,
  chest: [0, 0, 0, 0],
  abs: [0, 0, 0, 0],
  left_quad: [0.36, 0.46, 0.48, 0.72],
  right_quad: [0.52, 0.46, 0.64, 0.72],
  neck: [0.42, 0.06, 0.58, 0.14],
  back_upper: [0.32, 0.14, 0.68, 0.36],
  back_lower: [0.34, 0.36, 0.66, 0.52],
  glutes: [0.34, 0.48, 0.66, 0.62],
  left_shoulder: [0.2, 0.14, 0.36, 0.28],
  right_shoulder: [0.64, 0.14, 0.8, 0.28],
}

export function musclesFromNormalizedPoints(
  view: 'front' | 'back',
  points: Array<{ x: number; y: number }>,
): MuscleId[] {
  const bounds = view === 'front' ? FRONT_MUSCLE_BOUNDS : BACK_MUSCLE_BOUNDS
  const hit = new Set<MuscleId>()
  for (const p of points) {
    for (const id of Object.keys(bounds) as MuscleId[]) {
      const b = bounds[id]
      if (b[2] <= b[0]) continue
      if (p.x >= b[0] && p.x <= b[2] && p.y >= b[1] && p.y <= b[3]) hit.add(id)
    }
  }
  return [...hit]
}

/** Demo injuries shown when an exhibit is ingested (judges / offline API). */
export const DEMO_TRAUMA_FRONT: Array<{
  muscle: MuscleId
  label: string
  x: number
  y: number
}> = [
  { muscle: 'chest', label: 'Penetrating trauma — thoracic entry', x: 0.5, y: 0.22 },
  { muscle: 'abs', label: 'Secondary stab — epigastric', x: 0.48, y: 0.38 },
  { muscle: 'left_biceps', label: 'Defensive slash — brachial', x: 0.26, y: 0.32 },
]

export const DEMO_TRAUMA_BACK: Array<{ muscle: MuscleId; label: string; x: number; y: number }> = [
  { muscle: 'back_upper', label: 'Exit wound — scapular', x: 0.44, y: 0.24 },
  { muscle: 'glutes', label: 'Superficial laceration', x: 0.52, y: 0.54 },
]
