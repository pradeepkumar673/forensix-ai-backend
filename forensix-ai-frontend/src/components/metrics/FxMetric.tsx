/**
 * Tremor-inspired telemetry tiles — tuned for Tailwind v4 + ForensiX tokens.
 * (@tremor/react targets Tailwind v3; these primitives match the same IA patterns.)
 */

import { cn } from '@/lib/utils'

type Trend = 'up' | 'down' | 'neutral'

export type FxMetricProps = {
  title: string
  metric: string | number
  subtitle?: string
  /** Optional delta label, e.g. "+12% vs last week" */
  delta?: string
  deltaTrend?: Trend
  className?: string
}

const trendCls: Record<Trend, string> = {
  up: 'text-emerald-400',
  down: 'text-rose-400',
  neutral: 'text-muted-foreground',
}

export function FxMetric({ title, metric, subtitle, delta, deltaTrend = 'neutral', className }: FxMetricProps) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-primary/15 bg-card/80 px-5 py-4 shadow-[var(--shadow-glass)] backdrop-blur-xl',
        className,
      )}
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted-foreground">{title}</p>
      <p className="mt-2 font-display text-3xl font-semibold tracking-tight text-card-foreground">{metric}</p>
      {subtitle && <p className="mt-1 font-mono text-[11px] text-muted-foreground">{subtitle}</p>}
      {delta && (
        <p className={cn('mt-2 font-mono text-[10px] uppercase tracking-wide', trendCls[deltaTrend])}>{delta}</p>
      )}
    </div>
  )
}
