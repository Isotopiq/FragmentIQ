import Plot from "react-plotly.js";
import type { Data } from "plotly.js";

import { DataTable } from "../components/DataTable";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";

export function Statistics() {
  const jobs = useAsync(() => api.jobs(), []);
  const latest = jobs.data?.find((job) => job.status === "complete") ?? jobs.data?.[0];
  const stats = useAsync(async () => (latest ? (await api.statistics(latest.id)).rows : []), [latest?.id]);

  const rows = stats.data ?? [];
  const volcano = rows.map((row) => ({
    x: Number(row.log2_fold_change ?? 0),
    y: -Math.log10(Number(row.adjusted_p_value ?? row.p_value ?? 1)),
    text: row.feature_id,
    mode: "markers",
    type: "scatter",
    marker: { color: Number(row.adjusted_p_value ?? 1) < 0.05 ? "#dc2626" : "#2563eb", size: 9 },
  }));

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">Statistics</p>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Metadata-aware differential analysis</h1>
        <p className="mt-2 max-w-4xl text-slate-600 dark:text-slate-300">
          MVP statistics jobs generate transparent mock Welch-test outputs with preprocessing parameters stored on the job. The backend module is ready for
          real normalization, transformation, imputation, FDR, and covariate-aware methods.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-4">
        {["median normalization", "log2 transform", "half-minimum imputation", "BH-FDR"].map((label) => (
          <div key={label} className="card">
            <p className="text-sm text-slate-500">Configured step</p>
            <p className="mt-2 font-semibold capitalize text-slate-900 dark:text-white">{label}</p>
          </div>
        ))}
      </div>
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Volcano preview</h2>
        <Plot
          data={volcano as Data[]}
          layout={{
            autosize: true,
            height: 420,
            xaxis: { title: { text: "log2 fold change" } },
            yaxis: { title: { text: "-log10 adjusted p" } },
            margin: { t: 20 },
          }}
          useResizeHandler
          className="h-full w-full"
        />
      </div>
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Statistics result table</h2>
        <DataTable rows={rows} maxRows={25} />
      </div>
    </div>
  );
}

export default Statistics;
