import { useNavigate } from 'react-router-dom'
import { BrainCircuit, LayoutDashboard, Microscope, Search } from 'lucide-react'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { useUiStore } from '@/stores/ui-store'

const NAV = [
  { label: 'Command Deck', path: '/', icon: LayoutDashboard },
  { label: 'Digital Autopsy Lab', path: '/lab', icon: Microscope },
  { label: 'Intel Workspace', path: '/workspace', icon: BrainCircuit },
]

export function NeuralCommandPalette() {
  const open = useUiStore((s) => s.commandOpen)
  const setOpen = useUiStore((s) => s.setCommandOpen)
  const navigate = useNavigate()

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search routes, artefacts, hypotheses…"
        className="font-mono text-sm"
      />
      <CommandList className="max-h-[340px]">
        <CommandEmpty className="py-6 text-center font-mono text-xs text-muted-foreground">
          No neural hits — refine lexeme.
        </CommandEmpty>
        <CommandGroup heading="Jump">
          {NAV.map(({ label, path, icon: Icon }) => (
            <CommandItem
              key={path}
              className="gap-2 font-mono text-xs"
              onSelect={() => {
                navigate(path)
                setOpen(false)
              }}
            >
              <Icon className="h-4 w-4 text-primary" />
              {label}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Shortcuts">
          <CommandItem disabled className="gap-2 font-mono text-[11px] text-muted-foreground">
            <Search className="h-4 w-4" />
            ⌘K — Invoke neural palette
          </CommandItem>
          <CommandItem disabled className="gap-2 font-mono text-[11px] text-muted-foreground">
            ⌥D — Dashboard (when authenticated)
          </CommandItem>
          <CommandItem disabled className="gap-2 font-mono text-[11px] text-muted-foreground">
            ⌥L — Autopsy lab
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
