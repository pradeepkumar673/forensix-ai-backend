/** Operator-facing diagnostics tuned for SOC / forensic environments. */

export function forensicHttpMessage(status: number, detail: string): string {
  if (status === 503 || status === 502) {
    return 'Neural inference mesh degraded — orchestration gateway unreachable. Verify Ollama / Featherless endpoints.'
  }
  if (status === 401 || status === 403) {
    return 'Credential validation failed. Chain-of-custody clearance insufficient.'
  }
  if (status === 404) {
    return 'Target artefact absent from forensic vault — verify ingest UUID or pipeline ordering.'
  }
  if (status === 413 || status === 415) {
    return 'Evidence package rejected by vault policy — MIME type or payload envelope.'
  }
  if (status >= 500) {
    return 'Core inference fault — forensic traces persisted server-side; retry after thermal stabilization.'
  }
  return detail || 'Telemetry anomaly — channel aborted.'
}

export class ForensicApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly requestId?: string

  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message)
    this.name = 'ForensicApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}
