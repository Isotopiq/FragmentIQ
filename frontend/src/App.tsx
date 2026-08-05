import { useEffect, useState } from "react";
import Layout, { type PageKey } from "./components/Layout";
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
    const data = await api.projects.list();
    setProjects(data);
    if (!projectId && data[0]) setProjectId(data[0].id);
  }

  useEffect(() => {
    refreshProjects().catch(console.error);
  }, []);

  return (
    <Layout
      page={page}
      setPage={setPage}
      projects={projects}
      projectId={projectId}
      setProjectId={setProjectId}
    >
      {page === "dashboard" && <Dashboard />}
      {page === "projects" && <Projects />}
      {page === "upload" && <Upload projects={projects} refresh={refreshProjects} />}
      {page === "metadata" && <Metadata />}
      {page === "workflows" && <WorkflowBuilder />}
      {page === "jobs" && <JobMonitor />}
      {page === "results" && <Results />}
      {page === "visualizations" && <Visualizations />}
      {page === "statistics" && <Statistics />}
      {page === "network" && <Network />}
      {page === "libraries" && <Libraries />}
      {page === "system" && <SystemStatus />}
    </Layout>
  );
}
