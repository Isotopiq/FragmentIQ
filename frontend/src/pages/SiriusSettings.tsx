import { useState } from 'react';
import { Alert, Button, Card, Checkbox, Label, TextInput } from 'flowbite-react';
import { testSirius } from '../lib/api';

export function SiriusSettings() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [url, setUrl] = useState('');
  const [siriusPath, setSiriusPath] = useState('sirius');
  const [acceptTerms, setAcceptTerms] = useState(true);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleTest() {
    setLoading(true);
    setResult(null);
    setError('');
    try {
      const response = await testSirius({
        username,
        password,
        url: url || undefined,
        sirius_path: siriusPath,
        accept_terms: acceptTerms,
      });
      if (response.status === 'ok') {
        setResult(response as Record<string, unknown>);
      } else {
        setError(response.message || 'SIRIUS connection failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">External engine</p>
        <h1 className="text-3xl font-bold text-slate-900">SIRIUS API credentials</h1>
        <p className="text-slate-600">Credentials are sent to the backend test endpoint and are never logged to the browser console.</p>
      </div>
      <Card className="max-w-2xl">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <Label>Username / email</Label>
            <TextInput value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>
          <div>
            <Label>Password</Label>
            <TextInput type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          <div>
            <Label>SIRIUS API URL (optional)</Label>
            <TextInput value={url} onChange={(event) => setUrl(event.target.value)} placeholder="http://localhost:8080" />
          </div>
          <div>
            <Label>SIRIUS executable path</Label>
            <TextInput value={siriusPath} onChange={(event) => setSiriusPath(event.target.value)} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox checked={acceptTerms} onChange={(event) => setAcceptTerms(event.target.checked)} />
          <Label className="mb-0">Accept SIRIUS terms and license conditions</Label>
        </div>
        <Button onClick={handleTest} disabled={!username || !password || loading}>{loading ? 'Testing...' : 'Test connection'}</Button>
        {result && <Alert color="success">Connection OK. Account: {JSON.stringify(result.account)}</Alert>}
        {error && <Alert color="failure">{error}</Alert>}
      </Card>
    </div>
  );
}

export default SiriusSettings;
