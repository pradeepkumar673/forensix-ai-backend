import { useNavigate } from 'react-router-dom'
import type { PropsWithChildren } from 'react'
import {
  Cpu,
  FileDown,
  Layers,
  Radar,
  Shield,
  Skull,
} from 'lucide-react'

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'

export function GlobalPaletteWrapper({
  open,
  setOpen,
  children,
}: PropsWithChildren<{ open: boolean; setOpen: (o: boolean) => void }>) {
  const nav = useNavigate()

  function go(path: string) {
    nav(path)
    setOpen(false)
  }

  return (
    <>
      <CommandDialog
        title="ForensiX global vector search"
        description="Jump corridors or scaffold new flows"
        open={open}
        onOpenChange={setOpen}
        className="max-w-xl border-primary/54 bg-muted/93 shadow-[0_0_72px_rgba(34,211,238,0.09)] backdrop-blur-2xl [&_[dialog]]:backdrop-blur-2xl"
      >
        <CommandInput placeholder="Search operations, dossiers… ( ⌘ K )" />
        <CommandList>
          <CommandEmpty>No matching neural route.</CommandEmpty>
          <CommandGroup heading="PRIMARY">
            <CommandItem onSelect={() => go('/')}>
              <Cpu className="opacity-71" /> Command Deck
            </CommandItem>
            <CommandItem onSelect={() => go('/cases')}>
              <Layers className="opacity-71" /> Case Matrix
            </CommandItem>
            <CommandItem onSelect={() => go('/lab')}>
              <Skull className="opacity-71" /> Digital Autopsy Twin
            </CommandItem>
            <CommandItem onSelect={() => go('/workspace')}>
              <Radar className="opacity-71" /> Intelligence Workspace
            </CommandItem>
            <CommandItem onSelect={() => go('/evidence')}>
              <Shield className="opacity-71" /> Evidence Vault
            </CommandItem>
            <CommandItem onSelect={() => go('/reports')}>
              <FileDown className="opacity-71" /> Report Forge PDF
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
      {children}
    </>
  )
}
