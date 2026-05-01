import { useEffect, useMemo, useState } from "react";
import { Button, Card, Progress, Select, Timeline } from "flowbite-react";
import { api } from "../lib/api";
import type { Job } from "../lib/types";
import { StatusBadge } from "../components/StatusBadge";

export function JobMonitor() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [logs, setLogs] = useState("");

  const selected = useMemo(() => jobs.find((job) => job.id === Number(selectedId)) ?? jobs[0], [jobs, selectedId]);

  async function refresh() {
    const data = await api.jobs();
    setJobs(data);
    if (!selectedId && data[0]) setSelectedId(data[0].id);
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.jobLogs(selected.id).then((value) => setLogs(value.logs));
  }, [selected?.id, selected?.status, selected?.progress]);

  const stages = [
    "queued",
    "validating input",
    "running MZmine",
    "exporting MZmine results",
    "running SIRIUS",
    "running ML-MS/MS scoring",
    "running statistics",
    "generating report",
    "complete",
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Job monitor</h1>
        <p className="text-sm text-slate-500">Real-time mock logs and stage tracking, with cancellation/retry/download controls.</p>
      </div>
      <Card>
        <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
          <div className="space-y-4">
            <Select value={selected?.id ?? ""} onChange={(event) => setSelectedId(Number(event.target.value))}>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  #{job.id} {job.name}
                </option>
              ))}
            </Select>
            {selected ? (
              <div className="space-y-3 rounded-xl bg-slate-50 p-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-slate-900">{selected.name}</h2>
                  <StatusBadge status={selected.status} />
                </div>
                <Progress progress={selected.progress} color={selected.status === "failed" ? "red" : "blue"} />
                <p className="text-sm text-slate-600">Current stage: {selected.stage}</p>
                <div className="flex flex-wrap gap-2">
                  <Button size="xs" color="light" onClick={() => api.cancelJob(selected.id).then(refresh)}>
                    Cancel
                  </Button>
                  <Button size="xs" color="light" onClick={() => api.retryJob(selected.id).then(refresh)}>
                    Retry
                  </Button>
                  <Button size="xs" color="blue" onClick={() => window.open(`/api/jobs/${selected.id}/download`, "_blank")}>
                    Download ZIP
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">Create a job from the workflow builder to see progress.</p>
            )}
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Timeline>
              {stages.map((stage) => (
                <Timeline.Item key={stage}>
                  <Timeline.Point />
                  <Timeline.Content>
                    <Timeline.Title className={selected?.stage === stage ? "text-blue-700" : ""}>{stage}</Timeline.Title>
                    <Timeline.Body>{selected?.stage === stage ? "Active stage" : "Pipeline checkpoint"}</Timeline.Body>
                  </Timeline.Content>
                </Timeline.Item>
              ))}
            </Timeline>
            <pre className="max-h-[560px] overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-green-100 shadow-inner">
              {logs || "Logs will appear here."}
            </pre>
          </div>
        </div>
      </Card>
    </div>
  );
}
