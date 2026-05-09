import axios, { AxiosInstance, AxiosError } from 'axios'

// Get base URL from environment or default to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class APIClient {
  private client: AxiosInstance
  private baseURL: string

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    })

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('[API Error]', error.message, error.response?.data)
        return Promise.reject(error)
      }
    )
  }

  // Auto-discovery: Get list of available endpoints
  async getAvailableEndpoints(): Promise<string[]> {
    try {
      const response = await this.client.get('/endpoints')
      return response.data.endpoints || []
    } catch (error) {
      console.warn('[API] Could not discover endpoints:', error)
      return []
    }
  }

  // Generic GET request
  async get<T = any>(endpoint: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(endpoint, { params })
    return response.data
  }

  // Generic POST request
  async post<T = any>(endpoint: string, data?: any): Promise<T> {
    const response = await this.client.post<T>(endpoint, data)
    return response.data
  }

  // Generic PUT request
  async put<T = any>(endpoint: string, data?: any): Promise<T> {
    const response = await this.client.put<T>(endpoint, data)
    return response.data
  }

  // Generic DELETE request
  async delete<T = any>(endpoint: string): Promise<T> {
    const response = await this.client.delete<T>(endpoint)
    return response.data
  }

  // Case Management endpoints
  async getCases() {
    return this.get('/cases')
  }

  async getCase(caseId: string) {
    return this.get(`/cases/${caseId}`)
  }

  async createCase(data: any) {
    return this.post('/cases', data)
  }

  async updateCase(caseId: string, data: any) {
    return this.put(`/cases/${caseId}`, data)
  }

  async deleteCase(caseId: string) {
    return this.delete(`/cases/${caseId}`)
  }

  // Evidence endpoints
  async getEvidence(caseId?: string) {
    return this.get('/evidence', { case_id: caseId })
  }

  async uploadEvidence(formData: FormData) {
    const response = await this.client.post('/evidence/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  }

  async analyzeEvidence(evidenceId: string) {
    return this.post(`/evidence/${evidenceId}/analyze`)
  }

  // Autopsy endpoints
  async getAutopsyData(caseId: string) {
    return this.get(`/autopsy/${caseId}`)
  }

  async createAutopsyReport(caseId: string, data: any) {
    return this.post(`/autopsy/${caseId}`, data)
  }

  // Timeline endpoints
  async getTimeline(caseId: string) {
    return this.get(`/timeline/${caseId}`)
  }

  async detectContradictions(caseId: string) {
    return this.post(`/timeline/${caseId}/contradictions`)
  }

  // Knowledge Graph endpoints
  async getKnowledgeGraph(caseId: string) {
    return this.get(`/knowledge-graph/${caseId}`)
  }

  async updateKnowledgeGraph(caseId: string, data: any) {
    return this.put(`/knowledge-graph/${caseId}`, data)
  }

  // Audio Analysis endpoints
  async analyzeAudio(fileId: string) {
    return this.post(`/audio/${fileId}/analyze`)
  }

  async getAudioAnalysis(fileId: string) {
    return this.get(`/audio/${fileId}/analysis`)
  }

  // Risk Assessment endpoints
  async getRiskAssessment(caseId: string) {
    return this.get(`/risk/${caseId}`)
  }

  async calculateRisk(caseId: string, data: any) {
    return this.post(`/risk/${caseId}/calculate`, data)
  }

  // AI Chat endpoints
  async sendMessage(caseId: string, message: string) {
    return this.post(`/chat/${caseId}`, { message })
  }

  async getChatHistory(caseId: string) {
    return this.get(`/chat/${caseId}/history`)
  }

  // Report endpoints
  async generateReport(caseId: string, data: any) {
    return this.post(`/reports/${caseId}/generate`, data)
  }

  async getReport(reportId: string) {
    return this.get(`/reports/${reportId}`)
  }

  // 2D Body Map endpoints
  async getBodyMapData(caseId: string) {
    return this.get(`/body-map/${caseId}`)
  }

  async updateBodyMap(caseId: string, data: any) {
    return this.put(`/body-map/${caseId}`, data)
  }
}

export const apiClient = new APIClient()
