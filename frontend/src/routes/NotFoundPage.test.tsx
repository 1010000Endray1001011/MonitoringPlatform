import { fireEvent, screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/renderWithProviders'
import { NotFoundPage } from './NotFoundPage'

describe('NotFoundPage', () => {
  it('renders for an unmatched route and can navigate back to the dashboard', () => {
    renderWithProviders(
      <Routes>
        <Route path="*" element={<NotFoundPage />} />
        <Route path="/dashboard" element={<div>Dashboard placeholder</div>} />
      </Routes>,
      { route: '/this-does-not-exist' },
    )

    expect(screen.getByText(/nothing at this address/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Back to dashboard' }))

    expect(screen.getByText('Dashboard placeholder')).toBeInTheDocument()
  })
})
