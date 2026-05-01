import { useEffect, useState } from 'react';
import { Button, Card, FileInput, Label, TextInput } from 'flowbite-react';
import { api } from '../lib/api';
import { DataTable } from '../components/DataTable';

export function Libraries() {
  const [libraries, setLibraries] = useState<Record<string, unknown>[]>([]);
  const [models, setModels] = useState<Record<string, unknown>[]>([]);
  const [libraryFile, setLibraryFile] = useState<File | null>(null);
  const [modelFile, setModelFile] = useState<File | null>(null);

  const load = () =>
    Promise.all([api.listLibraries(), api.listModels()]).then(([libraryRows, modelRows]) => {
      setLibraries(libraryRows);
      setModels(modelRows);
    });

  useEffect(() => {
    load();
  }, []);

  async function uploadLibrary() {
    if (!libraryFile) return;
    await api.uploadLibrary({ name: libraryFile.name, file: libraryFile });
    setLibraryFile(null);
    await load();
  }

  async function uploadModel() {
    if (!modelFile) return;
    await api.uploadModel({ name: modelFile.name, engine: 'ms2deepscore', file: modelFile });
    setModelFile(null);
    await load();
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">Library manager</p>
        <h1 className="text-3xl font-bold text-slate-900">Spectral libraries and ML models</h1>
        <p className="text-slate-600">Upload user-provided MGF/MSP libraries and optional model files. Licensed libraries are never bundled.</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">Upload spectral library</h2>
          <Label value="Library name" />
          <TextInput value={libraryFile?.name || ''} readOnly placeholder="Select a file" />
          <FileInput onChange={(event) => setLibraryFile(event.target.files?.[0] || null)} />
          <Button onClick={uploadLibrary} disabled={!libraryFile}>Upload library</Button>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">Upload pretrained model</h2>
          <Label value="Model name" />
          <TextInput value={modelFile?.name || ''} readOnly placeholder="Select a file" />
          <FileInput onChange={(event) => setModelFile(event.target.files?.[0] || null)} />
          <Button onClick={uploadModel} disabled={!modelFile}>Upload model</Button>
        </Card>
      </div>
      <Card>
        <h2 className="text-lg font-semibold">Libraries</h2>
        <DataTable rows={libraries} />
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Models</h2>
        <DataTable rows={models} />
      </Card>
    </div>
  );
}
