import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from 'recharts'

/** Tremor-inspired radial gauge using Recharts (Tailwind v4 friendly). */
export function RiskGaugeCard({
  title,
  value,
  subtitle,
}: {
  title: string
  value: number
  subtitle: string
}) {
  const capped = Math.max(0, Math.min(100, value))
  const data = [{ name: 'risk', value: capped, fill: capped > 75 ? '#991b1b' : capped > 45 ? '#f59e0b' : '#00f5ff' }]
  return (
    <div className="metric-card holo-ring flex flex-col items-center justify-between gap-2">
      <p className="w-full font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">{title}</p>
      <div className="relative h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart innerRadius="68%" outerRadius="100%" data={data} startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar background={{ fill: 'rgba(15,31,61,0.9)' }} dataKey="value" cornerRadius={10} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-4">
          <span className="font-display text-3xl font-semibold text-card-foreground">{capped.toFixed(0)}</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">IDX</span>
        </div>
      </div>
      <p className="text-center font-mono text-[11px] text-muted-foreground">{subtitle}</p>
    </div>
  )
}
