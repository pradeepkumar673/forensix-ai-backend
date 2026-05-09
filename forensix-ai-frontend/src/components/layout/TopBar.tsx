import { CircleDot, Cpu, Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { qk } from '@/lib/query-keys'
import { getModelStatus, getReady } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'
import { useCaseStore, useActiveCase } from '@/stores/case-store'
import { useUiStore } from '@/stores/ui-store'
import { cn } from '@/lib/utils'

export function TopBar() {
  const investigator = useAuthStore((s) => s.investigatorName)
  const cases = useCaseStore((s) => s.cases)
  const activeId = useCaseStore((s) => s.activeCaseId)
  const setActive = useCaseStore((s) => s.setActiveCase)
  const active = useActiveCase()
  const setOracle = useUiStore((s) => s.setOracleOpen)

  const readyQ = useQuery({ queryKey: qk.ready, queryFn: getReady, refetchInterval: 45_000 })
  const modelsQ = useQuery({ queryKey: qk.models, queryFn: getModelStatus, refetchInterval: 60_000 })

  const meshOk = readyQ.data?.ready !== false
  const llm = modelsQ.data?.llm_provider ?? '…'

  return (
    <header className="flex h-[60px] items-center gap-4 border-b border-primary/10 bg-background/75 px-4 backdrop-blur-xl">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Cpu className="hidden h-5 w-5 shrink-0 text-primary md:inline" />
        <div className="min-w-0">
          <p className="truncate font-display text-sm font-semibold text-card-foreground md:text-base">
            Tactical Neural Workspace
          </p>
          <p className="truncate font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
            Investigator /{' '}
            <span className="text-primary/90">{investigator || '— UNSIGNED —'}</span>
          </p>
        </div>
      </div>

      <div className="hidden items-center gap-2 lg:flex">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          Case vector
        </span>
        <Select value={activeId ?? ''} onValueChange={(v) => setActive(v || null)}>
          <SelectTrigger className="h-9 w-[220px] border-primary/20 bg-card/80 font-mono text-xs">
            <SelectValue placeholder="Attach dossier…" />
          </SelectTrigger>
          <SelectContent className="max-h-72">
            {cases.map((c) => (
              <SelectItem key={c.id} value={c.id} className="font-mono text-xs">
                {c.referenceCode} — {c.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="ghost" size="sm" className="font-mono text-[11px] text-primary" asChild>
          <Link to="/cases/new">New dossier</Link>
        </Button>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Badge
          variant="outline"
          className={cn(
            'hidden gap-1 border-primary/30 font-mono text-[10px] uppercase md:flex',
            meshOk ? 'text-emerald-400/90' : 'text-amber-300/90',
          )}
        >
          <CircleDot className="h-3 w-3" />
          {meshOk ? 'Mesh nominal' : 'Mesh degraded'}
        </Badge>
        <Badge variant="outline" className="hidden border-primary/25 font-mono text-[10px] uppercase sm:flex">
          LLM / {llm}
        </Badge>
        <Badge variant="outline" className="border-accent/40 font-mono text-[10px] uppercase text-accent-foreground/90">
          {active?.riskBand ?? '—'} risk
        </Badge>
        <Button
          size="sm"
          className="gap-2 bg-primary/15 font-display text-primary hover:bg-primary/25"
          variant="outline"
          type="button"
          onClick={() => setOracle(true)}
        >
          <Sparkles className="h-4 w-4" />
          Oracle
        </Button>
      </div>
    </header>
  )
}
