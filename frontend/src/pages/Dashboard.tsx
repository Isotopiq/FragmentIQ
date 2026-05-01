import { Badge, Button, Card, Progress } from 'flowbite-react';
import { useEffect, useState } from 'react';
import { api, getEngines, getJobs, getProjects } from '../lib/api';
import type { EngineStatus, Job, Project } from '../lib/types';

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [engines, setEngines] = useState<EngineStatus[]>([]);
  const [message, setMessage] = useState('');

  async function loadDashboard() {
    const [projectRows, jobRows, engineRows] = await Promise.all([getProjects(), getJobs(), getEngines()]);
      setProjects(projectRows);
      setJobs(jobRows);
      setEngines(engineRows);
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function resetDemo() {
    setMessage('Seeding demo project, metadata, workflow, completed job, and result artifacts...');
    const response = await api.resetDemo();
    setMessage(`Demo ready: project ${response.project_id}, completed job ${response.job_id}.`);
    await loadDashboard();
  }

  const completed = jobs.filter((job) => job.status === 'complete').length;
  const failed = jobs.filter((job) => job.status === 'failed').length;
  const availableEngines = engines.filter((engine) => engine.status === 'available').length;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ['Projects', projects.length],
          ['Total jobs', jobs.length],
          ['Completed', completed],
          ['Available engines', `${availableEngines}/${engines.length}`],
        ].map(([label, value]) => (
          <Card key={label.toString()}>
            <div className="text-sm font-medium text-gray-500">{label}</div>
            <div className="text-3xl font-bold text-gray-900 dark:text-white">{value}</div>
          </Card>
        ))}
      </section>

      <Card>
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <h2 className="text-xl font-semibold">Quick actions</h2>
            <p className="text-sm text-gray-500">Launch common LC-MS/MS workflows in mock mode or with installed engines.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" color="purple" onClick={resetDemo}>
              Reset production demo
            </Button>
            {['New MZmine Job', 'New SIRIUS Job', 'Full Pipeline', 'Upload Spectral Library', 'New Statistical Analysis'].map((action) => (
              <Button key={action} size="sm" color="blue">
                {action}
              </Button>
            ))}
          </div>
        </div>
        {message && <p className="mt-4 rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-700">{message}</p>}
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-xl font-semibold">Recent jobs</h2>
          <div className="space-y-4">
            {jobs.slice(0, 6).map((job) => (
              <div key={job.id} className="rounded-xl border border-gray-100 p-4 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{job.name}</div>
                  <Badge color={job.status === 'complete' ? 'success' : job.status === 'failed' ? 'failure' : 'info'}>{job.status}</Badge>
                </div>
                <div className="mt-2 text-xs text-gray-500">{job.stage}</div>
                <Progress progress={job.progress} size="sm" className="mt-2" />
              </div>
            ))}
            {!jobs.length && <p className="text-sm text-gray-500">No jobs yet. Create a project and submit a mock pipeline.</p>}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-xl font-semibold">System readiness</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {engines.map((engine) => (
              <div key={engine.name} className="rounded-xl border border-gray-100 p-3 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{engine.name}</span>
                  <Badge color={engine.status === 'available' ? 'success' : engine.status.startsWith('needs') ? 'warning' : 'gray'}>
                    {engine.status}
                  </Badge>
                </div>
                <div className="mt-1 truncate text-xs text-gray-500">{engine.version || engine.notes || 'No version detected'}</div>
              </div>
            ))}
          </div>
          {failed > 0 && <p className="mt-4 text-sm text-red-600">{failed} job(s) need review.</p>}
        </Card>
      </section>
    </div>
  );
}

export default Dashboard;
