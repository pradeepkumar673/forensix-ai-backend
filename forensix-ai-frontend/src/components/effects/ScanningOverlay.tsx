import { motion, AnimatePresence } from 'framer-motion'
import { useUiStore } from '@/stores/ui-store'

/** Full-screen forensic scan shimmer while AI pipelines execute. */
export function ScanningOverlay() {
  const scanning = useUiStore((s) => s.scanning)
  return (
    <AnimatePresence>
      {scanning ? (
        <motion.div
          key="scan"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="pointer-events-none fixed inset-0 z-[9997] flex items-center justify-center bg-background/40 backdrop-blur-[2px]"
        >
          <motion.div
            className="relative h-px w-[min(520px,80vw)] overflow-hidden rounded-full bg-primary/40"
            initial={{ scaleX: 0.3 }}
            animate={{ scaleX: [0.3, 1, 0.45, 1] }}
            transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
          >
            <motion.div
              className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-primary to-transparent opacity-90"
              animate={{ x: ['-100%', '200%'] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
            />
          </motion.div>
          <p className="absolute bottom-24 font-mono text-[11px] uppercase tracking-[0.42em] text-primary/80">
            Neural cortex harmonizing evidence tensors…
          </p>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
