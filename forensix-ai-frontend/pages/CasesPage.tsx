import { useMemo, useState } from 'react'
import { format } from 'date-fns'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { ModelStatusRail } from '@/components/telemetry/ModelStatusRail'
import type { ForensicCase, RiskBand } from '@/stores/case-store'
import { useCaseStore } from '@/stores/case-store'

function riskColor(b: RiskBand) {
  switch (b) {
    case 'critical':
      return 'bg-accent text-accent-foreground border-accent'
    case 'high':
      return 'bg-orange-950/80 text-orange-200 border-orange-600/60'
    case 'medium':
      return 'bg-amber-950/60 text-amber-100 border-amber-700/50'
    default:
      return 'bg-primary/25 text-primary border-primary/35'
  }
}

export default function CasesPage() {
  const cases = useCaseStore((s) => s.cases)
  const setActive = useCaseStore((s) => s.setActiveCase)
  const addCase = useCaseStore((s) => s.addCase)
  const removeCase = useCaseStore((s) => s.removeCase)
  const active = useCaseStore((s) => s.activeCaseId)

  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState({
    code: 'CBI-2035-',
    title: '',
    synopsis: '',
    jurisdiction: 'National Capital Region',
    custodyLevel: 'TIER-III',
    riskBand: 'medium' as RiskBand,
    tags: 'homicide,digital-twin',
  })

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return cases
    return cases.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        c.tags.some((t) => t.includes(q))
    )
  }, [cases, filter])

  function submitNew() {
    addCase({
      code: draft.code,
      title: draft.title || 'Untitled investigation',
      synopsis: draft.synopsis,
      jurisdiction: draft.jurisdiction,
      custodyLevel: draft.custodyLevel,
      riskBand: draft.riskBand,
      tags: draft.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    })
    setOpen(false)
  }

  return (
    <div className="space-y-10 px-6 py-12 pb-32">
      <header className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-primary/90">Custody matrix</p>
          <h1 className="mt-3 font-display text-4xl font-semibold">Case envelope registry</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Every UUID below is accepted by FastAPI as <code className="font-mono text-primary">case_id</code> query
            parameters.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="h-12 px-8 font-display tracking-wide">New forensic envelope</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto border-primary/45 bg-muted/95 backdrop-blur-xl">
            <DialogHeader>
              <DialogTitle className="font-display">Classified case shell</DialogTitle>
              <DialogDescription>Metadata is local-first; chain with backend analysis runs.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label>Case code</Label>
                <Input value={draft.code} onChange={(e) => setDraft((d) => ({ ...d, code: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={draft.title} onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Synopsis</Label>
                <Textarea
                  rows={4}
                  value={draft.synopsis}
                  onChange={(e) => setDraft((d) => ({ ...d, synopsis: e.target.value }))}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Jurisdiction</Label>
                  <Input
                    value={draft.jurisdiction}
                    onChange={(e) => setDraft((d) => ({ ...d, jurisdiction: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Custody band</Label>
                  <Input
                    value={draft.custodyLevel}
                    onChange={(e) => setDraft((d) => ({ ...d, custodyLevel: e.target.value }))}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>Risk posture</Label>
                  <Select
                    value={draft.riskBand}
                    onValueChange={(v: RiskBand) => setDraft((d) => ({ ...d, riskBand: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Tags (comma-separated)</Label>
                  <Input value={draft.tags} onChange={(e) => setDraft((d) => ({ ...d, tags: e.target.value }))} />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                Abort
              </Button>
              <Button onClick={submitNew}>Commit envelope</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      <ModelStatusRail />

      <Card className="glass-panel-strong rounded-2xl">
        <CardHeader className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Dossiers</CardTitle>
            <CardDescription>Filter by synopsis fragments, forensic tags or exhibit codes.</CardDescription>
          </div>
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter matrix…"
            className="md:max-w-sm"
          />
        </CardHeader>
        <CardContent className="-mx-px">
          <ScrollArea className="h-[min(62vh,calc(100vh-360px))]">
            <div className="space-y-[2px] pr-5">
              {filtered.map((c) => (
                <CaseTimelineRow
                  key={c.id}
                  c={c}
                  active={active}
                  onSelect={() => setActive(c.id)}
                  onDestroy={() => removeCase(c.id)}
                  riskClass={riskColor(c.riskBand)}
                />
              ))}
              {filtered.length === 0 && (
                <p className="p-12 text-center font-mono text-sm text-muted-foreground">
                  Empty registry — hydrate from “New forensic envelope”.
                </p>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}

function CaseTimelineRow({
  c,
  active,
  onSelect,
  onDestroy,
  riskClass,
}: {
  c: ForensicCase
  active: string | null
  onSelect: () => void
  onDestroy: () => void
  riskClass: string
}) {
  return (
    <div
      className={`grid gap-4 rounded-xl border border-border/80 bg-muted/75 p-5 transition md:grid-cols-[1fr_auto] ${
        active === c.id ? 'ring-2 ring-primary/55' : ''
      }`}
    >
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <p className="font-display text-xl">{c.title}</p>
          <Badge className={riskClass}>{c.riskBand}</Badge>
          <Badge variant="outline" className="font-mono text-[10px] uppercase">
            {c.custodyLevel}
          </Badge>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{c.synopsis || '— no synopsis —'}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {c.tags.map((t) => (
            <span key={t} className="rounded-full border border-primary/35 px-2 py-0.5 font-mono text-[10px] text-primary">
              {t}
            </span>
          ))}
        </div>
        <Separator className="my-4 bg-border/60" />
        <p className="font-mono text-[11px] text-muted-foreground">
          UUID <span className="text-primary">{c.id}</span> · updated {format(new Date(c.updatedAt), 'PPpp')}
        </p>
      </div>
      <div className="flex flex-col justify-center gap-2 md:items-end">
        <Button size="sm" variant="secondary" onClick={onSelect}>
          Set active lock
        </Button>
        <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={onDestroy}>
          Purge local shell
        </Button>
      </div>
    </div>
  )
}
