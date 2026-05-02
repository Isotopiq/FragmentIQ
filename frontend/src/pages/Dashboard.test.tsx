import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Dashboard from './Dashboard'

vi.mock('flowbite-react', () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  Button: ({ children, onClick, disabled }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean }) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Card: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
  Progress: () => <div role="progressbar" />,
  Spinner: () => <span data-testid="spinner" />,
}))

vi.mock('../lib/api', () => ({
  api: {
    resetDemo: () => Promise.resolve({ status: 'seeded', project_id: 1, job_id: 1 }),
    installPackage: () => Promise.resolve({ status: 'installed', message: 'ok' }),
  },
  getProjects: () => Promise.resolve([]),
  getJobs: () => Promise.resolve([]),
  getEngines: () => Promise.resolve([]),
}))

describe('Dashboard', () => {
  it('renders quick actions', () => {
    render(<Dashboard />)
    expect(screen.getByText('New MZmine Job')).toBeInTheDocument()
    expect(screen.getByText('Full Pipeline')).toBeInTheDocument()
  })
})
