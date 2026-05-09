import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type AuthState = {
  investigatorName: string
  accessCode: string
  authenticated: boolean
  login: (name: string, code?: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      investigatorName: '',
      accessCode: '',
      authenticated: false,
      login: (name, code = '') =>
        set({
          investigatorName: name.trim(),
          accessCode: code.trim(),
          authenticated: Boolean(name.trim()),
        }),
      logout: () =>
        set({
          investigatorName: '',
          accessCode: '',
          authenticated: false,
        }),
    }),
    { name: 'forensix-auth' },
  ),
)
