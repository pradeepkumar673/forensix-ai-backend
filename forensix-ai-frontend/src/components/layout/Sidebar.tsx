import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  Boxes,
  BrainCircuit,
  FileScan,
  FlaskConical,
  FolderArchive,
  LayoutDashboard,
  Microscope,
  ShieldAlert,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useUiStore } from '@/stores/ui-store'

const links = [
  { to: '/', label: 'Command Deck', icon: LayoutDashboard },
  { to: '/cases', label: 'Case Registry', icon: FolderArchive },
  { to: '/vault', label: 'Evidence Vault', icon: Boxes },
  { to: '/lab', label: 'Digital Autopsy Lab', icon: Microscope },
  { to: '/workspace', label: 'Intel Workspace', icon: BrainCircuit },
  { to: '/report', label: 'Report Forge', icon: FileScan },
]

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed)
  const toggle = useUiStore((s) => s.toggleSidebar)

  return (
    <motion.aside
      layout
      className={cn(
        'relative flex h-full flex-col border-r border-primary/10 bg-sidebar/95 py-4 backdrop-blur-xl',
        collapsed ? 'w-[76px]' : 'w-[260px]',
      )}
    >
      <div className={cn('mb-6 flex items-center gap-2 px-4', collapsed && 'justify-center px-2')}>
        <div className="flex h-10 w-10 items-center justify-center rounded-xl holo-ring bg-primary/10">
          <ShieldAlert className="h-6 w-6 text-primary" />
        </div>
        {!collapsed && (
          <div className="leading-tight">
            <p className="font-display text-lg font-semibold tracking-tight text-card-foreground">
              ForensiX
            </p>
            <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
              Neural CID
            </p>
          </div>
        )}
      </div>

      <ScrollArea className="flex-1 px-2">
        <nav className="flex flex-col gap-1 pb-8">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className="block">
              {({ isActive }) => (
                <span
                  className={cn(
                    'group flex items-center gap-3 rounded-xl px-3 py-2.5 font-medium transition-colors',
                    isActive
                      ? 'bg-primary/15 text-primary shadow-[0_0_24px_rgba(0,245,255,0.12)]'
                      : 'text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                  )}
                >
                  <Icon className="h-[18px] w-[18px] shrink-0 opacity-90" />
                  {!collapsed && (
                    <span className="text-sm">{label}</span>
                  )}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </ScrollArea>

      <div className={cn('px-3', collapsed && 'flex justify-center')}>
        <Button
          type="button"
          size={collapsed ? 'icon' : 'sm'}
          variant="outline"
          className="w-full border-primary/25 bg-transparent font-mono text-[11px] uppercase tracking-wider text-muted-foreground"
          onClick={toggle}
        >
          <Activity className={cn('h-4 w-4', !collapsed && 'mr-2')} />
          {!collapsed && 'Collapse'}
        </Button>
      </div>
    </motion.aside>
  )
}
