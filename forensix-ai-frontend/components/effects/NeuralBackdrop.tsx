/**
 * Subtle drifting nodes — evokes an always-on neural mesh behind glass panels.
 */
import { motion } from 'framer-motion'

const NODES = 48

export function NeuralBackdrop({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden opacity-35 ${className}`}
    >
      <motion.svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="1.2" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="neon" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgb(34,211,238)" stopOpacity="0.85" />
            <stop offset="100%" stopColor="rgb(56,189,248)" stopOpacity="0.35" />
          </linearGradient>
        </defs>
        {Array.from({ length: NODES }).map((_, i) => (
          <motion.circle
            key={i}
            r={Math.random() * 1.2 + 0.4}
            fill="url(#neon)"
            filter="url(#glow)"
            initial={{
              cx: `${(i * 9301 + 49297) % 233 / 232 * 100}%`,
              cy: `${(i * 7919 + 104729) % 233 / 232 * 100}%`,
              opacity: 0.35,
            }}
            animate={{
              cx: `${((i + 11) * 8831 + 49297) % 233 / 232 * 100}%`,
              cy: `${((i + 23) * 7523 + 104729) % 233 / 232 * 100}%`,
              opacity: [0.2, 0.85, 0.25],
            }}
            transition={{
              duration: 18 + i * 0.12,
              repeat: Infinity,
              repeatType: 'reverse',
              ease: 'easeInOut',
            }}
          />
        ))}
      </motion.svg>
    </div>
  )
}
