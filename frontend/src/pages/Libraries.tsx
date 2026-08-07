import { useEffect, useState } from 'react';
import { Alert, Button, Card, FileInput, Label, Select, TextInput } from 'flowbite-react';
import { api } from '../lib/api';
import { DataTable } from '../components/DataTable';
import type { LibraryAsset, ModelAsset } from '../lib/types';

export function Libraries() {
  const [libraries, setLibraries] = useState<LibraryAsset[]>([]);
  const [models, setModels] = useState<ModelAsset[]>([]);
  const [libraryFile, setLibraryFile] = useState<File | null>(null);
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [modelEngine, setModelEngine] = useState('ms2deepscore');
  const [message, setMessage] = useState('');

  const load = () =>
    Promise.all([api.libraries(), api.models()]).then(([libraryRows, modelRows]) => {
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
    setMessage('Library uploaded and ready for indexing');
  }

  async function indexLibrary(id: number) {
    await api.indexLibrary(id);
    await load();
    setMessage('Library indexed');
  }

  async function uploadModel() {
    if (!modelFile) return;
    await api.uploadModel({ name: modelFile.name, engine: modelEngine, file: modelFile });
    setModelFile(null);
    await load();
    setMessage('Model uploaded');
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">Library manager</p>
        <h1 className="text-3xl font-bold text-slate-900">Spectral libraries and models</h1>
        <p className="text-slate-600">Upload user-provided MGF/MSP libraries, index them for search, and upload pretrained model files.</p>
      </div>
      {message && <Alert color="info">{message}</Alert>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">Upload spectral library</h2>
          <Label>Library name</Label>
          <TextInput value={libraryFile?.name || ''} readOnly placeholder="Select a file" />
          <FileInput onChange={(event) => setLibraryFile(event.target.files?.[0] || null)} />
          <Button onClick={uploadLibrary} disabled={!libraryFile}>Upload library</Button>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">Upload pretrained model</h2>
          <Label>Model name</Label>
          <TextInput value={modelFile?.name || ''} readOnly placeholder="Select a file" />
          <Label>Engine</Label>
          <Select value={modelEngine} onChange={(event) => setModelEngine(event.target.value)}>
            <option value="ms2deepscore">MS2DeepScore</option>
            <option value="ms2query">MS2Query</option>
            <option value="sirius">SIRIUS</option>
          </Select>
          <FileInput onChange={(event) => setModelFile(event.target.files?.[0] || null)} />
          <Button onClick={uploadModel} disabled={!modelFile}>Upload model</Button>
        </Card>
      </div>
      <Card>
        <h2 className="text-lg font-semibold">Libraries</h2>
        <table className="w-full text-sm text-left">
          <thead className="text-xs uppercase text-slate-500">
            <tr><th>Name</th><th>Format</th><th>Indexed</th><th>Engines</th><th>Action</th></tr>
          </thead>
          <tbody>
            {libraries.map((library) => (
              <tr key={library.id} className="border-b">
                <td>{library.name}</td>
                <td>{library.library_format || library.asset_type}</td>
                <td>{library.indexed ? 'Yes' : 'No'}</td>
                <td>{library.supported_engines?.join(', ')}</td>
                <td>
                  <Button size="xs" onClick={() => indexLibrary(library.id)} disabled={library.indexed}>Index</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Models</h2>
        <DataTable rows={models} />
      </Card>
    </div>
  );
}

export default Libraries;
