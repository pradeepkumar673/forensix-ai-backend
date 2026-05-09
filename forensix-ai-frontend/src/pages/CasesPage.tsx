import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Filter } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { type ForensicCase, useCaseStore } from '@/stores/case-store'

export default function CasesPage() {
  const cases = useCaseStore((s) => s.cases)
  const setActive = useCaseStore((s) => s.setActiveCase)
  const [status, setStatus] = useState<string>('all')
  const [risk, setRisk] = useState<string>('all')
  const [typeQ, setTypeQ] = useState('')
  const [dateQ, setDateQ] = useState('')

  const filtered = useMemo(() => {
    return cases.filter((c) => {
      if (status !== 'all' && c.status !== status) return false
      if (risk !== 'all' && c.riskBand !== risk) return false
      if (typeQ && !c.caseType.toLowerCase().includes(typeQ.toLowerCase())) return false
      if (dateQ && !c.openedAt.startsWith(dateQ)) return false
      return true
    })
  }, [cases, status, risk, typeQ, dateQ])

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-primary">Case registry</p>
          <h1 className="font-display text-4xl font-semibold text-card-foreground">Operational dossiers</h1>
        </div>
        <Button asChild className="bg-primary font-display text-primary-foreground hover:bg-primary/90">
          <Link to="/cases/new">New dossier</Link>
        </Button>
      </header>

      <Card className="glass-panel border-primary/20">
        <CardHeader className="flex flex-col gap-4 border-b border-primary/10 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="font-display text-lg">Lattice filters</CardTitle>
              <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
                Slice vault mirrors client-side
              </CardDescription>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-[140px] border-primary/20 bg-background/70 font-mono text-xs">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="cold">Cold</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select value={risk} onValueChange={setRisk}>
              <SelectTrigger className="w-[160px] border-primary/20 bg-background/70 font-mono text-xs">
                <SelectValue placeholder="Risk band" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All risk</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Case type contains…"
              value={typeQ}
              onChange={(e) => setTypeQ(e.target.value)}
              className="w-[180px] border-primary/20 bg-background/70 font-mono text-xs"
            />
            <Input
              type="date"
              value={dateQ}
              onChange={(e) => setDateQ(e.target.value)}
              className="w-[160px] border-primary/20 bg-background/70 font-mono text-xs"
            />
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/15 hover:bg-transparent">
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Ref</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Title</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Type</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Risk</TableHead>
                <TableHead className="font-mono text-[11px] uppercase text-muted-foreground">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((c: ForensicCase) => (
                <TableRow key={c.id} className="border-primary/10">
                  <TableCell className="font-mono text-xs text-primary">{c.referenceCode}</TableCell>
                  <TableCell className="font-display">{c.title}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{c.caseType}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-primary/30 font-mono text-[10px] uppercase">
                      {c.riskBand}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button size="sm" variant="outline" className="font-mono text-[11px]" type="button" onClick={() => setActive(c.id)}>
                      Attach active
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-12 text-center font-mono text-muted-foreground">
                    Empty lattice — widen filters or mint dossier.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
