import Plot from 'react-plotly.js'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { Job } from '../lib/types'

export function Visualizations() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selected, setSelected] = useState('')
  const [features, setFeatures] = useState<any[]>([])
  const [stats, setStats] = useState<any[]>([])

  useEffect(() => {
    api.jobs().then((items) => {
      setJobs(items)
      const complete = items.find((job) => job.status === 'complete')
      if (complete) setSelected(String(complete.id))
    })
  }, [])

  useEffect(() => {
    if (!selected) return
    api.features(Number(selected)).then((payload) => setFeatures(payload.rows))
    api.statistics(Number(selected)).then((payload) => setStats(payload.rows))
  }, [selected])

  const heatmap = useMemo(() => stats.slice(0, 25), [stats])

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <h1 className="text-2xl font-bold text-slate-900">Visualization Studio</h1>
        <p className="mt-1 text-sm text-slate-500">Plotly-powered PCA, volcano, heatmap, RT/mz, and annotation summaries.</p>
        <select className="mt-4 rounded-lg border-slate-300" value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">Select a completed job</option>
          {jobs.map((job) => (
            <option key={job.id} value={job.id}>
              #{job.id} {job.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="card p-4">
          <h2 className="font-semibold">PCA placeholder</h2>
          <Plot
            className="w-full"
            data={[
              {
                x: features.slice(0, 40).map((row, i) => Number(row.mz || i) / 100),
                y: features.slice(0, 40).map((row, i) => Number(row.rt || i)),
                mode: 'markers',
                type: 'scatter',
                marker: { color: '#4f46e5', size: 10 },
              },
            ]}
            layout={{ height: 360, margin: { t: 20, l: 50, r: 20, b: 45 }, xaxis: { title: 'PC1' }, yaxis: { title: 'PC2' } }}
            config={{ responsive: true, displaylogo: false }}
          />
        </div>
        <div className="card p-4">
          <h2 className="font-semibold">Volcano plot</h2>
          <Plot
            className="w-full"
            data={[
              {
                x: stats.map((row) => Number(row.log2_fold_change || 0)),
                y: stats.map((row) => -Math.log10(Number(row.p_value || 1))),
                mode: 'markers',
                type: 'scatter',
                marker: { color: '#2563eb', size: 8 },
                text: stats.map((row) => row.feature_id),
              },
            ]}
            layout={{ height: 360, margin: { t: 20, l: 50, r: 20, b: 45 }, xaxis: { title: 'log2 fold-change' }, yaxis: { title: '-log10 p-value' } }}
            config={{ responsive: true, displaylogo: false }}
          />
        </div>
        <div className="card p-4">
          <h2 className="font-semibold">RT vs m/z scatter</h2>
          <Plot
            className="w-full"
            data={[
              {
                x: features.map((row) => Number(row.rt || 0)),
                y: features.map((row) => Number(row.mz || 0)),
                mode: 'markers',
                type: 'scattergl',
                marker: { color: features.map((row) => Number(row.intensity || 1)), colorscale: 'Viridis', size: 7, showscale: true },
              },
            ]}
            layout={{ height: 360, margin: { t: 20, l: 55, r: 20, b: 45 }, xaxis: { title: 'RT (min)' }, yaxis: { title: 'm/z' } }}
            config={{ responsive: true, displaylogo: false }}
          />
        </div>
        <div className="card p-4">
          <h2 className="font-semibold">Top-feature heatmap</h2>
          <Plot
            className="w-full"
            data={[
              {
                z: heatmap.map((row) => [Number(row.group_1_mean || 0), Number(row.group_2_mean || 0)]),
                y: heatmap.map((row) => row.feature_id),
                x: ['Group 1', 'Group 2'],
                type: 'heatmap',
                colorscale: 'Blues',
              },
            ]}
            layout={{ height: 360, margin: { t: 20, l: 85, r: 20, b: 45 } }}
            config={{ responsive: true, displaylogo: false }}
          />
        </div>
      </div>
    </div>
  )
}
