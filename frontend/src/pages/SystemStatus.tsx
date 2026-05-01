import { useEffect, useState } from 'react';
import { Badge, Button, Card, Spinner } from 'flowbite-react';
import { api, getSystemStatus } from '../lib/api';

export function SystemStatus() {
  const [status, setStatus] = useState<any>(null);
  const [installing, setInstalling] = useState<Record<string, boolean>>({});
  const [installMessages, setInstallMessages] = useState<Record<string, { ok: boolean; text: string }>>({});

  const load = () => getSystemStatus().then(setStatus);
  useEffect(() => { load(); }, []);

  const engines = status?.engines || {};

  const statusColor = (value: string) => {
    if (value === 'available') return 'success';
    if (value.startsWith('needs')) return 'warning';
    if (value === 'not_installed') return 'gray';
    return 'info';
  };

  async function handleInstall(name: string) {
    setInstalling((prev) => ({ ...prev, [name]: true }));
    setInstallMessages((prev) => ({ ...prev, [name]: { ok: true, text: 'Installing...' } }));
    try {
      const result = await api.installPackage(name);
      if (result.status === 'installed') {
        setInstallMessages((prev) => ({ ...prev, [name]: { ok: true, text: result.message } }));
        await load();
      } else {
        setInstallMessages((prev) => ({ ...prev, [name]: { ok: false, text: result.message } }));
      }
    } catch (err: any) {
      setInstallMessages((prev) => ({ ...prev, [name]: { ok: false, text: err.message || 'Install failed' } }));
    } finally {
      setInstalling((prev) => ({ ...prev, [name]: false }));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Admin / System status</h1>
        <p className="text-sm text-slate-500">Manage engines, Python packages, spectral libraries, and ML models.</p>
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
            <dd className="mt-1 font-semibold text-slate-900 dark:text-white">{status?.max_upload_size_mb} MB</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-slate-400">API</dt>
            <dd className="mt-1 font-semibold text-slate-900 dark:text-white">FastAPI / SQLite</dd>
          </div>
        </dl>
      </Card>
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Engines &amp; tools</h2>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Object.entries(engines).map(([name, value]: [string, any]) => {
            const s = typeof value === 'object' ? value.status : String(value);
            const canInstall = value?.installable && s !== 'available';
            const msg = installMessages[name];
            return (
              <div key={name} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">{name}</p>
                  <Badge color={statusColor(s)}>{s.replace(/_/g, ' ')}</Badge>
                </div>
                {value?.version && <p className="mt-1 truncate text-xs text-slate-400">{value.version}</p>}
                {value?.count !== undefined && <p className="mt-1 text-xs text-slate-400">{value.count} item(s)</p>}
                {value?.notes && <p className="mt-1 text-xs text-slate-400">{value.notes}</p>}
                {canInstall && (
                  <Button
                    size="xs"
                    color="blue"
                    className="mt-2"
                    disabled={installing[name]}
                    onClick={() => handleInstall(name)}
                  >
                    {installing[name] ? <><Spinner size="xs" className="mr-2" /> Installing...</> : `Install ${name}`}
                  </Button>
                )}
                {msg && (
                  <p className={`mt-2 text-xs ${msg.ok ? 'text-green-600' : 'text-red-500'}`}>{msg.text}</p>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

export default SystemStatus;
