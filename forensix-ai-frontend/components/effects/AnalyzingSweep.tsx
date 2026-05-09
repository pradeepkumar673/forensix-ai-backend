/** Horizontal scan stripe while AI pipelines run. */

import { motion } from 'framer-motion'

export function AnalyzingSweep({ active }: { active: boolean }) {
  if (!active) return null
  return (
    <motion.div
      className="pointer-events-none absolute inset-0 z-20 overflow-hidden rounded-[inherit]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <motion.div
        className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent opacity-85 shadow-[0_0_20px_rgb(34,211,238)]"
        initial={{ top: '0%' }}
        animate={{ top: '100%' }}
        transition={{ repeat: Infinity, duration: 2.8, ease: 'linear' }}
      />
      <motion.div
        className="absolute inset-0 rounded-[inherit] ring-2 ring-primary/35"
        animate={{ opacity: [0.2, 0.55, 0.25] }}
        transition={{ repeat: Infinity, duration: 2.6 }}
      />
    </motion.div>
  )
}
