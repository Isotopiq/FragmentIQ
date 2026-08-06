import { useEffect, useState } from 'react';
import { Alert, Button, Card, FileInput, Label, Select, TextInput } from 'flowbite-react';
import { api } from '../lib/api';
import type { ModelAsset } from '../lib/types';

export function Models() {
  const [models, setModels] = useState<ModelAsset[]>([]);
  const [message, setMessage] = useState('');
  const [training, setTraining] = useState<{ project_id: number; name: string; engine: string; parameters: string }>({ project_id: 0, name: '', engine: 'dreams', parameters: '{}' });
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [engine, setEngine] = useState('ms2deepscore');

  const load = () => api.models().then(setModels);

  useEffect(() => {
    load();
  }, []);

  async function uploadModel() {
    if (!modelFile) return;
    await api.uploadModel({ name: modelFile.name, engine, file: modelFile });
    setModelFile(null);
    await load();
    setMessage('Model uploaded');
  }

  async function handleDefault(modelId: number) {
    await api.setDefaultModel(modelId);
    await load();
    setMessage('Default model updated');
  }

  async function startTraining() {
    const payload = {
      project_id: training.project_id,
      name: training.name || `${training.engine} training`,
      engine: training.engine,
      parameters: JSON.parse(training.parameters || '{}'),
    };
    const job = await api.trainModel(payload);
    setMessage(`Training job ${job.id} submitted. Monitor it in Job Monitor.`);
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">Model manager</p>
        <h1 className="text-3xl font-bold text-slate-900">ML Models and Training</h1>
        <p className="text-slate-600">Upload pretrained checkpoints, mark defaults for each engine, and queue model-training jobs.</p>
      </div>
      {message && <Alert color="info">{message}</Alert>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">Upload pretrained model</h2>
          <Label>Model name</Label>
          <TextInput value={modelFile?.name || ''} readOnly placeholder="Select a file" />
          <Label>Engine</Label>
          <Select value={engine} onChange={(event) => setEngine(event.target.value)}>
            <option value="ms2deepscore">MS2DeepScore</option>
            <option value="ms2query">MS2Query</option>
            <option value="dreams">DreaMS</option>
            <option value="sirius">SIRIUS</option>
          </Select>
          <FileInput onChange={(event) => setModelFile(event.target.files?.[0] || null)} />
          <Button onClick={uploadModel} disabled={!modelFile}>Upload model</Button>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">Train new model</h2>
          <Label>Project ID</Label>
          <TextInput type="number" value={training.project_id || ''} onChange={(event) => setTraining({ ...training, project_id: Number(event.target.value) })} />
          <Label>Run name</Label>
          <TextInput value={training.name} onChange={(event) => setTraining({ ...training, name: event.target.value })} placeholder="e.g. DreaMS fine-tune" />
          <Label>Engine</Label>
          <Select value={training.engine} onChange={(event) => setTraining({ ...training, engine: event.target.value })}>
            <option value="dreams">DreaMS</option>
            <option value="ms2query">MS2Query</option>
          </Select>
          <Label>Training parameters (JSON)</Label>
          <TextInput value={training.parameters} onChange={(event) => setTraining({ ...training, parameters: event.target.value })} />
          <Button onClick={startTraining}>Start training job</Button>
        </Card>
      </div>
      <Card>
        <h2 className="text-lg font-semibold">Models</h2>
        <table className="w-full text-sm text-left">
          <thead className="text-xs uppercase text-slate-500">
            <tr><th>Name</th><th>Engine</th><th>Status</th><th>Default</th><th>Action</th></tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.id} className="border-b">
                <td>{model.name}</td>
                <td>{model.engine}</td>
                <td>{model.status || 'ready'}</td>
                <td>{model.is_default ? 'Yes' : 'No'}</td>
                <td>
                  <Button size="xs" onClick={() => handleDefault(model.id)} disabled={model.is_default}>Set default</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

export default Models;
