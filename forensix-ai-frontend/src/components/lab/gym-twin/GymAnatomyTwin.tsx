/**
 * Gym-project–style muscle silhouette (SVG) for forensic twin highlights.
 * Simplified vector anatomy; regions pulse when matched to wound / segmentation data.
 */

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { MuscleId } from './muscleRegions'

type Props = {
  view: 'front' | 'back'
  highlighted: Set<MuscleId>
  className?: string
}

function regionClass(active: boolean) {
  return cn(
    'stroke-[1.2] transition-colors duration-300',
    active
      ? 'fill-[rgba(153,27,27,0.55)] stroke-[#00f5ff] drop-shadow-[0_0_12px_rgba(0,245,255,0.45)]'
      : 'fill-[rgba(15,31,61,0.55)] stroke-[rgba(0,245,255,0.22)]',
  )
}

export function GymAnatomyTwin({ view, highlighted, className }: Props) {
  const h = (id: MuscleId) => highlighted.has(id)

  if (view === 'back') {
    return (
      <motion.svg
        viewBox="0 0 200 420"
        className={cn('h-full max-h-[520px] w-auto overflow-visible', className)}
        initial={{ opacity: 0.85 }}
        animate={{ opacity: 1 }}
      >
        <title>Posterior anatomical reference</title>
        {/* Head */}
        <ellipse cx="100" cy="38" rx="22" ry="26" className={regionClass(h('neck'))} />
        {/* Upper back */}
        <path
          d="M 62 64 Q 100 52 138 64 L 132 118 Q 100 108 68 118 Z"
          className={regionClass(h('back_upper'))}
        />
        {/* Lower back */}
        <path
          d="M 68 118 L 132 118 L 128 168 Q 100 162 72 168 Z"
          className={regionClass(h('back_lower'))}
        />
        {/* Glutes */}
        <path
          d="M 72 168 Q 100 158 128 168 L 124 210 Q 100 222 76 210 Z"
          className={regionClass(h('glutes'))}
        />
        {/* Rear shoulders */}
        <path d="M 48 70 L 62 64 L 68 118 L 52 124 Z" className={regionClass(h('left_shoulder'))} />
        <path d="M 152 70 L 138 64 L 132 118 L 148 124 Z" className={regionClass(h('right_shoulder'))} />
        {/* Ham / leg block simplified */}
        <path d="M 76 210 L 92 210 L 88 360 L 78 360 Z" className={regionClass(h('left_calf'))} />
        <path d="M 124 210 L 108 210 L 112 360 L 122 360 Z" className={regionClass(h('right_calf'))} />
      </motion.svg>
    )
  }

  return (
    <motion.svg
      viewBox="0 0 200 420"
      className={cn('h-full max-h-[520px] w-auto overflow-visible', className)}
      initial={{ opacity: 0.85 }}
      animate={{ opacity: 1 }}
    >
      <title>Anterior anatomical reference — gym chart lineage</title>
      {/* Neck */}
      <path
        d="M 88 52 L 112 52 L 110 72 L 90 72 Z"
        className={regionClass(h('neck'))}
      />
      {/* Head */}
      <ellipse cx="100" cy="34" rx="20" ry="24" className="fill-[rgba(8,14,28,0.9)] stroke-[rgba(0,245,255,0.35)] stroke-[1]" />
      {/* Chest */}
      <path
        d="M 70 72 Q 100 62 130 72 L 126 128 Q 100 120 74 128 Z"
        className={regionClass(h('chest'))}
      />
      {/* Abs */}
      <path
        d="M 74 128 L 126 128 L 122 178 Q 100 172 78 178 Z"
        className={regionClass(h('abs'))}
      />
      {/* Shoulders */}
      <path d="M 52 76 L 70 72 L 74 108 L 58 118 Z" className={regionClass(h('left_shoulder'))} />
      <path d="M 148 76 L 130 72 L 126 108 L 142 118 Z" className={regionClass(h('right_shoulder'))} />
      {/* Biceps */}
      <path d="M 58 118 L 74 108 L 78 152 L 62 158 Z" className={regionClass(h('left_biceps'))} />
      <path d="M 142 118 L 126 108 L 122 152 L 138 158 Z" className={regionClass(h('right_biceps'))} />
      {/* Forearms */}
      <path d="M 62 158 L 78 152 L 72 210 L 56 214 Z" className={regionClass(h('left_forearm'))} />
      <path d="M 138 158 L 122 152 L 128 210 L 144 214 Z" className={regionClass(h('right_forearm'))} />
      {/* Quads */}
      <path d="M 78 178 L 98 178 L 94 300 L 82 300 Z" className={regionClass(h('left_quad'))} />
      <path d="M 122 178 L 102 178 L 106 300 L 118 300 Z" className={regionClass(h('right_quad'))} />
      {/* Calves */}
      <path d="M 82 300 L 94 300 L 92 400 L 84 400 Z" className={regionClass(h('left_calf'))} />
      <path d="M 118 300 L 106 300 L 108 400 L 116 400 Z" className={regionClass(h('right_calf'))} />
    </motion.svg>
  )
}
