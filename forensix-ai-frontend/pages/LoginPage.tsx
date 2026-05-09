import { motion } from 'framer-motion'
import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Fingerprint } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NeuralBackdrop } from '@/components/effects/NeuralBackdrop'
import { API_BASE_URL, getHealth } from '@/lib/api'
import { useSessionStore } from '@/stores/session-store'

export default function LoginPage() {
  const nav = useNavigate()
  const login = useSessionStore((s) => s.login)

  const [operator, setOperator] = useState('ANALYST Ω-9')
  const [passPhrase, setPassPhrase] = useState('')
  const [probe, setProbe] = useState<'idle' | 'ok' | 'fail'>('idle')

  async function verifyMesh() {
    try {
      await getHealth()
      setProbe('ok')
      toast.success('Mesh handshake confirmed')
    } catch {
      setProbe('fail')
      toast.warning('Core API unreachable — local ceremonial login still provisioned.')
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    login(operator, passPhrase || 'ALPHA-7')
    nav('/', { replace: true })
    toast.success('Biometric façade satisfied — vault session armed')
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center bg-background px-4 py-12">
      <NeuralBackdrop className="opacity-80" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="relative z-10 w-full max-w-[440px]"
      >
        <div className="absolute -inset-4 rounded-[2rem] border border-accent/55 bg-accent/17 blur-xl" aria-hidden />

        <Card className="relative rounded-3xl border-primary/52 bg-muted/93 shadow-[0_0_96px_rgba(34,211,238,0.14)] backdrop-blur-3xl holo-edge">
          <CardHeader className="space-y-10 px-12 pt-16 text-center">
            <motion.div
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ repeat: Infinity, duration: 6 }}
              className="mx-auto flex size-[104px] items-center justify-center rounded-[1.85rem] border border-accent/75 bg-accent/45 shadow-inner shadow-accent/51"
            >
              <Fingerprint className="size-16 text-accent-foreground opacity-93" strokeWidth={1.8} />
            </motion.div>
            <div>
              <CardTitle className="font-display text-[2.275rem] font-semibold leading-tight tracking-tight">
                ForensiX&nbsp;
                <span className="text-accent">Encrypted Entry</span>
              </CardTitle>
              <CardDescription className="mt-6 font-mono text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
                Classified custody mesh · biometric theatre
              </CardDescription>
              <p className="mt-2 font-mono text-[10px] text-primary/93">Endpoint {API_BASE_URL}</p>
            </div>
          </CardHeader>

          <CardContent className="space-y-8 px-12 pb-16">
            <form onSubmit={onSubmit} className="space-y-7">
              <div className="space-y-2 text-left">
                <Label htmlFor="op">Operator designate</Label>
                <Input
                  id="op"
                  value={operator}
                  onChange={(e) => setOperator(e.target.value)}
                  className="h-14 border-primary/62 bg-background/93"
                  autoComplete="username"
                />
              </div>
              <div className="space-y-2 text-left">
                <Label htmlFor="sec">Encryption phrase</Label>
                <Input
                  id="sec"
                  type="password"
                  value={passPhrase}
                  onChange={(e) => setPassPhrase(e.target.value)}
                  className="h-14 border-primary/62 bg-background/93"
                  autoComplete="current-password"
                />
              </div>
              <Button type="submit" className="h-[52px] w-full text-base uppercase tracking-[0.2em]">
                Affirm biometric handoff
              </Button>
              <Button type="button" variant="outline" className="h-[52px] w-full" onClick={verifyMesh}>
                Ping neural mesh —{' '}
                <span className="font-mono text-[11px] text-primary">{probe}</span>
              </Button>
            </form>

            <p className="text-center font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground/87">
              Local gate only · SSO / SAML for production hardened vaults.
            </p>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
