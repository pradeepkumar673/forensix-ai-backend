/**
 * ForensiX AI API — mirrors the FastAPI backend (app/main.py + routers).
 * Base URL: import.meta.env.VITE_API_BASE_URL (default http://127.0.0.1:8000)
 */

import axios, { type AxiosError, type AxiosInstance } from 'axios'

const rawBase = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
export const API_BASE_URL = rawBase.replace(/\/$/, '')

const V1 = `${API_BASE_URL}/api/v1`

export class ForensicApiError extends Error {
  status: number
  code?: string
  requestId?: string

  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message)
    this.name = 'ForensicApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

/** Map HTTP failures to in-universe forensic diagnostics for operators. */
export function toForensicMessage(status: number, detail: string): string {
  if (status === 503 || status === 502) {
    return 'Neural analysis mesh offline. Model orchestration unreachable — check Ollama / Featherless gateways.'
  }
  if (status === 401 || status === 403) {
    return 'Credential validation failed. Evidence chain access denied.'
  }
  if (status === 404) {
    return 'Target vector not found in forensic index. Run upstream ingest or verify case UUID.'
  }
  if (status === 413 || status === 415) {
    return 'Evidence chain integrity compromised — payload rejected by vault policy.'
  }
  if (status >= 500) {
    return 'Core inference fault. Chain-of-custody logging preserved; retry after platform health check.'
  }
  return detail || 'Anomaly in neural channel. Request could not be completed.'
}

function unpackError(err: unknown): never {
  const e = err as AxiosError<{
    message?: string
    detail?: string | { message?: string }
    error_code?: string
    request_id?: string
  }>

  const status = e.response?.status ?? 0
  const body = e.response?.data
  let detail = e.message

  if (body && typeof body === 'object') {
    if (typeof body.message === 'string') detail = body.message
    else if (typeof body.detail === 'string') detail = body.detail
    else if (body.detail && typeof body.detail === 'object' && 'message' in body.detail) {
      detail = String((body.detail as { message?: string }).message ?? detail)
    }
  }

  throw new ForensicApiError(
    toForensicMessage(status, detail),
    status,
    body?.error_code,
    body?.request_id
  )
}

function createClient(): AxiosInstance {
  const c = axios.create({
    baseURL: API_BASE_URL,
    timeout: 120_000,
    headers: { Accept: 'application/json' },
  })

  c.interceptors.response.use(
    (r) => r,
    (err: AxiosError) => {
      console.error('[ForensiX API]', err.response?.status, err.config?.url, err.response?.data)
      return Promise.reject(err)
    }
  )

  return c
}

const raw = createClient()
const v1 = axios.create({
  baseURL: V1,
  timeout: 120_000,
  headers: { Accept: 'application/json' },
})

v1.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    console.error('[ForensiX API v1]', err.response?.status, err.config?.url, err.response?.data)
    return Promise.reject(err)
  }
)

// ── System ─────────────────────────────────────────────────────────────────

export async function getHealth() {
  const { data } = await raw.get('/health').catch(unpackError)
  return data as Record<string, unknown>
}

export async function getModelStatus() {
  const { data } = await raw.get('/status/models').catch(unpackError)
  return data as {
    status: string
    llm_provider: string
    vision_enabled: boolean
    audio_enabled: boolean
    loaded_hf_models: string[]
  }
}

export async function getApiStatus() {
  const { data } = await raw.get('/api/v1/status').catch(unpackError)
  return data as {
    routers: Record<string, string>
    timestamp: string
  }
}

export async function getInfo() {
  const { data } = await raw.get('/info').catch(unpackError)
  return data as Record<string, unknown>
}

// ── Upload ───────────────────────────────────────────────────────────────────

export async function uploadReport(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/upload/report', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function uploadImages(files: File[]) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/upload/images', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function uploadDigitalEvidence(files: File[]) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/upload/digital-evidence', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function uploadStatements(files: File[]) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/upload/statements', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

// ── Analysis ─────────────────────────────────────────────────────────────────

export async function analyzeReport(file: File, caseId: string) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/report', fd, {
      params: { case_id: caseId },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function analyzeTimeOfDeath(payload: Record<string, unknown>) {
  const { data } = await v1.post('/analyze/time-of-death', payload).catch(unpackError)
  return data
}

export async function analyzeImages(files: File[], caseId: string, context?: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/analyze/images', fd, {
      params: { case_id: caseId, context },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function getCombinedAnalysis(caseId: string) {
  const { data } = await v1.get('/analyze/combined', { params: { case_id: caseId } }).catch(unpackError)
  return data
}

export async function analyzeAudioStress(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/audio/stress', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function transcribeAudio(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/audio/transcribe', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function visionSegmentation(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/vision/segmentation', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function visionPose(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/vision/pose', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function visionTampering(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/vision/tampering', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

// ── Correlation ──────────────────────────────────────────────────────────────

export async function buildTimeline(
  files: File[],
  caseId: string,
  opts?: { context?: string; statements_text?: string }
) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/correlate/timeline', fd, {
      params: {
        case_id: caseId,
        context: opts?.context,
        statements_text: opts?.statements_text,
      },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function getTimeline(caseId: string) {
  const { data } = await v1.get(`/correlate/timeline/${caseId}`).catch(unpackError)
  return data
}

export async function correlateContradictions(caseId: string, statementsFile: File) {
  const fd = new FormData()
  fd.append('statements_file', statementsFile)
  const { data } = await v1
    .post('/correlate/contradictions', fd, {
      params: { case_id: caseId },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function buildKnowledgeGraph(files: File[], caseId: string, context?: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/correlate/graph', fd, {
      params: { case_id: caseId, context },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpackError)
  return data
}

export async function getKnowledgeGraph(caseId: string) {
  const { data } = await v1.get(`/correlate/graph/${caseId}`).catch(unpackError)
  return data
}

export function getKnowledgeGraphHtmlUrl(caseId: string) {
  return `${V1}/correlate/graph/${caseId}/html`
}

export async function getGraphMetrics(caseId: string) {
  const { data } = await v1.get(`/correlate/graph/${caseId}/metrics`).catch(unpackError)
  return data
}

export async function validateTimeline(caseId: string) {
  const { data } = await v1
    .post('/correlate/validate-timeline', null, {
      params: { case_id: caseId },
    })
    .catch(unpackError)
  return data
}

// ── Risk ─────────────────────────────────────────────────────────────────────

export async function riskScore(body: Record<string, unknown>) {
  const { data } = await v1.post('/risk/score', body).catch(unpackError)
  return data
}

export async function riskAnomalies(body: Record<string, unknown>) {
  const { data } = await v1.post('/risk/anomalies', body).catch(unpackError)
  return data
}

export async function riskContradictions(body: Record<string, unknown>) {
  const { data } = await v1.post('/risk/contradictions', body).catch(unpackError)
  return data
}

export async function riskLeads(body: Record<string, unknown>) {
  const { data } = await v1.post('/risk/leads', body).catch(unpackError)
  return data
}

export async function riskFull(body: Record<string, unknown>) {
  const { data } = await v1.post('/risk/full', body).catch(unpackError)
  return data
}

// ── Assistant ────────────────────────────────────────────────────────────────

export async function assistantChat(body: Record<string, unknown>) {
  const { data } = await v1.post('/assistant/chat', body).catch(unpackError)
  return data as { session_id: string; reply: string; timestamp: string }
}

export async function assistantCreateSession(body: Record<string, unknown>) {
  const { data } = await v1.post('/assistant/session', body).catch(unpackError)
  return data
}

export async function assistantGetSession(sessionId: string) {
  const { data } = await v1.get(`/assistant/session/${sessionId}`).catch(unpackError)
  return data
}

export async function assistantDeleteSession(sessionId: string) {
  const { data } = await v1.delete(`/assistant/session/${sessionId}`).catch(unpackError)
  return data
}

// ── Reports (PDF binary) ─────────────────────────────────────────────────────

export async function generateReportPdf(reportData: Record<string, unknown>) {
  const res = await axios
    .post(`${API_BASE_URL}/api/v1/report/generate`, reportData, {
      responseType: 'blob',
      timeout: 180_000,
      headers: { 'Content-Type': 'application/json' },
    })
    .catch(unpackError)
  return res.data as Blob
}

export async function listReports() {
  const { data } = await v1.get('/report/list').catch(unpackError)
  return data as { reports: string[]; count: number }
}

export function reportDownloadUrl(filename: string) {
  return `${V1}/report/download/${encodeURIComponent(filename)}`
}
