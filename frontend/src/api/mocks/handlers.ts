import type { HttpHandler } from 'msw'

// Empty by default — each test file registers only the handlers it needs
// via server.use(...), scoped to that test by the afterEach reset in
// src/test/setup.ts. Nothing here is shared global fixture data.
export const handlers: HttpHandler[] = []
