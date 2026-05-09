import { create } from 'zustand'

type UiState = {
  sidebarCollapsed: boolean
  commandOpen: boolean
  oracleOpen: boolean
  scanning: boolean
  toggleSidebar: () => void
  setCommandOpen: (v: boolean) => void
  setOracleOpen: (v: boolean) => void
  setScanning: (v: boolean) => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  commandOpen: false,
  oracleOpen: false,
  scanning: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setCommandOpen: (v) => set({ commandOpen: v }),
  setOracleOpen: (v) => set({ oracleOpen: v }),
  setScanning: (v) => set({ scanning: v }),
}))
