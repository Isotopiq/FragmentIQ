import { useEffect, useState } from 'react';
import { Alert, Button, Card, Label, Select, Textarea, TextInput, ToggleSwitch } from 'flowbite-react';
import { createJob, createProject, createWorkflow, fetchPresets, listProjects } from '../lib/api';
import type { Project, WorkflowPreset } from '../lib/types';

export function WorkflowBuilder() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [presets, setPresets] = useState<WorkflowPreset[]>([]);
  const [projectId, setProjectId] = useState<number | ''>('');
  const [presetId, setPresetId] = useState('');
  const [advanced, setAdvanced] = useState(false);
  const [mzbatchText, setMzbatchText] = useState('<batch mzmine="preserved-mock-template"></batch>');
  const [message, setMessage] = useState('');

  const selectedPreset = presets.find((preset) => preset.id === presetId) || presets[0];

  useEffect(() => {
    Promise.all([listProjects(), fetchPresets()]).then(([projectData, presetData]) => {
      setProjects(projectData);
      setPresets(presetData);
      if (projectData[0]) setProjectId(projectData[0].id);
      if (presetData[0]) setPresetId(presetData[0].id);
    });
  }, []);

  async function ensureProject() {
    if (projectId) return Number(projectId);
    const project = await createProject({ name: 'MVP analysis project', description: 'Created from workflow builder' });
    setProjects((current) => [project, ...current]);
    setProjectId(project.id);
    return project.id;
  }

  async function submitWorkflow() {
    const targetProject = await ensureProject();
    const workflow = await createWorkflow({
      project_id: targetProject,
      name: selectedPreset?.name || 'Custom workflow',
      engine: selectedPreset?.engines?.join('+') || 'pipeline',
      preset_key: selectedPreset?.id,
      mzbatch_text: mzbatchText,
      parameters: {
        ...(selectedPreset?.parameters || {}),
        preserve_mzbatch: true,
        mock_execution: true,
      },
    });
    const job = await createJob({
      project_id: targetProject,
      workflow_id: workflow.id,
      name: `${workflow.name} run`,
      job_type: 'full_pipeline',
      parameters: workflow.parameters,
    });
    setMessage(`Submitted mock job ${job.id}. Open Job Monitor to follow logs and results.`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Workflow Builder</h1>
        <p className="text-slate-500">
          Choose editable presets, preserve mzbatch text, and submit reproducible mock jobs.
        </p>
      </div>
      {message && <Alert color="success">{message}</Alert>}
      <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
        <Card>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label value="Project" />
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
              <Label value="Workflow preset" />
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
          <ToggleSwitch checked={advanced} label="Show schema-driven advanced parameters" onChange={setAdvanced} />
          {advanced && (
            <div className="grid gap-4 md:grid-cols-3">
              {Object.entries(selectedPreset?.parameters || {}).map(([key, value]) => (
                <div key={key}>
                  <Label value={key.replaceAll('_', ' ')} />
                  <TextInput defaultValue={String(value)} />
                </div>
              ))}
            </div>
          )}
          <div>
            <Label value="Raw .mzbatch XML/text (preserved for reproducibility)" />
            <Textarea rows={8} value={mzbatchText} onChange={(event) => setMzbatchText(event.target.value)} />
          </div>
          <Button onClick={submitWorkflow}>Save workflow and submit mock job</Button>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-slate-900">Batch-mode guardrails</h2>
          <ul className="space-y-2 text-sm text-slate-600">
            <li>Only batch-compatible MZmine parameters are represented here.</li>
            <li>Original mzbatch content is stored exactly with the workflow.</li>
            <li>Production workers construct commands as argument arrays, not shell strings.</li>
            <li>SIRIUS credentials and licenses remain server-side.</li>
            <li>DREAMS, MS2DeepScore, MS2Query, and libraries are detected as optional modules.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
