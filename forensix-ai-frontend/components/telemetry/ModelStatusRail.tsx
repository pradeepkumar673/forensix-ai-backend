import { useQuery } from '@tanstack/react-query'

import { Badge } from '@/components/ui/badge'
import { getModelStatus } from '@/lib/api'

export function ModelStatusRail() {
  const q = useQuery({
    queryKey: ['model-status'],
    queryFn: () => getModelStatus(),
    refetchInterval: 45_000,
  })

  if (q.isLoading) {
    return (
      <div className="flex flex-wrap gap-2 rounded-lg border border-border/70 bg-muted/65 px-3 py-2 font-mono text-[11px] text-muted-foreground">
        Polling inference mesh…
      </div>
    )
  }

  if (q.isError) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/15 px-3 py-2 font-mono text-[11px] text-destructive">
        Neural analysis offline · model telemetry unreachable
      </div>
    )
  }

  const data = q.data
  if (!data) {
    return (
      <div className="flex flex-wrap gap-2 rounded-lg border border-border/70 bg-muted/65 px-3 py-2 font-mono text-[11px] text-muted-foreground">
        Telemetry payload empty · retry shortly
      </div>
    )
  }

  const provider = data.llm_provider
  const isFeatherless = provider === 'featherless'

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-border/70 bg-card/82 px-4 py-2 font-mono text-[11px] text-muted-foreground backdrop-blur-lg">
      <span className="flex items-center gap-2 uppercase tracking-[0.24em] text-primary/95">
        <span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgb(74,222,128)]" />
        live mesh
      </span>
      <span>
        PROVIDER{' '}
        <Badge variant="outline" className="ml-2 border-primary/55 text-primary">
          {isFeatherless ? 'Featherless (cloud inference)' : 'Ollama (local mesh)'}
        </Badge>
      </span>
      <span>
        VISION {(data as { vision_enabled: boolean }).vision_enabled ? 'ARMED' : 'STANDBY'}
      </span>
      <span>
        AUDIO {(data as { audio_enabled: boolean }).audio_enabled ? 'ARMED' : 'STANDBY'}
      </span>
      <span className="max-w-xl truncate uppercase">
        MODELS LOADED {(data as { loaded_hf_models: string[] }).loaded_hf_models?.join(', ') || 'NONE'}
      </span>
    </div>
  )
}
