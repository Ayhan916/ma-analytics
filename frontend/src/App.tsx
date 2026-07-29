import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { DashboardPage } from './pages/DashboardPage'
import { DataSourcesPage } from './pages/DataSourcesPage'
import { AppDetailPage } from './pages/AppDetailPage'
import { SearchPage } from './pages/SearchPage'
import { InboxPage } from './pages/InboxPage'
import { KanbanPage } from './pages/KanbanPage'
import { SettingsPage } from './pages/SettingsPage'
import { InnovationLabPage } from './pages/InnovationLabPage'
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/datasources" element={<ProtectedRoute><DataSourcesPage /></ProtectedRoute>} />
          <Route path="/datasources/:id" element={<ProtectedRoute><AppDetailPage /></ProtectedRoute>} />
          <Route path="/search" element={<ProtectedRoute><SearchPage /></ProtectedRoute>} />
          <Route path="/inbox" element={<ProtectedRoute><InboxPage /></ProtectedRoute>} />
          <Route path="/kanban" element={<ProtectedRoute><KanbanPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/innovation" element={<ProtectedRoute><InnovationLabPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
