import { useEffect, useState } from 'react';
import { Badge, Card } from 'flowbite-react';
import { getSystemStatus } from '../lib/api';

export function SystemStatus() {
  const [status, setStatus] = useState<any>(null);
  useEffect(() => {
    getSystemStatus().then(setStatus);
  }, []);
  const engines = status?.engines || {};

  const statusColor = (value: string) => {
    if (value === 'available') return 'success';
    if (value.startsWith('needs')) return 'warning';
    if (value === 'not_installed') return 'gray';
    return 'info';
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Admin / System status</h1>
        <p className="text-sm text-slate-500">Startup detection for MZmine, SIRIUS, optional ML engines, libraries, models, and runtime dependencies.</p>
      </div>
      <Card>
        <dl className="grid gap-4 md:grid-cols-4">
          <div>
            <dt className="text-xs uppercase text-slate-400">Mock mode</dt>
            <dd className="mt-1 font-semibold text-slate-900 dark:text-white">{String(status?.mock_mode)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-400">Storage</dt>
            <dd className="mt-1 font-semibold text-slate-900 dark:text-white">{status?.storage_root}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-400">Upload limit</dt>
            <dd className="mt-1 font-semibold text-slate-900 dark:text-white">{status?.upload_max_mb} MB</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-400">API</dt>
            <dd className="mt-1 font-semibold text-slate-900 dark:text-white">FastAPI / SQLite</dd>
          </div>
        </dl>
      </Card>
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Engines &amp; tools</h2>
        <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-4">
          {Object.entries(engines).map(([name, value]: [string, any]) => {
            const s = typeof value === 'object' ? value.status : String(value);
            return (
              <div key={name} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">{name}</p>
                  <Badge color={statusColor(s)}>{s.replace(/_/g, ' ')}</Badge>
                </div>
                {value?.version && <p className="mt-1 truncate text-xs text-slate-400">{value.version}</p>}
                {value?.count !== undefined && <p className="mt-1 text-xs text-slate-400">{value.count} item(s)</p>}
                {value?.notes && <p className="mt-1 text-xs text-slate-400">{value.notes}</p>}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

export default SystemStatus;
