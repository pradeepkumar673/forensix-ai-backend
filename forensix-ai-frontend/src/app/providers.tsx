import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={qc}>
      <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
      <Toaster richColors closeButton />
    </QueryClientProvider>
  )
}
