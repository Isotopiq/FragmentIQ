import type {
  DatasetFile,
  EngineStatus,
  Job,
  LibraryAsset,
  MetadataTable,
  ModelAsset,
  Project,
  Workflow,
  WorkflowPreset
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText)
  }
  return response.json()
}

export const api = {
  projects: () => request<Project[]>('/projects'),
  createProject: (payload: { name: string; description?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  projectFiles: (projectId: number) => request<DatasetFile[]>(`/projects/${projectId}/files`),
  uploadFile: (projectId: number, files: FileList | File[]) => {
    const form = new FormData()
    Array.from(files).forEach((file) => form.append('files', file))
    return request<DatasetFile[]>(`/projects/${projectId}/files`, { method: 'POST', body: form })
  },
  metadata: (projectId: number) => request<MetadataTable[]>(`/projects/${projectId}/metadata`),
  uploadMetadata: (projectId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<MetadataTable>(`/projects/${projectId}/metadata`, { method: 'POST', body: form })
  },
  saveMetadata: (projectId: number, payload: { name: string; columns: string[]; rows: Record<string, unknown>[] }) =>
    request<MetadataTable>(`/projects/${projectId}/metadata/json`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  validateMetadata: (metadataId: number) => request<{ valid: boolean; warnings: string[] }>(`/metadata/${metadataId}/validate`, { method: 'POST' }),
  presets: () => request<WorkflowPreset[]>('/workflows/presets'),
  createWorkflow: (payload: Partial<Workflow>) => request<Workflow>('/workflows', { method: 'POST', body: JSON.stringify(payload) }),
  validateWorkflow: (workflowId: number) => request<{ valid: boolean; warnings: string[] }>(`/workflows/${workflowId}/validate`, { method: 'POST' }),
  jobs: (projectId?: number) => request<Job[]>(`/jobs${projectId ? `?project_id=${projectId}` : ''}`),
  createJob: (payload: { project_id: number; workflow_id?: number; name: string; job_type: string; parameters?: Record<string, unknown> }) =>
    request<Job>('/jobs', { method: 'POST', body: JSON.stringify(payload) }),
  cancelJob: (jobId: number) => request<Job>(`/jobs/${jobId}/cancel`, { method: 'POST' }),
  retryJob: (jobId: number) => request<Job>(`/jobs/${jobId}/retry`, { method: 'POST' }),
  logs: (jobId: number) => request<{ content: string }>(`/jobs/${jobId}/logs`),
  features: (jobId: number) => request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/features`),
  annotations: (jobId: number) => request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/annotations`),
  statistics: (jobId: number) => request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/statistics`),
  plots: (jobId: number) => request<Record<string, unknown>>(`/jobs/${jobId}/results/plots`),
  network: (jobId: number) => request<{ nodes: unknown[]; edges: unknown[] }>(`/jobs/${jobId}/results/network`),
  libraries: () => request<LibraryAsset[]>('/libraries'),
  models: () => request<ModelAsset[]>('/models'),
  engines: () => request<Record<string, EngineStatus>>('/system/engines'),
  status: () => request<Record<string, unknown>>('/system/status')
}
