import { useEffect, useMemo, useState } from "react";
import { Card, Select } from "flowbite-react";
import CytoscapeComponent from "react-cytoscapejs";
import { api } from "../lib/api";
import { Job } from "../lib/types";

const fallback = {
  nodes: Array.from({ length: 12 }, (_, index) => ({
    data: {
      id: `F${index + 1}`,
      label: `Feature ${index + 1}`,
      compound_class: ["lipid", "alkaloid", "organic acid"][index % 3],
      score: 0.55 + (index % 5) * 0.08,
    },
  })),
  edges: Array.from({ length: 12 }, (_, index) => ({
    data: { id: `E${index}`, source: `F${index + 1}`, target: `F${((index + 3) % 12) + 1}`, score: 0.55 + (index % 4) * 0.1 },
  })),
};

export function Network() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<number | "">("");
  const [network, setNetwork] = useState<any>(fallback);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    api.jobs().then((items) => {
      setJobs(items);
      const complete = items.find((job) => job.status === "complete");
      if (complete) setJobId(complete.id);
    });
  }, []);

  useEffect(() => {
    if (!jobId) return;
    api.network(Number(jobId)).then((data) => {
      if (data?.nodes?.length) setNetwork(data);
    });
  }, [jobId]);

  const elements = useMemo(() => [...network.nodes, ...network.edges], [network]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm uppercase tracking-wide text-indigo-600">Molecular network viewer</p>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Consensus MS/MS network</h1>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <Select value={String(jobId)} onChange={(event) => setJobId(Number(event.target.value))}>
              <option value="">Demo network</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  Job #{job.id} - {job.name}
                </option>
              ))}
            </Select>
            <div className="flex gap-2 text-xs text-slate-500">
              <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-700">Color: class</span>
              <span className="rounded-full bg-indigo-100 px-3 py-1 text-indigo-700">Edge: cosine score</span>
            </div>
          </div>
          <div className="h-[620px] overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
            <CytoscapeComponent
              elements={elements}
              style={{ width: "100%", height: "100%" }}
              layout={{ name: "cose", animate: false }}
              stylesheet={[
                {
                  selector: "node",
                  style: {
                    label: "data(label)",
                    "background-color": "#4f46e5",
                    color: "#0f172a",
                    "font-size": 10,
                    "text-background-color": "#ffffff",
                    "text-background-opacity": 0.8,
                    "text-background-padding": 2,
                  },
                },
                {
                  selector: "edge",
                  style: {
                    width: "mapData(score, 0.5, 1, 1, 6)",
                    "line-color": "#93c5fd",
                    "curve-style": "bezier",
                    opacity: 0.75,
                  },
                },
              ]}
              cy={(cy: any) => {
                cy.on("tap", "node", (event: any) => setSelected(event.target.data()));
              }}
            />
          </div>
        </Card>
        <Card className="h-fit">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Node details</h2>
          {selected ? (
            <dl className="mt-4 space-y-3 text-sm">
              {Object.entries(selected).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs uppercase text-slate-400">{key}</dt>
                  <dd className="font-medium text-slate-800 dark:text-slate-100">{String(value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-4 text-sm text-slate-500">Click a node to inspect m/z, RT, class, scores, and neighboring annotations.</p>
          )}
        </Card>
      </div>
    </div>
  );
}

export default Network;
