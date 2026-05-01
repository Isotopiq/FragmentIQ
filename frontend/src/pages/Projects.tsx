import { useEffect, useState } from 'react';
import { Button, Card, Label, TextInput, Textarea } from 'flowbite-react';
import { api } from '../lib/api';
import type { Project } from '../lib/types';

export function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('Untargeted metabolomics study');
  const [description, setDescription] = useState('LC-MS/MS annotation and statistics workspace');

  const load = async () => setProjects(await api.projects.list());
  useEffect(() => {
    void load();
  }, []);

  const create = async () => {
    await api.projects.create({ name, description });
    setName('');
    setDescription('');
    await load();
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">Project manager</p>
        <h1 className="text-3xl font-bold text-slate-950">Projects and datasets</h1>
      </div>
      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <h2 className="text-xl font-semibold">Create project</h2>
          <div>
            <Label value="Name" />
            <TextInput value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <Label value="Description" />
            <Textarea rows={5} value={description} onChange={(event) => setDescription(event.target.value)} />
          </div>
          <Button onClick={create} disabled={!name.trim()}>
            Create project
          </Button>
        </Card>
        <div className="grid gap-4">
          {projects.map((project) => (
            <Card key={project.id}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">{project.name}</h3>
                  <p className="text-sm text-slate-500">{project.description || 'No description provided.'}</p>
                  <p className="mt-2 text-xs text-slate-400">Created {new Date(project.created_at).toLocaleString()}</p>
                </div>
                <Button color="light" href={`/projects/${project.id}/archive`}>
                  Download archive
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
