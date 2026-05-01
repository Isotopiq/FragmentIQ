import { useEffect, useState } from 'react';
import { Card } from 'flowbite-react';
import { getSystemStatus } from '../lib/api';

export function SystemStatus() {
  const [status, setStatus] = useState<any>(null);
  useEffect(() => {
    getSystemStatus().then(setStatus);
  }, []);
  const engines = status?.engines || {};
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Admin / System status</h1>
        <p className="text-sm text-slate-500">Startup detection for MZmine, SIRIUS, optional ML engines, libraries, models, and runtime dependencies.</p>
      </div>
      <Card>
        <dl className="grid gap-4 md:grid-cols-4">
          <div><dt className="text-xs uppercase text-slate-400">Mock mode</dt><dd className="font-semibold">{String(status?.mock_mode)}</dd></div>
          <div><dt className="text-xs uppercase text-slate-400">Storage</dt><dd className="font-semibold">{status?.storage_root}</dd></div>
          <div><dt className="text-xs uppercase text-slate-400">Upload limit</dt><dd className="font-semibold">{status?.upload_max_mb} MB</dd></div>
          <div><dt className="text-xs uppercase text-slate-400">API</dt><dd className="font-semibold">FastAPI / SQLite</dd></div>
        </dl>
      </Card>
      {Object.entries(engines).map(([group, items]: [string, any]) => (
        <Card key={group}>
          <h2 className="mb-4 text-lg font-semibold capitalize">{group.replace('_', ' ')}</h2>
          <div className="grid gap-3 md:grid-cols-3">
            {Object.entries(items).map(([name, value]: [string, any]) => (
              <div key={name} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <p className="text-sm font-semibold">{name}</p>
                <p className="text-sm text-slate-500">{typeof value === 'object' ? value.status : String(value)}</p>
                {value?.version && <p className="mt-1 text-xs text-slate-400">{value.version}</p>}
                {value?.count !== undefined && <p className="mt-1 text-xs text-slate-400">{value.count} item(s)</p>}
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

export default SystemStatus;
