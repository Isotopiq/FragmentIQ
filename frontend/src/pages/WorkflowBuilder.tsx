import { useEffect, useState } from 'react';
import { Alert, Button, Card, Label, Select, Textarea, TextInput } from 'flowbite-react';
import { createJob, createProject, createWorkflow, fetchPresets, listProjects, api } from '../lib/api';
import type { DatasetFile, LibraryAsset, Project, WorkflowPreset } from '../lib/types';

export function WorkflowBuilder() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [presets, setPresets] = useState<WorkflowPreset[]>([]);
  const [projectId, setProjectId] = useState<number | ''>('');
  const [presetId, setPresetId] = useState('');
  const [advanced, setAdvanced] = useState(false);
  const [mzbatchText, setMzbatchText] = useState('');
  const [inputFileIds, setInputFileIds] = useState<number[]>([]);
  const [libraryIds, setLibraryIds] = useState<number[]>([]);
  const [files, setFiles] = useState<DatasetFile[]>([]);
  const [libraries, setLibraries] = useState<LibraryAsset[]>([]);
  const [message, setMessage] = useState('');
  const [parameters, setParameters] = useState<Record<string, unknown>>({});

  const selectedPreset = presets.find((preset) => preset.id === presetId) || presets[0];

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const presetParam = params.get('preset');
    Promise.all([listProjects(), fetchPresets(), api.libraries()]).then(([projectData, presetData, libraryData]) => {
      setProjects(projectData);
      setPresets(presetData);
      setLibraries(libraryData);
      if (projectData[0]) setProjectId(projectData[0].id);
      if (presetParam && presetData.find((p) => p.id === presetParam)) {
        setPresetId(presetParam);
      } else if (presetData[0]) {
        setPresetId(presetData[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!projectId) {
      setFiles([]);
      return;
    }
    api.projectFiles(Number(projectId)).then((projectFiles) => {
      setFiles(projectFiles);
      const mzxml = projectFiles.find((f) => f.file_type.toLowerCase() === 'mzxml');
      setInputFileIds(mzxml ? [mzxml.id] : projectFiles.slice(0, 1).map((f) => f.id));
    }).catch(() => setFiles([]));
  }, [projectId]);

  useEffect(() => {
    if (selectedPreset?.parameters) {
      setParameters({ ...selectedPreset.parameters });
    } else {
      setParameters({});
    }
  }, [selectedPreset]);

  useEffect(() => {
    if (libraries.length && libraryIds.length === 0) {
      setLibraryIds([libraries[0].id]);
    }
  }, [libraries]);

  async function ensureProject() {
    if (projectId) return Number(projectId);
    const project = await createProject({ name: 'MVP analysis project', description: 'Created from workflow builder' });
    setProjects((current) => [project, ...current]);
    setProjectId(project.id);
    return project.id;
  }

  function selectMultiple(setter: React.Dispatch<React.SetStateAction<number[]>>) {
    return (event: React.ChangeEvent<HTMLSelectElement>) => {
      const values = Array.from(event.target.selectedOptions).map((option) => Number(option.value));
      setter(values);
    };
  }

  function updateParameter(key: string, value: unknown) {
    setParameters((current) => ({ ...current, [key]: value }));
  }

  async function submitWorkflow() {
    setMessage('Submitting...');
    try {
      const targetProject = await ensureProject();
      const needsMzbatch = selectedPreset?.engines?.includes('mzmine');
      const workflow = await createWorkflow({
        project_id: targetProject,
        name: selectedPreset?.name || 'Custom workflow',
        engine: selectedPreset?.engines?.join('+') || 'pipeline',
        preset_key: selectedPreset?.id,
        mzbatch_text: needsMzbatch ? mzbatchText : undefined,
        library_ids: libraryIds,
        input_file_ids: inputFileIds,
        parameters: {
          ...parameters,
          preserve_mzbatch: true,
          minimum_matched_peaks: typeof parameters.minimum_matched_peaks === 'number' ? parameters.minimum_matched_peaks : 3,
        },
      });
      const job = await createJob({
        project_id: targetProject,
        workflow_id: workflow.id,
        name: `${workflow.name} run`,
        job_type: selectedPreset?.engines?.length === 1 ? selectedPreset.engines[0] : 'full_pipeline',
        library_ids: libraryIds,
        input_file_ids: inputFileIds,
        parameters: workflow.parameters,
      });
      setMessage(`Submitted job ${job.id}. Open Job Monitor to follow logs and results.`);
    } catch (error: any) {
      setMessage(`Error: ${error?.message || String(error)}`);
    }
  }

  function renderParameterValue(value: unknown): string {
    if (typeof value === 'boolean') return String(value);
    if (value === null || value === undefined) return '';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function parseParameterValue(raw: string, original: unknown): unknown {
    if (typeof original === 'number') return raw === '' ? 0 : Number(raw);
    if (typeof original === 'boolean') return raw.toLowerCase() === 'true';
    if (typeof original === 'object' && original !== null) {
      try {
        return JSON.parse(raw);
      } catch {
        return raw;
      }
    }
    return raw;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Workflow Builder</h1>
        <p className="text-slate-500">
          Choose editable presets, select input files and spectral libraries, and submit reproducible jobs.
        </p>
      </div>
      {message && <Alert color="success">{message}</Alert>}
      <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
        <Card>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Project</Label>
              <Select value={projectId} onChange={(event) => setProjectId(Number(event.target.value))}>
                <option value="">Create project automatically</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Workflow preset</Label>
              <Select value={presetId} onChange={(event) => setPresetId(event.target.value)}>
                {presets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="font-semibold text-slate-900">{selectedPreset?.category}</p>
            <p className="mt-1 text-sm text-slate-600">{selectedPreset?.description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedPreset?.engines.map((engine) => (
                <span key={engine} className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">
                  {engine}
                </span>
              ))}
            </div>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={advanced}
              onChange={(event) => setAdvanced(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Show editable advanced parameters
          </label>
          {advanced && (
            <div className="grid gap-4 md:grid-cols-3">
              {Object.entries(parameters).map(([key, value]) => (
                <div key={key}>
                  <Label>{key.split('_').join(' ')}</Label>
                  <TextInput
                    value={renderParameterValue(value)}
                    onChange={(event) => updateParameter(key, parseParameterValue(event.target.value, value))}
                  />
                </div>
              ))}
            </div>
          )}
          <div>
            <Label>Input files {selectedPreset?.engines?.includes('mzmine') ? '(mzML/mzXML/MGF/MSP)' : '(MGF/MSP/mzXML/mzML)'}</Label>
            <select
              multiple
              value={inputFileIds.map(String)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              size={Math.min(5, Math.max(files.length, 2))}
              onChange={selectMultiple(setInputFileIds)}
            >
              {files.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.original_name} ({file.file_type})
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">Hold Ctrl/Cmd to select multiple files.</p>
          </div>
          <div>
            <Label>Spectral libraries (MGF/MSP)</Label>
            <select
              multiple
              value={libraryIds.map(String)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              size={Math.min(5, Math.max(libraries.length, 2))}
              onChange={selectMultiple(setLibraryIds)}
            >
              {libraries.map((library) => (
                <option key={library.id} value={library.id}>
                  {library.name} ({library.asset_type})
                </option>
              ))}
            </select>
          </div>
          {selectedPreset?.engines?.includes('mzmine') && (
            <div>
              <Label>Raw .mzbatch XML/text (preserved for reproducibility, or leave empty to auto-generate)</Label>
              <Textarea rows={8} value={mzbatchText} onChange={(event) => setMzbatchText(event.target.value)} />
            </div>
          )}
          <Button type="button" color="blue" onClick={submitWorkflow}>
            Save workflow and submit job
          </Button>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-slate-900">Batch-mode guardrails</h2>
          <ul className="space-y-2 text-sm text-slate-600">
            <li>Only batch-compatible MZmine parameters are represented here.</li>
            <li>Original mzbatch content is stored exactly with the workflow.</li>
            <li>Production workers construct commands as argument arrays, not shell strings.</li>
            <li>SIRIUS credentials and licenses remain server-side.</li>
            <li>DREAMS, MS2DeepScore, MS2Query, matchms, and CFM-ID libraries are detected as optional modules.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

export default WorkflowBuilder;
