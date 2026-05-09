import { Outlet } from 'react-router-dom'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

/** Mounts global forensic keyboard chords once Router context exists. */
export function ShortcutsRoot() {
  useKeyboardShortcuts()
  return <Outlet />
}
