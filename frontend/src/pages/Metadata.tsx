import { Button, Card, Label, Select, TextInput } from 'flowbite-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { MetadataTable, Project } from '../lib/types';

const emptyRows = [
  { sample_name: 'sample_a', condition: 'control', batch: 'B1', replicate: '1', subject_id: 'M01' },
  { sample_name: 'sample_b', condition: 'treated', batch: 'B1', replicate: '1', subject_id: 'M02' },
];

export function Metadata() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number>();
  const [metadata, setMetadata] = useState<MetadataTable[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>(emptyRows);
  const [columns, setColumns] = useState(['sample_name', 'condition', 'batch', 'replicate', 'subject_id']);
  const [newColumn, setNewColumn] = useState('');
  const selected = metadata[0];

  useEffect(() => {
    api.projects().then((items) => {
      setProjects(items);
      setProjectId(items[0]?.id);
    });
  }, []);

  useEffect(() => {
    if (projectId) api.metadata(projectId).then(setMetadata);
  }, [projectId]);

  const groupCounts = useMemo(() => {
    return rows.reduce<Record<string, number>>((acc, row) => {
      const key = row.condition || 'unassigned';
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  }, [rows]);

  const save = async () => {
    if (!projectId) return;
    const created = await api.createMetadata(projectId, {
      name: 'Spreadsheet metadata',
      columns,
      rows,
      group_columns: ['condition', 'batch'],
    });
    setMetadata([created, ...metadata]);
  };

  const updateCell = (index: number, column: string, value: string) => {
    setRows(rows.map((row, i) => (i === index ? { ...row, [column]: value } : row)));
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold text-indigo-600">Sample metadata</p>
        <h1 className="text-3xl font-bold text-slate-900">Metadata and grouping editor</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Define experimental factors, paired identifiers, batches, replicate fields, and filename-derived groupings. Missing and
          duplicated sample names are validated by the backend.
        </p>
      </div>

      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <Label value="Project" />
            <Select value={projectId ?? ''} onChange={(event) => setProjectId(Number(event.target.value))}>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label value="Add custom column" />
            <div className="flex gap-2">
              <TextInput value={newColumn} onChange={(event) => setNewColumn(event.target.value)} placeholder="time_point" />
              <Button
                color="light"
                onClick={() => {
                  if (newColumn && !columns.includes(newColumn)) setColumns([...columns, newColumn]);
                  setNewColumn('');
                }}
              >
                Add
              </Button>
            </div>
          </div>
          <div>
            <Label value="Filename auto-grouping preview" />
            <TextInput placeholder="regex: ^(?<condition>[^_]+)_" />
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={save}>Save metadata table</Button>
          </div>
        </div>
      </Card>

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-900">Spreadsheet editor</h2>
          <Button color="light" onClick={() => setRows([...rows, Object.fromEntries(columns.map((col) => [col, '']))])}>
            Add sample row
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                {columns.map((column) => (
                  <th key={column} className="px-3 py-2 text-left font-semibold text-slate-600">{column}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {columns.map((column) => (
                    <td key={column} className="px-3 py-2">
                      <input
                        className="w-40 rounded-lg border border-slate-200 px-3 py-2 focus:border-indigo-500 focus:ring-indigo-500"
                        value={row[column] || ''}
                        onChange={(event) => updateCell(rowIndex, column, event.target.value)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <h3 className="font-semibold text-slate-900">Sample count by condition</h3>
          <div className="mt-3 space-y-2">
            {Object.entries(groupCounts).map(([group, count]) => (
              <div key={group} className="flex items-center justify-between rounded-xl bg-indigo-50 px-3 py-2 text-sm">
                <span className="font-medium text-indigo-900">{group}</span>
                <span>{count} samples</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <h3 className="font-semibold text-slate-900">Validation warnings</h3>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
            {(selected?.warnings?.length ? selected.warnings : ['Every row should include sample_name and at least one grouping column.']).map(
              (warning) => <li key={warning}>{warning}</li>,
            )}
          </ul>
        </Card>
        <Card>
          <h3 className="font-semibold text-slate-900">Final sample order</h3>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-slate-600">
            {rows.map((row) => <li key={`${row.sample_name}-${row.replicate}`}>{row.sample_name || 'unnamed sample'}</li>)}
          </ol>
        </Card>
      </div>
    </div>
  );
}
