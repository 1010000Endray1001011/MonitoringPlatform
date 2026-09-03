import { Route, Routes } from 'react-router-dom'
import { HttpResponse, http } from 'msw'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { RegisterPage } from './RegisterPage'

const BASE = 'http://localhost:8000'

function renderRegisterRoute() {
  return renderWithProviders(
    <Routes>
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<div>Login placeholder</div>} />
    </Routes>,
    { route: '/register' },
  )
}

function fillAndSubmit(email: string, password: string, passwordConfirm: string) {
  fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: email } })
  fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: password } })
  fireEvent.change(screen.getByPlaceholderText('Confirm password'), {
    target: { value: passwordConfirm },
  })
  fireEvent.click(screen.getByRole('button', { name: /register/i }))
}

describe('RegisterPage', () => {
  it('navigates to /login after a successful registration', async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/register`, () =>
        HttpResponse.json({ id: '1', email: 'dev@example.com' }, { status: 201 }),
      ),
    )
    renderRegisterRoute()

    fillAndSubmit('dev@example.com', 'S0me-Str0ng-Pass', 'S0me-Str0ng-Pass')

    await waitFor(() => expect(screen.getByText('Login placeholder')).toBeInTheDocument())
  })

  it('shows the server-side validation message on a 400, without navigating', async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/register`, () =>
        HttpResponse.json(
          { error: { code: 'validation_error', details: { email: ['Already registered.'] } } },
          { status: 400 },
        ),
      ),
    )
    renderRegisterRoute()

    fillAndSubmit('dev@example.com', 'S0me-Str0ng-Pass', 'S0me-Str0ng-Pass')

    expect(await screen.findByRole('alert')).toHaveTextContent('Already registered.')
    expect(screen.queryByText('Login placeholder')).not.toBeInTheDocument()
  })
})
