import { motion } from 'framer-motion'

/** Animated aurora + drifting particles behind dashboard shells. */
export function CyberBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <motion.div
        className="absolute -left-1/4 top-0 h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle,rgba(0,245,255,0.14),transparent_68%)] blur-3xl"
        animate={{ x: [0, 40, 0], y: [0, 24, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute -right-1/4 bottom-0 h-[480px] w-[480px] rounded-full bg-[radial-gradient(circle,rgba(153,27,27,0.16),transparent_65%)] blur-3xl"
        animate={{ x: [0, -32, 0], y: [0, -20, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: 'easeInOut' }}
      />
      <div className="absolute inset-0 opacity-[0.035] [background-image:linear-gradient(rgba(0,245,255,0.35)_1px,transparent_1px),linear-gradient(90deg,rgba(0,245,255,0.35)_1px,transparent_1px)] [background-size:56px_56px]" />
    </div>
  )
}
