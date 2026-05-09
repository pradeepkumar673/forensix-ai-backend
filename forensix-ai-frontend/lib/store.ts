import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

// Type definitions
export interface Case {
  id: string
  name: string
  description?: string
  status: 'open' | 'closed' | 'in-progress' | 'pending-review'
  createdAt: Date
  updatedAt: Date
  caseNumber?: string
  investigator?: string
}

export interface Evidence {
  id: string
  caseId: string
  name: string
  type: string
  size: number
  uploadedAt: Date
  status: 'pending' | 'analyzing' | 'completed' | 'error'
  hash?: string
}

export interface TimelineEvent {
  id: string
  caseId: string
  timestamp: Date
  description: string
  evidence: string[]
  type: 'event' | 'contradiction'
}

export interface BodyMapData {
  id: string
  caseId: string
  wounds: WoundMarking[]
  poses: PoseMarking[]
  spatterPatterns: SpatterPattern[]
}

export interface WoundMarking {
  id: string
  x: number
  y: number
  type: string
  depth?: number
  description?: string
}

export interface PoseMarking {
  id: string
  angle: number
  position: string
}

export interface SpatterPattern {
  id: string
  pattern: string
  intensity: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  caseId: string
}

// Store interface
interface ForensixStore {
  // Cases
  cases: Case[]
  currentCase: Case | null
  setCases: (cases: Case[]) => void
  setCurrentCase: (caseItem: Case | null) => void
  addCase: (caseItem: Case) => void
  updateCase: (caseItem: Case) => void
  removeCase: (caseId: string) => void

  // Evidence
  evidence: Evidence[]
  setEvidence: (evidence: Evidence[]) => void
  addEvidence: (evidence: Evidence) => void
  updateEvidence: (evidence: Evidence) => void
  removeEvidence: (evidenceId: string) => void

  // Timeline
  timelineEvents: TimelineEvent[]
  setTimelineEvents: (events: TimelineEvent[]) => void
  addTimelineEvent: (event: TimelineEvent) => void
  updateTimelineEvent: (event: TimelineEvent) => void
  removeTimelineEvent: (eventId: string) => void
  contradictions: string[]
  setContradictions: (contradictions: string[]) => void

  // Body Map
  bodyMapData: BodyMapData | null
  setBodyMapData: (data: BodyMapData | null) => void
  addWound: (wound: WoundMarking) => void
  updateWound: (wound: WoundMarking) => void
  removeWound: (woundId: string) => void

  // Chat
  chatMessages: ChatMessage[]
  setChatMessages: (messages: ChatMessage[]) => void
  addChatMessage: (message: ChatMessage) => void

  // UI State
  sidebarCollapsed: boolean
  setSidebarCollapsed: (collapsed: boolean) => void
  loading: boolean
  setLoading: (loading: boolean) => void
  error: string | null
  setError: (error: string | null) => void
}

// Create the store
export const useForensixStore = create<ForensixStore>()(
  subscribeWithSelector((set) => ({
    // Cases
    cases: [],
    currentCase: null,
    setCases: (cases) => set({ cases }),
    setCurrentCase: (currentCase) => set({ currentCase }),
    addCase: (caseItem) =>
      set((state) => ({
        cases: [...state.cases, caseItem],
      })),
    updateCase: (caseItem) =>
      set((state) => ({
        cases: state.cases.map((c) => (c.id === caseItem.id ? caseItem : c)),
      })),
    removeCase: (caseId) =>
      set((state) => ({
        cases: state.cases.filter((c) => c.id !== caseId),
      })),

    // Evidence
    evidence: [],
    setEvidence: (evidence) => set({ evidence }),
    addEvidence: (ev) =>
      set((state) => ({
        evidence: [...state.evidence, ev],
      })),
    updateEvidence: (ev) =>
      set((state) => ({
        evidence: state.evidence.map((e) => (e.id === ev.id ? ev : e)),
      })),
    removeEvidence: (evidenceId) =>
      set((state) => ({
        evidence: state.evidence.filter((e) => e.id !== evidenceId),
      })),

    // Timeline
    timelineEvents: [],
    setTimelineEvents: (events) => set({ timelineEvents: events }),
    addTimelineEvent: (event) =>
      set((state) => ({
        timelineEvents: [...state.timelineEvents, event],
      })),
    updateTimelineEvent: (event) =>
      set((state) => ({
        timelineEvents: state.timelineEvents.map((e) => (e.id === event.id ? event : e)),
      })),
    removeTimelineEvent: (eventId) =>
      set((state) => ({
        timelineEvents: state.timelineEvents.filter((e) => e.id !== eventId),
      })),
    contradictions: [],
    setContradictions: (contradictions) => set({ contradictions }),

    // Body Map
    bodyMapData: null,
    setBodyMapData: (bodyMapData) => set({ bodyMapData }),
    addWound: (wound) =>
      set((state) => {
        if (!state.bodyMapData) return state
        return {
          bodyMapData: {
            ...state.bodyMapData,
            wounds: [...state.bodyMapData.wounds, wound],
          },
        }
      }),
    updateWound: (wound) =>
      set((state) => {
        if (!state.bodyMapData) return state
        return {
          bodyMapData: {
            ...state.bodyMapData,
            wounds: state.bodyMapData.wounds.map((w) => (w.id === wound.id ? wound : w)),
          },
        }
      }),
    removeWound: (woundId) =>
      set((state) => {
        if (!state.bodyMapData) return state
        return {
          bodyMapData: {
            ...state.bodyMapData,
            wounds: state.bodyMapData.wounds.filter((w) => w.id !== woundId),
          },
        }
      }),

    // Chat
    chatMessages: [],
    setChatMessages: (messages) => set({ chatMessages: messages }),
    addChatMessage: (message) =>
      set((state) => ({
        chatMessages: [...state.chatMessages, message],
      })),

    // UI State
    sidebarCollapsed: false,
    setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
    loading: false,
    setLoading: (loading) => set({ loading }),
    error: null,
    setError: (error) => set({ error }),
  }))
)
