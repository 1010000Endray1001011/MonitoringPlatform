import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ChannelsPage } from './routes/ChannelsPage'
import { DashboardPage } from './routes/DashboardPage'
import { IncidentsPage } from './routes/IncidentsPage'
import { LoginPage } from './routes/LoginPage'
import { MonitorDetailPage } from './routes/MonitorDetailPage'
import { ProtectedRoute } from './routes/ProtectedRoute'
import { RegisterPage } from './routes/RegisterPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/monitors/:id" element={<MonitorDetailPage />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/channels" element={<ChannelsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
