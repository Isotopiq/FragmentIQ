import { useEffect, useState } from "react";
import { Button, Card, FileInput, Label, Select } from "flowbite-react";
import { uploadFile } from "../lib/api";
import type { DatasetFile, Project } from "../lib/types";
import { DataTable } from "../components/DataTable";

type Props = { projects: Project[]; refresh: () => Promise<void> };

export function Upload({ projects, refresh }: Props) {
  const [projectId, setProjectId] = useState<number | "">("");
  const [files, setFiles] = useState<DatasetFile[]>([]);
  const [message, setMessage] = useState("Upload mzML, mzXML, MGF, MSP, CSV, TSV, mzTab, imzML, or MZmine exports.");

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projects, projectId]);

  async function submit(fileList: FileList | null) {
    if (!projectId || !fileList) return;
    const uploaded: DatasetFile[] = [];
    for (const file of Array.from(fileList)) {
      uploaded.push(await uploadFile(Number(projectId), file));
    }
    setFiles((current) => [...uploaded, ...current]);
    setMessage(`${uploaded.length} file(s) uploaded and validated.`);
    await refresh();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Upload Data</h1>
        <p className="text-sm text-slate-500">{message}</p>
      </div>
      <Card>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <Label value="Project" />
            <Select value={projectId} onChange={(event) => setProjectId(Number(event.target.value))}>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label value="Drag-and-drop or choose files" />
            <FileInput multiple onChange={(event) => submit(event.target.files)} helperText="Large-file friendly streaming uploads with server-side extension and size checks." />
          </div>
        </div>
        <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50 p-8 text-center text-sm text-indigo-700">
          Files are stored in isolated project directories and paths are sanitized to prevent traversal.
        </div>
      </Card>
      <DataTable rows={files} title="Recently uploaded files" empty="Upload files to see validation results." />
      <Button color="light" onClick={refresh}>
        Refresh dashboard
      </Button>
    </div>
  );
}
