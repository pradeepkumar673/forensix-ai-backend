/** Floating forensic oracle — persists session id aligned with `/api/v1/assistant`. */

import { useMutation } from '@tanstack/react-query'
import type { PropsWithChildren } from 'react'
import { FormEvent, useEffect, useRef, useState } from 'react'
import { MessageSquare, Sparkles } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

import { ForensicApiError, assistantChat } from '@/lib/api'

import type { ForensicCase } from '@/stores/case-store'
import { useSessionStore } from '@/stores/session-store'

type Bubble = {
  role: 'user' | 'assistant'
  content: string
  ts?: string
}

const CHIPS = [
  'Find contradictions in witness statements.',
  'Estimate plausible time-of-death window rationale.',
  'Generate executive synopsis for SIO briefing.',
]

type Props = {
  open: boolean
  onOpenChange: (o: boolean) => void
  activeCase?: ForensicCase | null
}

export function OraclePanel({ open, onOpenChange, activeCase }: Props) {
  const sessionIdRef = useRef<string | null>(null)

  useEffect(() => {
    sessionIdRef.current = useSessionStore.getState().assistantSessionId ?? null
  }, [open])

  const [input, setInput] = useState('')
  const [chat, setChat] = useState<Bubble[]>([
    {
      role: 'assistant',
      content:
        'Oracle channel nominal. I ingest your active case dossier envelopes and chain-of-analysis outputs. Speak plainly, investigator.',
      ts: new Date().toISOString(),
    },
  ])

  const setAssistantGlobal = useSessionStore((s) => s.setAssistantSessionId)

  const mutation = useMutation({
    mutationFn: async (userMessage: string) => {
      const body = {
        message: userMessage,
        session_id: sessionIdRef.current ?? '',
        case_context: activeCase && {
          case_id: activeCase.id,
          victim: activeCase.title,
          location: activeCase.jurisdiction,
          date: activeCase.updatedAt.slice(0, 10),
          report_summary: activeCase.synopsis,
          evidence_summary: '',
        },
      }
      const res = await assistantChat(body)
      return res
    },
    onMutate(userMessage: string) {
      setChat((prev) => [
        ...prev,
        {
          role: 'user',
          content: userMessage,
          ts: new Date().toISOString(),
        },
      ])
      setInput('')
    },
    onSuccess(data) {
      sessionIdRef.current = data.session_id
      setAssistantGlobal(data.session_id)
      setChat((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply,
          ts: data.timestamp,
        },
      ])
    },
    onError(error) {
      const msg =
        error instanceof ForensicApiError
          ? error.message
          : 'Neural conduit faulted mid-inference.'
      setChat((prev) => [
        ...prev,
        { role: 'assistant', content: msg, ts: new Date().toISOString() },
      ])
    },
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const msg = input.trim()
    if (!msg || mutation.isPending) return
    mutation.mutate(msg)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[480px] max-w-[100vw] border-border/85 bg-sidebar/94 p-6 font-sans backdrop-blur-2xl sm:max-w-[480px]">
        <SheetHeader className="space-y-2 text-left">
          <SheetTitle className="font-display flex items-center gap-2 text-xl tracking-wide">
            <Sparkles className="size-[22px] text-primary" /> Forensic Oracle
          </SheetTitle>
          <SheetDescription className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
            Contextual LLM conduit · session {sessionIdRef.current ?? 'cold boot'}
          </SheetDescription>
        </SheetHeader>
        <Separator className="my-5 opacity-65" />

        <div className="flex flex-wrap gap-2 pb-5">
          {CHIPS.map((c) => (
            <Button
              key={c}
              type="button"
              variant="outline"
              size="sm"
              className="rounded-full border-primary/44 font-mono text-[10px] uppercase tracking-[0.16em]"
              onClick={() => setInput(c)}
            >
              {c}
            </Button>
          ))}
        </div>

        <ScrollArea className="relative h-[min(56vh,520px)] flex-1 rounded-lg border border-primary/35 bg-muted/76 p-3">
          <div className="space-y-3 pr-2">
            <AnimatePresence initial={false}>
              {chat.map((m, idx) => (
                <motion.div
                  layout
                  key={`${idx}-${m.ts}`}
                  initial={{ opacity: 0, x: m.role === 'user' ? 16 : -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`max-w-[95%] rounded-xl border px-4 py-2 text-[13px] leading-relaxed ${
                    m.role === 'user'
                      ? 'ml-auto border-primary/43 bg-background/93 text-foreground shadow-[inset_0_1px_rgba(34,211,238,0.15)]'
                      : 'mr-auto border-border/70 bg-sidebar/93 text-muted-foreground'
                  }`}
                >
                  <p className="mb-2 font-display text-[9px] uppercase tracking-[0.35em] text-primary/92">
                    {m.role === 'user' ? 'Investigator ✦ Secure channel' : 'Oracle · Lattice synthesis'}
                  </p>
                  {m.content}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          {mutation.isPending && (
            <div className="pointer-events-none absolute inset-x-10 bottom-4 flex animate-pulse items-center gap-2 rounded-lg border border-primary/45 bg-muted/93 px-3 py-2 text-[11px] text-primary backdrop-blur">
              <Sparkles className="size-[14px] animate-spin" />
              Parsing neural strata…
            </div>
          )}
        </ScrollArea>

        <SheetFooter className="gap-5 pt-5 sm:flex-col">
          <Separator className="opacity-43" />

          <form onSubmit={onSubmit} className="flex gap-3">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                mutation.isPending
                  ? 'Hold — inference still streaming downstream…'
                  : 'Speak in plain investigative language • voice capture stub'
              }
              className="h-14 flex-1 border-primary/54 bg-muted/85 font-medium"
            />
            <Button type="submit" size="lg" className="h-14 min-w-[120px]" disabled={mutation.isPending}>
              <MessageSquare className="size-[18px]" />
              Transmit
            </Button>
          </form>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

export function OracleOrbButton({
  floating,
  onToggle,
  children,
}: PropsWithChildren<{
  floating?: boolean
  onToggle?: () => void
}>) {
  return (
    <motion.div
      className={`${floating ? 'fixed bottom-[22px] right-[22px] z-[100]' : ''}`}
      animate={{ rotate: floating ? [-1.25, 1.55, -1] : [0], scale: floating ? [1, 1.05, 0.997] : 1 }}
      transition={{ repeat: floating ? Infinity : 0, duration: 24, repeatType: 'mirror' }}
    >
      <Button
        type="button"
        size="icon"
        aria-label={floating ? 'Open forensic oracle' : 'Collapse oracle launcher'}
        onClick={onToggle}
        variant="outline"
        className="group relative isolate size-[64px] overflow-hidden rounded-full border-primary bg-gradient-to-br from-accent/82 via-muted to-background opacity-93 shadow-[0_0_32px_rgba(34,211,238,0.41)] backdrop-blur-2xl hover:brightness-112"
      >
        <span className="absolute inset-0 opacity-72 mix-blend-screen">
          <span className="absolute inset-[12%] rounded-full blur-md bg-[radial-gradient(circle,#22d3ee55,transparent_65%)]" />
        </span>
        <MessageSquare className="relative text-primary-foreground" />
      </Button>
      {children && <span className="sr-only">{children}</span>}
    </motion.div>
  )
}
