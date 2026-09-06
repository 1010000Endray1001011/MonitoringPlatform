import { useNavigate } from 'react-router-dom'
import { Button } from 'react95'
import { logout } from '../auth/logout'

// Shared across all four protected screens (dashboard, monitor detail,
// incidents, channels) — without it, /incidents and /channels would only
// be reachable by typing the URL directly, which fails the "no Swagger,
// no manual API client" bar every screen in this phase is held to.
export function NavBar() {
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav>
      <Button onClick={() => navigate('/dashboard')}>Dashboard</Button>
      <Button onClick={() => navigate('/incidents')}>Incidents</Button>
      <Button onClick={() => navigate('/channels')}>Channels</Button>
      <Button onClick={handleLogout}>Log out</Button>
    </nav>
  )
}
