import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Dashboard from './Dashboard'

vi.mock('flowbite-react', () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  Button: ({ children }: { children: React.ReactNode }) => <button>{children}</button>,
  Card: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
  Progress: () => <div role="progressbar" />,
}))

vi.mock('../lib/api', () => ({
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
