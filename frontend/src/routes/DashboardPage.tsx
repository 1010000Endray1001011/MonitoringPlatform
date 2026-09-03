import { useNavigate } from 'react-router-dom'
import { Button, Window, WindowContent, WindowHeader } from 'react95'
import { logout } from '../auth/logout'

// Placeholder only — the real monitor list, creation form, and live status
// are a separate, later piece of work. This exists so the protected-route
// and auth flow have somewhere real to land and be checked by hand.
export function DashboardPage() {
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <Window>
      <WindowHeader>Dashboard</WindowHeader>
      <WindowContent>
        <p>You're logged in.</p>
        <Button onClick={handleLogout}>Log out</Button>
      </WindowContent>
    </Window>
  )
}
