import { useEffect, useRef } from 'react'

type Actions = {
  onCommandPalette?: () => void
  onOracleToggle?: () => void
}

/** Cmd/Ctrl+K command surface, Cmd/Ctrl+Enter forensic Oracle. */
export function useGlobalShortcuts(actions: Actions) {
  const ref = useRef(actions)
  ref.current = actions

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      const k = e.key.toLowerCase()

      if (!mod) return

      if (k === 'k') {
        e.preventDefault()
        ref.current.onCommandPalette?.()
      }

      if (k === 'enter') {
        e.preventDefault()
        ref.current.onOracleToggle?.()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
}
