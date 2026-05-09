import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type RiskBand = 'low' | 'medium' | 'high' | 'critical'

export type ForensicCase = {
  id: string
  code: string
  title: string
  synopsis: string
  jurisdiction: string
  custodyLevel: string
  riskBand: RiskBand
  tags: string[]
  createdAt: string
  updatedAt: string
}

type CaseState = {
  cases: ForensicCase[]
  activeCaseId: string | null
  setActiveCase: (id: string | null) => void
  addCase: (
    draft: Omit<ForensicCase, 'id' | 'createdAt' | 'updatedAt'> & Partial<Pick<ForensicCase, 'id'>>
  ) => ForensicCase
  updateCase: (id: string, patch: Partial<ForensicCase>) => void
  removeCase: (id: string) => void
}

function nowIso() {
  return new Date().toISOString()
}

// Lightweight UUID fallback when crypto.randomUUID unavailable in older engines
function newId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `case-${Math.random().toString(36).slice(2, 12)}`
}

export const useCaseStore = create<CaseState>()(
  persist(
    (set, get) => ({
      cases: [],
      activeCaseId: null,

      setActiveCase: (id) => set({ activeCaseId: id }),

      addCase: (draft) => {
        const c: ForensicCase = {
          id: draft.id ?? newId(),
          code: draft.code,
          title: draft.title,
          synopsis: draft.synopsis,
          jurisdiction: draft.jurisdiction,
          custodyLevel: draft.custodyLevel,
          riskBand: draft.riskBand,
          tags: draft.tags ?? [],
          createdAt: nowIso(),
          updatedAt: nowIso(),
        }
        set((s) => ({ cases: [c, ...s.cases] }))
        return c
      },

      updateCase: (id, patch) =>
        set((s) => ({
          cases: s.cases.map((c) =>
            c.id === id ? { ...c, ...patch, updatedAt: nowIso() } : c
          ),
        })),

      removeCase: (id) =>
        set((s) => ({
          cases: s.cases.filter((c) => c.id !== id),
          activeCaseId: s.activeCaseId === id ? null : s.activeCaseId,
        })),
    }),
    { name: 'forensix-cases-v1' }
  )
)
