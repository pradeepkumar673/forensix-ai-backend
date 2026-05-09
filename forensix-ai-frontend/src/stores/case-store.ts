import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type RiskBand = 'low' | 'medium' | 'high' | 'critical'

export type ForensicCase = {
  id: string
  title: string
  referenceCode: string
  status: 'active' | 'cold' | 'closed'
  riskBand: RiskBand
  caseType: string
  jurisdiction: string
  openedAt: string
  summary: string
  victimAlias?: string
  sceneLocation?: string
}

type CaseState = {
  cases: ForensicCase[]
  activeCaseId: string | null
  addCase: (c: Omit<ForensicCase, 'id' | 'openedAt'> & { id?: string }) => string
  updateCase: (id: string, patch: Partial<ForensicCase>) => void
  removeCase: (id: string) => void
  setActiveCase: (id: string | null) => void
}

function bandScore(r: RiskBand): number {
  switch (r) {
    case 'low':
      return 22
    case 'medium':
      return 48
    case 'high':
      return 72
    default:
      return 92
  }
}

export const riskNumeric = (c: ForensicCase) => bandScore(c.riskBand)

export const useCaseStore = create<CaseState>()(
  persist(
    (set, get) => ({
      cases: [],
      activeCaseId: null,

      addCase: (payload) => {
        const id = payload.id ?? crypto.randomUUID()
        const row: ForensicCase = {
          id,
          openedAt: new Date().toISOString(),
          title: payload.title,
          referenceCode: payload.referenceCode,
          status: payload.status,
          riskBand: payload.riskBand,
          caseType: payload.caseType,
          jurisdiction: payload.jurisdiction,
          summary: payload.summary,
          victimAlias: payload.victimAlias,
          sceneLocation: payload.sceneLocation,
        }
        set((s) => ({ cases: [row, ...s.cases], activeCaseId: s.activeCaseId ?? id }))
        return id
      },

      updateCase: (id, patch) =>
        set((s) => ({
          cases: s.cases.map((c) => (c.id === id ? { ...c, ...patch } : c)),
        })),

      removeCase: (id) =>
        set((s) => ({
          cases: s.cases.filter((c) => c.id !== id),
          activeCaseId: s.activeCaseId === id ? null : s.activeCaseId,
        })),

      setActiveCase: (id) => set({ activeCaseId: id }),
    }),
    { name: 'forensix-cases' },
  ),
)

export function useActiveCase() {
  const id = useCaseStore((s) => s.activeCaseId)
  return useCaseStore((s) => s.cases.find((c) => c.id === id) ?? null)
}
