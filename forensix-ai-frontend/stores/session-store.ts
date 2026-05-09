import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type SessionState = {
  operatorId: string
  clearance: string
  biometricVerified: boolean
  assistantSessionId: string | null
  setAssistantSessionId: (id: string | null) => void
  login: (operatorId: string, clearance?: string) => void
  logout: () => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      operatorId: '',
      clearance: 'ALPHA-7',
      biometricVerified: false,
      assistantSessionId: null,

      setAssistantSessionId: (id) => set({ assistantSessionId: id }),

      login: (operatorId, clearance = 'ALPHA-7') =>
        set({ operatorId, clearance, biometricVerified: true }),

      logout: () =>
        set({
          operatorId: '',
          biometricVerified: false,
          assistantSessionId: null,
        }),
    }),
    { name: 'forensix-session-v1' }
  )
)
