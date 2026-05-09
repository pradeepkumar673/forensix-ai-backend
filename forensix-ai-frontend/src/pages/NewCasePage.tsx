import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCaseStore, type RiskBand } from '@/stores/case-store'

export default function NewCasePage() {
  const navigate = useNavigate()
  const addCase = useCaseStore((s) => s.addCase)
  const [title, setTitle] = useState('')
  const [referenceCode, setReferenceCode] = useState('')
  const [caseType, setCaseType] = useState('Homicide')
  const [jurisdiction, setJurisdiction] = useState('')
  const [summary, setSummary] = useState('')
  const [victimAlias, setVictimAlias] = useState('')
  const [sceneLocation, setSceneLocation] = useState('')
  const [status, setStatus] = useState<'active' | 'cold' | 'closed'>('active')
  const [riskBand, setRiskBand] = useState<RiskBand>('medium')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    addCase({
      title,
      referenceCode: referenceCode || `FX-${crypto.randomUUID().slice(0, 8).toUpperCase()}`,
      status,
      riskBand,
      caseType,
      jurisdiction,
      summary,
      victimAlias,
      sceneLocation,
    })
    navigate('/cases')
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-primary">Mint dossier</p>
        <h1 className="font-display text-4xl font-semibold text-card-foreground">New forensic case</h1>
      </header>

      <Card className="glass-panel-strong border-primary/25">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <Database className="h-6 w-6 text-primary" />
            Metadata envelope
          </CardTitle>
          <CardDescription className="font-mono text-[11px] uppercase tracking-[0.22em]">
            Persisted locally · hydrate backend pipelines via active UUID selectors
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-5 md:grid-cols-2" onSubmit={submit}>
            <div className="space-y-2 md:col-span-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Title</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} required className="border-primary/25 bg-background/70" />
            </div>
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Reference code</Label>
              <Input value={referenceCode} onChange={(e) => setReferenceCode(e.target.value)} placeholder="Auto if blank" className="border-primary/25 bg-background/70 font-mono text-xs" />
            </div>
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Case type</Label>
              <Input value={caseType} onChange={(e) => setCaseType(e.target.value)} className="border-primary/25 bg-background/70" />
            </div>
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Jurisdiction</Label>
              <Input value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} required className="border-primary/25 bg-background/70" />
            </div>
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Victim alias</Label>
              <Input value={victimAlias} onChange={(e) => setVictimAlias(e.target.value)} className="border-primary/25 bg-background/70" />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Scene vector</Label>
              <Input value={sceneLocation} onChange={(e) => setSceneLocation(e.target.value)} className="border-primary/25 bg-background/70" />
            </div>
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Status</Label>
              <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
                <SelectTrigger className="border-primary/25 bg-background/70">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="cold">Cold</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Risk band</Label>
              <Select value={riskBand} onValueChange={(v) => setRiskBand(v as RiskBand)}>
                <SelectTrigger className="border-primary/25 bg-background/70">
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
            <div className="space-y-2 md:col-span-2">
              <Label className="font-mono text-[11px] uppercase text-muted-foreground">Executive summary</Label>
              <Textarea rows={5} value={summary} onChange={(e) => setSummary(e.target.value)} className="border-primary/25 bg-background/70" />
            </div>
            <div className="md:col-span-2">
              <Button type="submit" className="bg-primary font-display text-primary-foreground hover:bg-primary/90">
                Seal dossier lattice
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
