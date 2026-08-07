import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Label, Select, Textarea, TextInput } from 'flowbite-react'
import Plot from 'react-plotly.js'
import { api } from '../lib/api'
import { DataTable } from '../components/DataTable'
import type { LibraryAsset, SpectralHit, SpectralSearchResponse } from '../lib/types'

const DEFAULT_PEAKS = `50.0 10
100.0 100
150.0 40
200.0 25`

export function SpectralIdentification() {
  const [libraries, setLibraries] = useState<LibraryAsset[]>([])
  const [engine, setEngine] = useState('matchms')
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<number[]>([])
  const [precursorMz, setPrecursorMz] = useState('')
  const [peaksText, setPeaksText] = useState(DEFAULT_PEAKS)
  const [threshold, setThreshold] = useState('0.7')
  const [minMatched, setMinMatched] = useState('3')
  const [precursorTol, setPrecursorTol] = useState('0.01')
  const [mzTol, setMzTol] = useState('0.1')
  const [topK, setTopK] = useState('10')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SpectralSearchResponse | null>(null)
  const [selectedHit, setSelectedHit] = useState<SpectralHit | null>(null)

  useEffect(() => {
    api.libraries().then((items) => {
      setLibraries(items)
      if (items[0]) setSelectedLibraryIds([items[0].id])
    })
  }, [])

  function libraryFormat(library: LibraryAsset): string {
    if (library.library_format) return library.library_format
    const ext = library.path.split('.').pop()?.toUpperCase()
    return ext || 'unknown'
  }

  function parsePeaks(text: string): [number, number][] {
    const rows: [number, number][] = []
    for (const raw of text.split(/\n|\r/)) {
      const line = raw.trim()
      if (!line) continue
      const parts = line.split(/[,\s\t]+/)
      if (parts.length < 2) continue
      const mz = parseFloat(parts[0])
      const intensity = parseFloat(parts[1])
      if (!Number.isNaN(mz) && !Number.isNaN(intensity)) {
        rows.push([mz, intensity])
      }
    }
    return rows
  }

  async function handleSearch() {
    const peaks = parsePeaks(peaksText)
    if (!peaks.length) {
      setError('No valid peaks found. Use one "m/z intensity" pair per line.')
      return
    }
    if (!selectedLibraryIds.length) {
      setError('Select at least one spectral library.')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    setSelectedHit(null)
    try {
      const response = await api.spectralSearch({
        engine,
        library_ids: selectedLibraryIds,
        precursor_mz: precursorMz ? parseFloat(precursorMz) : undefined,
        peaks,
        cosine_threshold: parseFloat(threshold),
        min_matched_peaks: parseInt(minMatched, 10),
        precursor_tolerance: parseFloat(precursorTol),
        mz_tolerance: parseFloat(mzTol),
        top_k: parseInt(topK, 10),
      })
      setResult(response)
      if (response.candidates[0]) setSelectedHit(response.candidates[0])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const mirrorPlot = useMemo(() => {
    if (!selectedHit) return null
    const query = selectedHit.query_peaks.map(([mz, intensity]) => ({ mz, intensity }))
    const reference = selectedHit.reference_peaks.map(([mz, intensity]) => ({ mz, intensity }))
    return {
      data: [
        {
          type: 'bar' as any,
          x: query.map((p) => p.mz),
          y: query.map((p) => p.intensity),
          name: 'Query',
          marker: { color: '#2563eb' },
          width: 0.4,
        },
        {
          type: 'bar' as any,
          x: reference.map((p) => p.mz),
          y: reference.map((p) => -p.intensity),
          name: `Reference: ${selectedHit.candidate_name}`,
          marker: { color: '#db2777' },
          width: 0.4,
        },
      ] as any[],
      layout: {
        autosize: true,
        height: 420,
        title: { text: `Mirror plot — score ${selectedHit.score.toFixed(3)}` },
        xaxis: { title: { text: 'm/z' } },
        yaxis: { title: { text: 'Intensity (query positive, reference negative)' } },
        margin: { t: 40, l: 60, r: 20, b: 50 },
        barmode: 'group' as any,
        bargap: 0.1,
      } as any,
      config: { responsive: true, displaylogo: false },
    }
  }, [selectedHit])

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">MS2 identification</p>
        <h1 className="text-3xl font-bold text-slate-900">Spectral identification</h1>
        <p className="text-slate-600">
          Identify unknown metabolites by matching an MS/MS spectrum against uploaded MGF/MSP libraries.
        </p>
      </div>

      {error && <Alert color="failure">{error}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]">
        <Card>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Search engine</Label>
              <Select value={engine} onChange={(e) => setEngine(e.target.value)}>
                <option value="matchms">matchms (modified cosine)</option>
                <option value="ms2query">MS2Query (fallback cosine)</option>
                <option value="ms2deepscore">MS2DeepScore (fallback cosine)</option>
              </Select>
            </div>
            <div>
              <Label>Spectral libraries</Label>
              <select
                multiple
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                size={Math.min(5, Math.max(libraries.length, 2))}
                value={selectedLibraryIds.map(String)}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions).map((o) => Number(o.value))
                  setSelectedLibraryIds(values)
                }}
              >
                {libraries.map((library) => (
                  <option key={library.id} value={library.id}>
                    {library.name} ({libraryFormat(library)})
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500">Hold Ctrl/Cmd to select multiple libraries.</p>
            </div>
            <div>
              <Label>Precursor m/z</Label>
              <TextInput type="number" step="0.0001" value={precursorMz} onChange={(e) => setPrecursorMz(e.target.value)} placeholder="100.0" />
            </div>
            <div>
              <Label>Cosine threshold</Label>
              <TextInput type="number" step="0.05" min="0" max="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            </div>
            <div>
              <Label>Min matched peaks</Label>
              <TextInput type="number" value={minMatched} onChange={(e) => setMinMatched(e.target.value)} />
            </div>
            <div>
              <Label>Precursor tolerance (Da)</Label>
              <TextInput type="number" step="0.001" value={precursorTol} onChange={(e) => setPrecursorTol(e.target.value)} />
            </div>
            <div>
              <Label>m/z tolerance (Da)</Label>
              <TextInput type="number" step="0.05" value={mzTol} onChange={(e) => setMzTol(e.target.value)} />
            </div>
            <div>
              <Label>Top k hits</Label>
              <TextInput type="number" value={topK} onChange={(e) => setTopK(e.target.value)} />
            </div>
          </div>
          <div>
            <Label>Query peaks (m/z intensity per line)</Label>
            <Textarea rows={8} value={peaksText} onChange={(e) => setPeaksText(e.target.value)} />
          </div>
          <Button color="blue" onClick={handleSearch} disabled={loading}>
            {loading ? 'Searching...' : 'Identify spectrum'}
          </Button>
        </Card>

        <Card>
          <h2 className="font-semibold text-slate-900 dark:text-white">Mirror spectrum</h2>
          <p className="text-sm text-slate-500">Select a candidate row below to compare query (blue, up) vs. reference (pink, down).</p>
          {mirrorPlot ? (
            <Plot className="w-full" data={mirrorPlot.data} layout={mirrorPlot.layout} config={mirrorPlot.config} />
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-slate-500">
              Submit a search and select a candidate to view the mirror spectrum.
            </div>
          )}
        </Card>
      </div>

      {result && (
        <Card>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-slate-900">Candidate identifications</h2>
              <p className="text-sm text-slate-500">
                {result.candidates.length} hits from {result.query.num_peaks} query peaks using {result.engine}.
              </p>
            </div>
          </div>
          {result.candidates.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    {['Rank', 'Candidate', 'Formula', 'Score', 'Matched peaks', 'Library', ''].map((col) => (
                      <th key={col} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
                  {result.candidates.map((hit) => (
                    <tr
                      key={`${hit.library_id}-${hit.rank}`}
                      onClick={() => setSelectedHit(hit)}
                      className={`cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 ${selectedHit?.rank === hit.rank && selectedHit?.library_id === hit.library_id ? 'bg-indigo-50 dark:bg-indigo-950' : ''}`}
                    >
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-200">{hit.rank}</td>
                      <td className="whitespace-nowrap px-3 py-2 font-medium text-slate-900 dark:text-white">{hit.candidate_name}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-200">{hit.formula || '-'}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-200">{hit.score.toFixed(4)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-200">{hit.matched_peaks}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-slate-700 dark:text-slate-200">{hit.library_name}</td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <button
                          type="button"
                          className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedHit(hit)
                          }}
                        >
                          View mirror
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <DataTable rows={[]} columns={[]} empty="No candidates passed the threshold. Try lowering the cosine threshold or m/z tolerance." />
          )}
        </Card>
      )}
    </div>
  )
}

export default SpectralIdentification
