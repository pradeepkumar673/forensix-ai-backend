import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Loader2, MessageSquare, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { assistantChat } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { useUiStore } from '@/stores/ui-store'
import { useActiveCase } from '@/stores/case-store'
import { toast } from 'sonner'

const CHIPS = [
  'Summarize chain-of-custody gaps.',
  'Prioritize forensic contradictions.',
  'Draft interview hooks from anomalies.',
]

export function ForensicOracle() {
  const open = useUiStore((s) => s.oracleOpen)
  const setOpen = useUiStore((s) => s.setOracleOpen)
  const active = useActiveCase()
  const [sessionId, setSessionId] = useState('')
  const [input, setInput] = useState('')
  const [msgs, setMsgs] = useState<{ role: 'user' | 'assistant'; text: string }[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  const chat = useMutation({
    mutationFn: (msg: string) =>
      assistantChat({
        message: msg,
        session_id: sessionId,
        case_context: active
          ? {
              case_id: active.id,
              victim: active.victimAlias ?? active.title,
              location: active.sceneLocation ?? '',
              date: active.openedAt,
              report_summary: active.summary,
              evidence_summary: '',
            }
          : undefined,
      }),
    onSuccess: (data) => {
      setSessionId(data.session_id)
      setMsgs((m) => [...m, { role: 'assistant', text: data.reply }])
    },
    onError: (e: Error) => toast.error(e.message),
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, chat.isPending])

  return (
    <>
      <motion.button
        type="button"
        aria-label="Open Forensic Oracle"
        className="fixed bottom-6 right-6 z-[500] flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/35 bg-card/90 shadow-[0_0_40px_rgba(0,245,255,0.18)] backdrop-blur-xl md:hidden"
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.96 }}
        onClick={() => setOpen(true)}
      >
        <MessageSquare className="h-6 w-6 text-primary" />
      </motion.button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="right"
          className="flex w-full flex-col border-l border-primary/20 bg-[#070f22]/95 p-0 sm:max-w-lg"
        >
          <SheetHeader className="border-b border-primary/10 px-6 py-4 text-left">
            <SheetTitle className="font-display text-lg text-primary">Forensic Oracle</SheetTitle>
            <SheetDescription className="font-mono text-[11px] uppercase tracking-[0.28em]">
              Context dossier: <span className="text-primary">{active?.referenceCode ?? 'NONE'}</span>
            </SheetDescription>
          </SheetHeader>

          <ScrollArea className="flex-1 px-4 py-4">
            <div className="space-y-4 pb-24">
              {msgs.length === 0 && (
                <p className="font-mono text-xs leading-relaxed text-muted-foreground">
                  Neural assistant tuned for SOC-grade investigations. Queries inherit active case metadata when
                  attached from the top bar.
                </p>
              )}
              {msgs.map((m, i) => (
                <div
                  key={i}
                  className={`rounded-xl border px-3 py-2 text-sm ${
                    m.role === 'user'
                      ? 'ml-6 border-primary/25 bg-primary/5 text-card-foreground'
                      : 'mr-6 border-border bg-card/70 text-muted-foreground'
                  }`}
                >
                  {m.role === 'assistant' ? (
                    <div className="space-y-2 text-xs leading-relaxed [&_a]:text-primary [&_code]:text-primary">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                    </div>
                  ) : (
                    m.text
                  )}
                </div>
              ))}
              {chat.isPending && (
                <div className="flex items-center gap-2 font-mono text-xs text-primary">
                  <Loader2 className="h-4 w-4 animate-spin" /> Inference mesh processing…
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          <div className="space-y-3 border-t border-primary/10 bg-background/80 px-4 py-4 backdrop-blur-xl">
            <div className="flex flex-wrap gap-2">
              {CHIPS.map((c) => (
                <Button
                  key={c}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 border-primary/25 font-mono text-[11px] text-muted-foreground"
                  onClick={() => setInput(c)}
                >
                  {c}
                </Button>
              ))}
            </div>
            <div className="flex gap-2">
              <Textarea
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Interrogate evidence corpus…"
                className="resize-none border-primary/20 bg-card/80 font-mono text-xs"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    const t = input.trim()
                    if (!t) return
                    setMsgs((m) => [...m, { role: 'user', text: t }])
                    setInput('')
                    chat.mutate(t)
                  }
                }}
              />
              <Button
                type="button"
                className="shrink-0 bg-primary/90 text-primary-foreground hover:bg-primary"
                disabled={!input.trim() || chat.isPending}
                onClick={() => {
                  const t = input.trim()
                  if (!t) return
                  setMsgs((m) => [...m, { role: 'user', text: t }])
                  setInput('')
                  chat.mutate(t)
                }}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
