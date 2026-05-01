import { NavLink } from 'react-router-dom'
import { Badge, DarkThemeToggle } from 'flowbite-react'
import {
  BeakerIcon,
  ChartBarIcon,
  CircleStackIcon,
  Cog6ToothIcon,
  FolderIcon,
  HomeIcon,
  QueueListIcon,
  ShareIcon,
  TableCellsIcon,
  UploadIcon,
} from '@heroicons/react/24/outline'

const nav = [
  { to: '/', label: 'Dashboard', icon: HomeIcon },
  { to: '/projects', label: 'Projects', icon: FolderIcon },
  { to: '/upload', label: 'Upload', icon: UploadIcon },
  { to: '/metadata', label: 'Metadata', icon: TableCellsIcon },
  { to: '/workflows', label: 'Workflow Builder', icon: QueueListIcon },
  { to: '/jobs', label: 'Job Monitor', icon: BeakerIcon },
  { to: '/results', label: 'Results', icon: CircleStackIcon },
  { to: '/visualizations', label: 'Visualizations', icon: ChartBarIcon },
  { to: '/network', label: 'Molecular Network', icon: ShareIcon },
  { to: '/system', label: 'System Status', icon: Cog6ToothIcon },
]

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 border-r border-slate-200 bg-white/95 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:block">
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-indigo-600 p-2 text-white shadow-lg shadow-indigo-600/20">
              <BeakerIcon className="h-7 w-7" />
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
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-200'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Project context</p>
              <h2 className="text-lg font-semibold">Self-hosted metabolomics workspace</h2>
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
