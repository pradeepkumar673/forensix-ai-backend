import { Toaster } from '@/components/ui/sonner'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { PropsWithChildren } from 'react'
import { Activity, Cpu, FileDown, Layers, Radar, Shield, Skull } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'

import { NeuralBackdrop } from '@/components/effects/NeuralBackdrop'
import { useSessionStore } from '@/stores/session-store'

type NavLinkItem = {
  to: string
  label: string
  Icon: typeof Activity
}

const NAV: NavLinkItem[] = [
  { to: '/', label: 'Command Deck', Icon: Cpu },
  { to: '/cases', label: 'Case Matrix', Icon: Layers },
  { to: '/evidence', label: 'Evidence Vault', Icon: Shield },
  { to: '/lab', label: 'Autopsy Twin', Icon: Skull },
  { to: '/workspace', label: 'Intel Forge', Icon: Radar },
  { to: '/reports', label: 'Report Forge', Icon: FileDown },
]

export function AppShell({ children }: PropsWithChildren) {
  const nav = useNavigate()
  const logout = useSessionStore((s) => s.logout)
  const operator = useSessionStore((s) => s.operatorId)

  return (
    <div className="relative min-h-dvh">
      <NeuralBackdrop className="fixed inset-0 -z-[1] opacity-40" />

      <div className="relative z-[3] mx-auto grid min-h-dvh max-w-[1920px] grid-cols-[260px_minmax(0,1fr)] gap-px bg-sidebar-border/70">
      <aside className="relative flex flex-col gap-10 border-border/70 bg-sidebar/95 px-4 py-8 backdrop-blur-xl">
        <div className="px-3">
          <p className="font-display text-xs uppercase tracking-[0.58em] text-primary/85">ForensiX AI</p>
          <p className="mt-4 font-display text-2xl font-semibold tracking-tight text-sidebar-foreground">
            NEXUS-9<span className="text-primary">Δ</span>
          </p>
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
            neural custody mesh online
          </p>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  'group flex items-center gap-3 rounded-lg px-3 py-3 text-[13px] transition-all',
                  isActive
                    ? 'glass-panel-strong text-primary shadow-[0_0_24px_rgba(34,211,238,0.22)]'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                ].join(' ')
              }
              end={to === '/'}
            >
              <Icon className="size-[18px] opacity-85" />
              <span className="font-medium">{label}</span>
            </NavLink>
          ))}

          <div className="mt-auto rounded-lg border border-dashed border-border/80 bg-muted/70 p-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">operator</p>
            <p className="truncate font-semibold">{operator || 'UNKNOWN'}</p>
            <button
              type="button"
              onClick={() => {
                logout()
                nav('/login', { replace: true })
              }}
              className="mt-3 w-full rounded-md border border-border/80 py-2 text-xs text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
            >
              Secure lockout (clears oracle session)
            </button>
          </div>
        </nav>
      </aside>

      <main className="relative bg-background grid-overlay">
        <div className="pointer-events-none absolute inset-0 -z-[1]" />
        {children}
        <span className="scanlines pointer-events-none" aria-hidden />
      </main>
      </div>
      <Toaster />
    </div>
  )
}

export function ShortcutHint({
  shortcut,
  children,
}: PropsWithChildren<{ shortcut: string }>) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="underline decoration-primary/34 decoration-dashed underline-offset-8">{children}</span>
      </TooltipTrigger>
      <TooltipContent sideOffset={12} className="font-mono text-[11px]">
        {shortcut}
      </TooltipContent>
    </Tooltip>
  )
}
