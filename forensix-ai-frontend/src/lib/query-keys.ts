export const qk = {
  ready: ['forensix', 'ready'] as const,
  health: ['forensix', 'health'] as const,
  models: ['forensix', 'models'] as const,
  apiStatus: ['forensix', 'api-status'] as const,
  combined: (caseId: string) => ['forensix', 'analyze', 'combined', caseId] as const,
  timeline: (caseId: string) => ['forensix', 'timeline', caseId] as const,
  graph: (caseId: string) => ['forensix', 'graph', caseId] as const,
  risk: (caseId: string) => ['forensix', 'risk', caseId] as const,
}
