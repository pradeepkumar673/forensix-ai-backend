import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUiStore } from '@/stores/ui-store'
import { useAuthStore } from '@/stores/auth-store'

/** Global hotkeys — Cmd/Ctrl+K palette, G-series jumps (vim homage). */
export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const auth = useAuthStore((s) => s.authenticated)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (meta && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        useUiStore.getState().setCommandOpen(true)
        return
      }
      if (!auth || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)
        return
      if (e.altKey && e.key.toLowerCase() === 'd') {
        e.preventDefault()
        navigate('/')
      }
      if (e.altKey && e.key.toLowerCase() === 'l') {
        e.preventDefault()
        navigate('/lab')
      }
      if (e.altKey && e.key.toLowerCase() === 'w') {
        e.preventDefault()
        navigate('/workspace')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [auth, navigate])
}
