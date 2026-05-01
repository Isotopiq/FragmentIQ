import type { ReactNode } from 'react'
import { Badge, DarkThemeToggle } from 'flowbite-react'
import type { Project } from '../lib/types'

const nav = [
  { key: 'dashboard', label: 'Dashboard', icon: '⌂' },
  { key: 'projects', label: 'Projects', icon: '▣' },
  { key: 'upload', label: 'Upload', icon: '↑' },
  { key: 'metadata', label: 'Metadata', icon: '▦' },
  { key: 'workflows', label: 'Workflow Builder', icon: '⚙' },
  { key: 'jobs', label: 'Job Monitor', icon: '▶' },
  { key: 'results', label: 'Results', icon: '◎' },
  { key: 'visualizations', label: 'Visualizations', icon: '◌' },
  { key: 'statistics', label: 'Statistics', icon: '∑' },
  { key: 'network', label: 'Molecular Network', icon: '◇' },
  { key: 'libraries', label: 'Libraries & Models', icon: '◫' },
  { key: 'system', label: 'System Status', icon: '✓' },
]

export type PageKey = (typeof nav)[number]['key']

type LayoutProps = {
  children: ReactNode
  page: PageKey
  setPage: (page: PageKey) => void
  projects: Project[]
  projectId?: number
  setProjectId: (projectId?: number) => void
}

export function Layout({ children, page, setPage, projects, projectId, setProjectId }: LayoutProps) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 border-r border-slate-200 bg-white/95 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:block">
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-indigo-600 p-2 text-white shadow-lg shadow-indigo-600/20">
                <span className="block h-7 w-7 text-center text-xl leading-7">⚗</span>
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">FragmentIQ</h1>
              <p className="text-xs text-slate-500">LC-MS/MS annotation platform</p>
            </div>
          </div>
          <Badge color="info" className="mt-4 w-fit">Mock-ready MVP</Badge>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setPage(item.key)}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
                  page === item.key
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-200'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`}
            >
              <span className="inline-flex h-5 w-5 items-center justify-center">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Project context</p>
              <select
                className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                value={projectId ?? ''}
                onChange={(event) => setProjectId(event.target.value ? Number(event.target.value) : undefined)}
              >
                <option value="">Self-hosted metabolomics workspace</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <Badge color="success">API connected in Docker</Badge>
              <DarkThemeToggle />
            </div>
          </div>
        </header>
        <div className="p-4 lg:p-8">{children}</div>
      </main>
    </div>
  )
}

export default Layout
