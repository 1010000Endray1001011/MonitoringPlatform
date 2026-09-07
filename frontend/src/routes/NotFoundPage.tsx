import { useNavigate } from 'react-router-dom'
import { Button } from 'react95'
import { PageLayout } from '../components/PageLayout'

// Public and auth-agnostic on purpose — a bad URL isn't a permissions
// question, so it doesn't belong behind ProtectedRoute. "Back to
// dashboard" still ends up at /login for a logged-out visitor; that
// redirect is ProtectedRoute's job, not this page's.
export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <PageLayout title="404 — Not Found" size="compact">
      <p>There's nothing at this address.</p>
      <Button onClick={() => navigate('/dashboard')}>Back to dashboard</Button>
    </PageLayout>
  )
}
