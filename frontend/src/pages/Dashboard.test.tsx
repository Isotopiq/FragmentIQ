import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from './Dashboard'

describe('Dashboard', () => {
  it('renders quick actions', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )
    expect(screen.getByText('New MZmine Job')).toBeInTheDocument()
    expect(screen.getByText('Full Pipeline')).toBeInTheDocument()
  })
})
