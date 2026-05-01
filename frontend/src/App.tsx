import { useEffect, useMemo, useState } from "react";
import Layout, { PageKey } from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import Upload from "./pages/Upload";
import Metadata from "./pages/Metadata";
import WorkflowBuilder from "./pages/WorkflowBuilder";
import JobMonitor from "./pages/JobMonitor";
import Results from "./pages/Results";
import Visualizations from "./pages/Visualizations";
import Network from "./pages/Network";
import Statistics from "./pages/Statistics";
import Libraries from "./pages/Libraries";
import SystemStatus from "./pages/SystemStatus";
import { api } from "./lib/api";
import { Project } from "./lib/types";

export default function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();

  async function refreshProjects() {
    const data = await api.listProjects();
    setProjects(data);
    if (!projectId && data[0]) setProjectId(data[0].id);
  }

  useEffect(() => {
    refreshProjects().catch(console.error);
  }, []);

  const common = useMemo(
    () => ({ projectId, refreshProjects, navigate: setPage }),
    [projectId],
  );

  return (
    <Layout
      page={page}
      setPage={setPage}
      projects={projects}
      projectId={projectId}
      setProjectId={setProjectId}
    >
      {page === "dashboard" && <Dashboard {...common} />}
      {page === "projects" && <Projects {...common} />}
      {page === "upload" && <Upload {...common} />}
      {page === "metadata" && <Metadata {...common} />}
      {page === "workflows" && <WorkflowBuilder {...common} />}
      {page === "jobs" && <JobMonitor {...common} />}
      {page === "results" && <Results {...common} />}
      {page === "visualizations" && <Visualizations {...common} />}
      {page === "statistics" && <Statistics {...common} />}
      {page === "network" && <Network {...common} />}
      {page === "libraries" && <Libraries {...common} />}
      {page === "system" && <SystemStatus {...common} />}
    </Layout>
  );
}
