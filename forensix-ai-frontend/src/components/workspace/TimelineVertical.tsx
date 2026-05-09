import { motion } from 'framer-motion'

export type TimelineEvt = {
  event_id?: string
  description?: string
  timestamp?: string | null
  event_type?: string
}

/** Vertical forensic chronology with contradiction pulses driven by backend gap strings. */
export function TimelineVertical({
  events,
  contradictions,
}: {
  events: TimelineEvt[]
  contradictions: string[]
}) {
  const contradictionPulse = contradictions.length > 0
  return (
    <div className="relative mx-auto max-w-3xl pl-8">
      <div className="absolute bottom-0 left-[11px] top-0 w-px bg-gradient-to-b from-primary/60 via-primary/20 to-transparent" />
      {events.length === 0 ? (
        <p className="font-mono text-sm text-muted-foreground">
          No anchored chronology — POST `/correlate/timeline` with UTF-8 exhibits.
        </p>
      ) : (
        events.map((ev, idx) => (
          <motion.div
            key={ev.event_id ?? idx}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.04 }}
            className="relative mb-8"
          >
            <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full border border-primary bg-[#0a1428] shadow-[0_0_16px_rgba(0,245,255,0.35)]" />
            <div className="rounded-2xl border border-primary/15 bg-card/70 px-4 py-3 font-mono">
              <p className="text-[10px] uppercase tracking-[0.28em] text-primary">
                {ev.timestamp ?? 'TIME UNKNOWN'} · {ev.event_type ?? 'EVENT'}
              </p>
              <p className="mt-2 text-sm text-card-foreground">{ev.description}</p>
            </div>
          </motion.div>
        ))
      )}
      {contradictionPulse && (
        <motion.div
          className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-3 font-mono text-xs text-accent-foreground"
          animate={{ boxShadow: ['0 0 0 0 rgba(239,68,68,0)', '0 0 0 6px rgba(239,68,68,0.25)', '0 0 0 0 rgba(239,68,68,0)'] }}
          transition={{ duration: 2.4, repeat: Infinity }}
        >
          <p className="text-[10px] uppercase tracking-[0.3em] text-accent">Contradiction manifold</p>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {contradictions.slice(0, 6).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  )
}
