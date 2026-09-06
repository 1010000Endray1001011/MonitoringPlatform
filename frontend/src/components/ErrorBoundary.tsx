import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Window, WindowContent, WindowHeader } from 'react95'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

// React still has no hook equivalent for componentDidCatch /
// getDerivedStateFromError as of React 19 — a class component is the only
// way to implement this. Wraps every route (not one boundary per page) so
// a render exception anywhere stops being a blank white screen, without
// needing this repeated at every route definition.
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // No error-tracking service wired up — out of scope for this project —
    // so the console is the only place this is ever surfaced.
    console.error('Unhandled error in a route:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <Window>
          <WindowHeader>Something went wrong</WindowHeader>
          <WindowContent>
            <p>This screen hit an unexpected error and couldn't continue.</p>
            {/* A full navigation, not react-router's navigate() — the tree
                below this boundary is in an unknown state, so the same
                "guarantee a clean slate" reasoning as the 401 handler in
                api/client.ts applies here too. */}
            <Button onClick={() => window.location.assign('/dashboard')}>Back to dashboard</Button>
          </WindowContent>
        </Window>
      )
    }
    return this.props.children
  }
}
