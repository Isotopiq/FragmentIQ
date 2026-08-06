# FragmentIQ

FragmentIQ is a self-hostable LC-MS/MS processing and annotation platform MVP. It provides a browser GUI for projects, raw data uploads, sample metadata/grouping, editable workflow presets, mock MZmine/SIRIUS/ML-MS/MS jobs, interactive results, Plotly visualizations, molecular-network preview, engine status, and reproducible exports.

This repository currently delivers the requested **initial MVP plus real-runner scaffolding**. It runs end-to-end in mock mode without MZmine, SIRIUS, DREAMS, MS2DeepScore, or MS2Query installed. With `MOCK_EXECUTION=false`, the backend validates project-owned inputs, preserves the exact `.mzbatch` workflow, constructs safe subprocess argument arrays (`shell=False`), captures stdout/stderr, writes a command manifest, and parses supported MZmine/SIRIUS output tables when the external tools create them.

## Stack

- Frontend: React + Vite + TypeScript, Tailwind CSS, Flowbite React, Plotly, Cytoscape, TanStack Table
- Backend: FastAPI, SQLModel, SQLite, local filesystem storage
- Deployment: Docker Compose with backend, frontend, Redis placeholder, and worker images
- Mock mode: enabled by default for local development and CI

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (Node 22+):

```bash
cd frontend
npm install
npm run dev
```

## MVP workflow

For a production-demo walkthrough, click **Reset seeded demo** on the Dashboard after startup. This creates a demo
project, sample metadata table, uploaded mock feature table, preserved workflow, completed mock pipeline job, parsed
feature/annotation/statistics tables, Plotly-ready result payloads, molecular network data, report HTML, and a ZIP export.

1. Create a project from the Dashboard or Projects page.
2. Upload mzML/mzXML/MGF/MSP/CSV/TSV/mzTab files.
3. Upload or edit sample metadata with grouping columns such as condition, batch, subject ID, and time point.
4. Choose a workflow preset or preserve/edit `.mzbatch` text in the Workflow Builder.
5. Submit a mock full-pipeline job.
6. Watch job progress/logs in Job Monitor.
7. Inspect feature, annotation, and statistics tables; Plotly PCA/volcano/heatmap placeholders; and molecular network preview.
8. Download the job ZIP archive.

## Real MZmine and SIRIUS integration points

Mock execution is controlled by `MOCK_EXECUTION=true`. To integrate real engines:

1. Mount or install MZmine in `workers/mzmine` or the backend/worker image.
2. Set `MZMINE_BINARY` to the executable path.
3. Set `MZMINE_BATCH_FLAG` if your deployed MZmine wrapper expects a flag other than `-batch`.
4. Mount SIRIUS in `workers/sirius` and set `SIRIUS_BINARY`.
5. Configure SIRIUS login/license server-side only. Do not expose credentials through frontend environment variables.
6. Set `MOCK_EXECUTION=false` only after the external tools are installed and validated.
7. Submit jobs with uploaded project-owned inputs. Real MZmine jobs require mzML/mzXML/imzML plus preserved `.mzbatch`; real SIRIUS jobs require MGF/MSP or an explicitly selected input file.

The engine status page already detects Java, MZmine, SIRIUS, matchms, MS2DeepScore, MS2Query, DREAMS, Spec2Vec, RDKit, mounted models, and mounted libraries.

Real-run artifacts:

- `data/workflow_configs/job_<id>.mzbatch`
- `data/results/job_<id>/workflow.mzbatch`
- `data/results/job_<id>/command_manifest.json`
- `data/results/job_<id>/*.stdout.log`
- `data/results/job_<id>/*.stderr.log`
- parsed `ResultTable` rows when supported output files are present

## Libraries and models

Mount user-provided spectral libraries and pretrained models:

- `./data/libraries:/data/libraries`
- `./data/models:/data/models`

Do not bundle licensed libraries. NIST MSP exports, commercial SIRIUS assets, or proprietary model files should only be mounted by users who have legal access.

## Storage layout

Docker Compose mounts:

- `./data/uploads`
- `./data/results`
- `./data/libraries`
- `./data/models`
- `./data/logs`
- `./data/database`
- `./data/workflow_configs`

Each job writes features, annotations, statistics, network JSON, report HTML, and a reproducibility manifest.

## API coverage

Implemented MVP endpoints include:

- Projects: `POST/GET /api/projects`, `GET/DELETE /api/projects/{id}`, archive download
- Uploads: `POST/GET /api/projects/{id}/files`, `DELETE /api/files/{id}`
- Metadata: `POST/GET /api/projects/{id}/metadata`, `PUT /api/metadata/{id}`, validation
- Workflows: presets, create/read/update/validate
- Jobs: create/list/read/cancel/retry/logs/events/download
- Results: features, annotations, statistics, plots, network
- Libraries/models: upload/list/delete/index
- System: status and engines

## Tests

Backend:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests
```

Frontend:

```bash
cd frontend
npm install
npm test
npm run build
```

## Troubleshooting

- If uploads fail, confirm the file extension is supported and `UPLOAD_MAX_MB` is large enough.
- If engine status says `not_installed`, mount/install the corresponding binary or Python package in the relevant image.
- If SIRIUS needs login/license, configure it inside the backend/worker environment; credentials are intentionally absent from the frontend.
- If real jobs fail immediately, inspect `data/results/job_<id>/command_manifest.json` and the corresponding stderr log.
- To reset local state, stop containers and remove `data/database/fragmentiq.db` plus per-job directories under `data/results`.

## Production notes

- Put the frontend/backend behind Nginx or Traefik with TLS.
- Use PostgreSQL by setting `DATABASE_URL` to a Postgres DSN.
- Keep `MOCK_EXECUTION=false` only after worker containers and external tools are installed and validated.
- Add queue-backed workers for long-running real MZmine/SIRIUS/ML tasks; Redis is already present in compose as the queue substrate.
