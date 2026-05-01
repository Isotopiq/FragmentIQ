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

function flattenEngines(payload: Record<string, EngineStatus | Record<string, unknown>>): EngineStatus[] {
  return Object.entries(payload).map(([name, value]) => ({
    name,
    category: name === 'models' || name === 'libraries' ? 'assets' : 'engine',
    status: typeof value === 'object' && value && 'status' in value ? String(value.status) : 'unknown',
    version: typeof value === 'object' && value && 'version' in value ? String(value.version ?? '') : undefined,
    notes: typeof value === 'object' && value && 'notes' in value ? String(value.notes ?? '') : undefined,
  }))
}

const projectApi = Object.assign(() => request<Project[]>('/projects'), {
  list: () => request<Project[]>('/projects'),
  create: (payload: { name: string; description?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) }),
})

export const api = {
  projects: projectApi,
  listProjects: () => request<Project[]>('/projects'),
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
  saveMetadata: (projectId: number, payload: { name: string; columns: string[]; rows: Record<string, unknown>[]; group_columns?: string[] }) =>
    request<MetadataTable>(`/projects/${projectId}/metadata/json`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  createMetadata: (projectId: number, payload: { name: string; columns: string[]; rows: Record<string, unknown>[]; group_columns?: string[] }) =>
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
  jobLogs: (jobId: number) => request<{ content: string }>(`/jobs/${jobId}/logs`),
  features: (jobId: number) => request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/features`),
  annotations: (jobId: number) => request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/annotations`),
  statistics: (jobId: number) => request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/statistics`),
  results: (jobId: number, kind: 'features' | 'annotations' | 'statistics') =>
    request<{ rows: Record<string, unknown>[] }>(`/jobs/${jobId}/results/${kind}`).then((payload) => payload.rows),
  plots: (jobId: number) => request<Record<string, unknown>>(`/jobs/${jobId}/results/plots`),
  network: (jobId: number) => request<{ nodes: unknown[]; edges: unknown[] }>(`/jobs/${jobId}/results/network`),
  listJobs: (projectId?: number) => api.jobs(projectId),
  getFeatures: (jobId: string | number) => api.features(Number(jobId)).then((payload) => payload.rows),
  getStatistics: (jobId: string | number) => api.statistics(Number(jobId)).then((payload) => payload.rows),
  getNetwork: (jobId: string | number) => api.network(Number(jobId)),
  libraries: () => request<LibraryAsset[]>('/libraries'),
  listLibraries: () => request<LibraryAsset[]>('/libraries'),
  uploadLibrary: (payload: { name: string; file: File; source?: string }) => {
    const form = new FormData()
    form.append('name', payload.name)
    form.append('source', payload.source ?? 'user')
    form.append('file', payload.file)
    return request<LibraryAsset>('/libraries', { method: 'POST', body: form })
  },
  models: () => request<ModelAsset[]>('/models'),
  listModels: () => request<ModelAsset[]>('/models'),
  uploadModel: (payload: { name: string; engine: string; file: File; version?: string }) => {
    const form = new FormData()
    form.append('name', payload.name)
    form.append('engine', payload.engine)
    if (payload.version) form.append('version', payload.version)
    form.append('file', payload.file)
    return request<ModelAsset>('/models', { method: 'POST', body: form })
  },
  uploadFileSingle: (projectId: number, file: File) => {
    const form = new FormData()
    form.append('files', file)
    return request<DatasetFile[]>(`/projects/${projectId}/files`, { method: 'POST', body: form }).then((items) => items[0])
  },
  engines: () => request<Record<string, EngineStatus>>('/system/engines'),
  status: () => request<Record<string, unknown>>('/system/status'),
  resetDemo: () => request<{ status: string; project_id?: number; job_id?: number }>('/demo/reset', { method: 'POST' })
}

export const listProjects = () => api.projects()
export const getProjects = listProjects
export const createProject = api.createProject
export const fetchPresets = api.presets
export const createWorkflow = api.createWorkflow
export const createJob = api.createJob
export const fetchJobs = api.jobs
export const getJobs = api.jobs
export const fetchFeatures = (jobId: number) => api.features(jobId).then((payload) => payload.rows)
export const fetchAnnotations = (jobId: number) => api.annotations(jobId).then((payload) => payload.rows)
export const fetchStatistics = (jobId: number) => api.statistics(jobId).then((payload) => payload.rows)
export const getSystemStatus = api.status
export const getEngines = () => api.engines().then(flattenEngines)
export const uploadFile = api.uploadFileSingle
