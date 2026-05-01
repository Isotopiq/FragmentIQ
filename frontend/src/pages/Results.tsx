import { useEffect, useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import { fetchAnnotations, fetchFeatures, fetchJobs, fetchStatistics } from '../lib/api'
import type { Job } from '../lib/types'
import { DataTable } from '../components/DataTable'

export function Results() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobId, setJobId] = useState<number | ''>('')
  const [features, setFeatures] = useState<Record<string, unknown>[]>([])
  const [annotations, setAnnotations] = useState<Record<string, unknown>[]>([])
  const [stats, setStats] = useState<Record<string, unknown>[]>([])

  useEffect(() => {
    fetchJobs().then((items) => {
      setJobs(items)
      const complete = items.find((job) => job.status === 'complete') ?? items[0]
      if (complete) setJobId(complete.id)
    })
  }, [])

  useEffect(() => {
    if (!jobId) return
    Promise.all([fetchFeatures(jobId), fetchAnnotations(jobId), fetchStatistics(jobId)]).then(([f, a, s]) => {
      setFeatures(f)
      setAnnotations(a)
      setStats(s)
    })
  }, [jobId])

  const volcano = useMemo(() => ({
    x: stats.map((row) => Number(row.log2_fold_change ?? 0)),
    y: stats.map((row) => -Math.log10(Number(row.adjusted_p_value ?? row.p_value ?? 1))),
    text: stats.map((row) => String(row.feature_id ?? 'feature')),
  }), [stats])

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Results viewer</h1>
            <p className="text-sm text-slate-500">Combined feature, annotation, and statistics tables.</p>
          </div>
          <select className="input max-w-xs" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
            {jobs.map((job) => <option key={job.id} value={job.id}>Job #{job.id} - {job.name}</option>)}
          </select>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="card">
          <h2 className="mb-3 font-semibold">Volcano plot</h2>
          <Plot
            data={[{ type: 'scattergl', mode: 'markers', x: volcano.x, y: volcano.y, text: volcano.text, marker: { color: '#4f46e5', size: 8 } }]}
            layout={{ autosize: true, height: 380, margin: { l: 50, r: 20, t: 20, b: 50 }, xaxis: { title: { text: 'log2 fold change' } }, yaxis: { title: { text: '-log10 adjusted p-value' } } }}
            useResizeHandler
            className="h-[380px] w-full"
          />
        </div>
        <div className="card">
          <h2 className="mb-3 font-semibold">RT vs m/z feature map</h2>
          <Plot
            data={[{ type: 'scattergl', mode: 'markers', x: features.map((row) => Number(row.rt ?? 0)), y: features.map((row) => Number(row.mz ?? 0)), marker: { color: features.map((row) => Number(row.intensity ?? 0)), colorscale: 'Viridis', showscale: true } }]}
            layout={{ autosize: true, height: 380, margin: { l: 50, r: 20, t: 20, b: 50 }, xaxis: { title: { text: 'RT' } }, yaxis: { title: { text: 'm/z' } } }}
            useResizeHandler
            className="h-[380px] w-full"
          />
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 font-semibold">Unified annotation table</h2>
        <DataTable rows={annotations} columns={['feature_id', 'mz', 'rt', 'candidate_name', 'formula', 'compound_class', 'sirius_structure_score', 'ms2deepscore', 'matchms_cosine', 'confidence_level']} />
      </div>
      <div className="card">
        <h2 className="mb-4 font-semibold">Statistics table</h2>
        <DataTable rows={stats} columns={['feature_id', 'mz', 'rt', 'annotation', 'log2_fold_change', 'p_value', 'adjusted_p_value', 'effect_size']} />
      </div>
    </div>
  )
}

export default Results
