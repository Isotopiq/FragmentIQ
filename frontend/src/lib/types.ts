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
  parameters: Record<string, unknown>;
  mzbatch_text?: string;
};

export type Job = {
  id: number;
  project_id: number;
  workflow_id?: number;
  name: string;
  job_type: string;
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
};

export type LibraryAsset = {
  id: number;
  name: string;
  asset_type: string;
  source: string;
  description?: string;
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
  path: string;
  size_bytes: number;
  created_at: string;
};

