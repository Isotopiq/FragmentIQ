export type Project = {
  id: number;
  name: string;
  description: string;
  created_at: string;
};

export type DatasetFile = {
  id: number;
  project_id: number;
  original_name: string;
  stored_name: string;
  file_type: string;
  size_bytes: number;
  created_at: string;
};

export type MetadataTable = {
  id: number;
  project_id: number;
  name: string;
  columns: string[];
  rows: Record<string, string>[];
  group_columns: string[];
  warnings: string[];
};

export type WorkflowPreset = {
  id: string;
  name: string;
  category: string;
  description: string;
  engines: string[];
  parameters: Record<string, unknown>;
  mzbatch_template?: string;
};

export type Workflow = {
  id: number;
  project_id: number;
  name: string;
  engine: string;
  preset_key?: string;
  library_ids: number[];
  input_file_ids: number[];
  parameters: Record<string, unknown>;
  mzbatch_text?: string;
  validation_warnings?: string[];
};

export type Job = {
  id: number;
  project_id: number;
  workflow_id?: number;
  name: string;
  job_type: string;
  library_ids: number[];
  input_file_ids: number[];
  status: string;
  stage: string;
  progress: number;
  parameters: Record<string, unknown>;
  command_args: string[];
  software_versions: Record<string, unknown>;
  error_message?: string;
  created_at: string;
};

export type EngineStatus = {
  name: string;
  category: string;
  status: string;
  version?: string;
  notes?: string;
  installable?: boolean;
};

export type LibraryAsset = {
  id: number;
  name: string;
  asset_type: string;
  source: string;
  description?: string;
  library_format?: string;
  ion_mode?: string;
  supported_engines: string[];
  path: string;
  size_bytes: number;
  indexed: boolean;
  created_at: string;
};

export type ModelAsset = {
  id: number;
  name: string;
  engine: string;
  version?: string;
  status?: string;
  base_model_id?: number;
  is_default?: boolean;
  training_params?: Record<string, unknown>;
  training_job_id?: number;
  path: string;
  size_bytes: number;
  created_at: string;
};

export type SiriusCredentials = {
  username: string;
  password: string;
  url?: string;
  sirius_path?: string;
  accept_terms?: boolean;
};

export type SpectralHit = {
  rank: number;
  candidate_name: string;
  formula?: string;
  smiles?: string;
  inchikey?: string;
  precursor_mz?: number;
  score: number;
  matched_peaks: number;
  annotation_source: string;
  library_id: number;
  library_name: string;
  query_peaks: [number, number][];
  reference_peaks: [number, number][];
};

export type SpectralSearchResponse = {
  engine: string;
  query: {
    precursor_mz?: number;
    num_peaks: number;
    peaks: [number, number][];
  };
  candidates: SpectralHit[];
};

