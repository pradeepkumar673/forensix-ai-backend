/**
 * ForensiX FastAPI client — mirrors /api/v1 routers plus system probes.
 */

import axios, { type AxiosError, type AxiosInstance } from 'axios'
import { ForensicApiError, forensicHttpMessage } from '@/lib/forensic-errors'

const rawBase = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
export const API_BASE_URL = rawBase.replace(/\/$/, '')
export const V1_BASE = `${API_BASE_URL}/api/v1`

function unpack(err: unknown): never {
  const e = err as AxiosError<{
    message?: string
    detail?: string | Record<string, unknown>
    error_code?: string
    request_id?: string
  }>
  const status = e.response?.status ?? 0
  const body = e.response?.data
  let detail = e.message
  if (body && typeof body === 'object') {
    if (typeof body.message === 'string') detail = body.message
    else if (typeof body.detail === 'string') detail = body.detail
  }
  throw new ForensicApiError(
    forensicHttpMessage(status, detail),
    status,
    body && typeof body === 'object' ? body.error_code : undefined,
    body && typeof body === 'object' ? body.request_id : undefined,
  )
}

function attachLogging(instance: AxiosInstance, tag: string) {
  instance.interceptors.response.use(
    (r) => r,
    (err: AxiosError) => {
      if (err.response?.status !== 404 && err.response?.status !== undefined) {
        console.error(`[ForensiX ${tag}]`, err.response?.status, err.config?.url)
      }
      return Promise.reject(err)
    },
  )
}

export const raw: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 240_000,
  headers: { Accept: 'application/json' },
})
attachLogging(raw, 'API')

export const v1: AxiosInstance = axios.create({
  baseURL: V1_BASE,
  timeout: 240_000,
  headers: { Accept: 'application/json' },
})
attachLogging(v1, 'v1')

// ── System ───────────────────────────────────────────────────────────────────

export type ReadyPayload = {
  status: string
  ready: boolean
  timestamp: string
  checks: Record<string, unknown>
  warnings: string[]
  hints: string[]
}

export async function getReady(): Promise<ReadyPayload> {
  let lastErr: unknown
  for (const path of ['/ready', '/api/v1/ready'] as const) {
    try {
      const r = await raw.get(path, { validateStatus: (s) => s === 200 || s === 404 })
      if (r.status === 200) return r.data as ReadyPayload
    } catch (e) {
      lastErr = e
      unpack(e)
    }
  }
  try {
    await raw.get('/health').catch(unpack)
    const m = await getModelStatus()
    return {
      status: 'degraded',
      ready: true,
      timestamp: new Date().toISOString(),
      checks: {
        llm_inference_ready: false,
        advanced_vision_enabled: m.vision_enabled,
        audio_analysis_enabled: m.audio_enabled,
        llm_provider: m.llm_provider,
      },
      warnings: ['Readiness route unavailable — operating with inferred subsystem telemetry.'],
      hints: ['Deploy ForensiX API ≥ revision exposing GET /ready.'],
    }
  } catch (e) {
    unpack(lastErr ?? e)
  }
}

export async function getHealth() {
  const { data } = await raw.get('/health').catch(unpack)
  return data as Record<string, unknown>
}

export async function getModelStatus() {
  const { data } = await raw.get('/status/models').catch(unpack)
  return data as {
    status: string
    llm_provider: string
    vision_enabled: boolean
    audio_enabled: boolean
    loaded_hf_models: string[]
    model_warmup?: Record<string, string>
  }
}

export async function getApiStatus() {
  const { data } = await raw.get('/api/v1/status').catch(unpack)
  return data as { routers: Record<string, string>; timestamp: string }
}

// ── Upload ───────────────────────────────────────────────────────────────────

export async function uploadReport(file: File, onProgress?: (n: number) => void) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/upload/report', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (ev) => {
        if (ev.total && onProgress) onProgress(Math.round((ev.loaded / ev.total) * 100))
      },
    })
    .catch(unpack)
  return data
}

export async function uploadImages(files: File[], onProgress?: (n: number) => void) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/upload/images', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (ev) => {
        if (ev.total && onProgress) onProgress(Math.round((ev.loaded / ev.total) * 100))
      },
    })
    .catch(unpack)
  return data
}

export async function uploadDigitalEvidence(files: File[], onProgress?: (n: number) => void) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/upload/digital-evidence', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (ev) => {
        if (ev.total && onProgress) onProgress(Math.round((ev.loaded / ev.total) * 100))
      },
    })
    .catch(unpack)
  return data
}

export async function uploadStatements(files: File[], onProgress?: (n: number) => void) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/upload/statements', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (ev) => {
        if (ev.total && onProgress) onProgress(Math.round((ev.loaded / ev.total) * 100))
      },
    })
    .catch(unpack)
  return data
}

// ── Analysis ─────────────────────────────────────────────────────────────────

export async function analyzeReport(file: File, caseId: string) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/report', fd, { params: { case_id: caseId } })
    .catch(unpack)
  return data
}

export async function analyzeImages(files: File[], caseId: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/analyze/images', fd, { params: { case_id: caseId } })
    .catch(unpack)
  return data
}

/** Structured PMI / livor / rigor observations → LLM multi-method ToD window */
export async function analyzeTimeOfDeath(payload: Record<string, unknown>) {
  const { data } = await v1.post('/analyze/time-of-death', payload).catch(unpack)
  return data
}

export async function getCombinedAnalysis(caseId: string) {
  const r = await v1.get(`/analyze/combined`, {
    params: { case_id: caseId },
    validateStatus: (s) => s === 200 || s === 404,
  })
  if (r.status === 404) return null
  return r.data
}

export async function visionSegmentation(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/vision/segmentation', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

export async function visionPose(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/vision/pose', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

export async function visionTampering(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/vision/tampering', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

export async function audioStress(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/audio/stress', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

export async function audioTranscribe(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await v1
    .post('/analyze/audio/transcribe', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

// ── Correlation ──────────────────────────────────────────────────────────────

export async function postTimeline(files: File[], caseId: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/correlate/timeline', fd, { params: { case_id: caseId } })
    .catch(unpack)
  return data
}

export async function getTimeline(caseId: string) {
  const r = await v1.get(`/correlate/timeline/${caseId}`, {
    validateStatus: (s) => s === 200 || s === 404,
  })
  if (r.status === 404) return { events: [], contradictions: [] }
  return r.data
}

export async function buildKnowledgeGraph(files: File[], caseId: string, context?: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  const { data } = await v1
    .post('/correlate/graph', fd, {
      params: { case_id: caseId, context },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

export async function getKnowledgeGraph(caseId: string) {
  const r = await v1.get(`/correlate/graph/${caseId}`, {
    validateStatus: (s) => s === 200 || s === 404,
  })
  if (r.status === 404) return { status: 'empty', case_id: caseId, graph: null }
  return r.data
}

export async function correlateContradictions(caseId: string, statementsFile: File) {
  const fd = new FormData()
  fd.append('statements_file', statementsFile)
  const { data } = await v1
    .post('/correlate/contradictions', fd, {
      params: { case_id: caseId },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .catch(unpack)
  return data
}

// ── Risk ─────────────────────────────────────────────────────────────────────

export async function riskFull(body: Record<string, unknown>) {
  const { data } = await v1.post('/risk/full', body).catch(unpack)
  return data as {
    status: string
    error?: string
    data: {
      risk_score: Record<string, unknown>
      anomalies: Record<string, unknown>
      contradictions: Record<string, unknown>
      leads: Record<string, unknown>
    }
  }
}

// ── Assistant ────────────────────────────────────────────────────────────────

export async function assistantChat(body: {
  message: string
  session_id?: string
  case_context?: Record<string, unknown>
}) {
  const { data } = await v1.post('/assistant/chat', body).catch(unpack)
  return data as { session_id: string; reply: string; timestamp: string }
}

// ── Report PDF ───────────────────────────────────────────────────────────────

export async function generateReportPdf(payload: Record<string, unknown>) {
  const res = await v1.post('/report/generate', payload, { responseType: 'blob' }).catch(unpack)
  return res.data as Blob
}
