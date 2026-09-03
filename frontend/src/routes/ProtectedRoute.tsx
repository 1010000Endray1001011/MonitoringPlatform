import { Navigate, Outlet } from 'react-router-dom'
import { useAuthBootstrap } from '../auth/useAuthBootstrap'

export function ProtectedRoute() {
  const { ready, isAuthenticated } = useAuthBootstrap()

  // Renders nothing rather than a spinner for now — this window is
  // typically one network round trip, and a loading widget is exactly the
  // kind of visual detail that belongs in the later theming pass, not here.
  if (!ready) return null
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}
