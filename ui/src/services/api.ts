import axios, { AxiosInstance, AxiosError } from 'axios'
import type { Agent, ScanResult, Wordlist, ApiResponse } from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

class KaiApiClient {
  private client: AxiosInstance
  
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    })
    
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message)
        return Promise.reject(error)
      }
    )
  }
  
  // Agents
  async getAgents(): Promise<Agent[]> {
    const response = await this.client.get<ApiResponse<Agent[]>>('/agents')
    return response.data.data
  }
  
  async getAgent(id: string): Promise<Agent> {
    const response = await this.client.get<ApiResponse<Agent>>(`/agents/${id}`)
    return response.data.data
  }
  
  async sendAgentCommand(agentId: string, command: string, params?: Record<string, unknown>): Promise<void> {
    await this.client.post(`/agents/${agentId}/command`, { command, params })
  }
  
  async stopAgent(agentId: string): Promise<void> {
    await this.client.post(`/agents/${agentId}/stop`)
  }
  
  // Scans
  async getScans(): Promise<ScanResult[]> {
    const response = await this.client.get<ApiResponse<ScanResult[]>>('/scans')
    return response.data.data
  }
  
  async getScan(id: string): Promise<ScanResult> {
    const response = await this.client.get<ApiResponse<ScanResult>>(`/scans/${id}`)
    return response.data.data
  }
  
  async startScan(target: string, scanType: string, options?: Record<string, unknown>): Promise<ScanResult> {
    const response = await this.client.post<ApiResponse<ScanResult>>('/scans', {
      target,
      scanType,
      options,
    })
    return response.data.data
  }
  
  async stopScan(id: string): Promise<void> {
    await this.client.post(`/scans/${id}/stop`)
  }
  
  // Wordlists
  async getWordlists(): Promise<Wordlist[]> {
    const response = await this.client.get<ApiResponse<Wordlist[]>>('/wordlists')
    return response.data.data
  }
  
  async uploadWordlist(file: File, metadata: Partial<Wordlist>): Promise<Wordlist> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('metadata', JSON.stringify(metadata))
    
    const response = await this.client.post<ApiResponse<Wordlist>>('/wordlists', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data.data
  }
  
  async deleteWordlist(id: string): Promise<void> {
    await this.client.delete(`/wordlists/${id}`)
  }
  
  // Mindmap
  async getMindmapData(scanId: string): Promise<{ nodes: unknown[]; edges: unknown[] }> {
    const response = await this.client.get<ApiResponse<{ nodes: unknown[]; edges: unknown[] }>>(`/mindmaps/${scanId}`)
    return response.data.data
  }
  
  async saveMindmap(scanId: string, nodes: unknown[], edges: unknown[]): Promise<void> {
    await this.client.post(`/mindmaps/${scanId}`, { nodes, edges })
  }
}

export const api = new KaiApiClient()
