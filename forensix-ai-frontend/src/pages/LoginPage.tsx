import { motion } from 'framer-motion'
import { Fingerprint, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuthStore } from '@/stores/auth-store'

export default function LoginPage() {
  const navigate = useNavigate()
  const loc = useLocation()
  const login = useAuthStore((s) => s.login)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    login(name, code)
    const dest =
      (loc.state as { from?: { pathname?: string } } | undefined)?.from?.pathname ?? '/'
    navigate(dest, { replace: true })
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-[#050810] px-4 scanlines">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(0,245,255,0.14),transparent_55%),radial-gradient(circle_at_80%_70%,rgba(153,27,27,0.16),transparent_50%)]" />
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55 }}
        className="relative z-[1] w-full max-w-lg rounded-3xl border border-primary/25 bg-[#0a1428]/92 p-10 shadow-[0_0_80px_rgba(0,245,255,0.12)] backdrop-blur-2xl"
      >
        <div className="mb-8 flex items-center gap-4">
          <motion.div
            className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/35 bg-primary/10"
            animate={{ rotate: [0, 2, -2, 0] }}
            transition={{ duration: 6, repeat: Infinity }}
          >
            <Fingerprint className="h-9 w-9 text-primary" />
            <motion.span
              className="absolute inset-0 rounded-2xl border border-primary/50"
              animate={{ opacity: [0.4, 1, 0.4], scale: [1, 1.06, 1] }}
              transition={{ duration: 2.8, repeat: Infinity }}
            />
          </motion.div>
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.38em] text-primary">Secure ingress</p>
            <h1 className="font-display text-3xl font-semibold text-card-foreground">ForensiX Neural CID</h1>
          </div>
        </div>

        <form className="space-y-5" onSubmit={submit}>
          <div className="space-y-2">
            <Label htmlFor="inv" className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Investigator callsign
            </Label>
            <Input
              id="inv"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Cmdr. Aris Thorne"
              className="border-primary/25 bg-background/60 font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="code" className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Case access token (optional)
            </Label>
            <Input
              id="code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Vault bearer key"
              className="border-primary/25 bg-background/60 font-mono"
            />
          </div>
          <Button type="submit" className="w-full bg-primary font-display text-primary-foreground hover:bg-primary/90">
            <ShieldCheck className="mr-2 h-4 w-4" />
            Authenticate session
          </Button>
        </form>
        <p className="mt-6 font-mono text-[11px] text-muted-foreground">
          Biometric choreography simulated — production integrates hardware TPM / FIDO2 assertions.
        </p>
      </motion.div>
    </div>
  )
}
