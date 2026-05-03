import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { CaseProvider } from './context/CaseContext'
import { ThemeProvider } from './context/ThemeContext'
import { AuthProvider } from './context/AuthContext'
import MainLayout from './components/layout/MainLayout'
import ProtectedRoute from './components/ProtectedRoute'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'
import CaseAnalysisPage from './pages/CaseAnalysisPage'
import ChatbotPage from './pages/ChatbotPage'
import CaseHistoryPage from './pages/CaseHistoryPage'
import SettingsPage from './pages/SettingsPage'
import VerificationsPage from './pages/VerificationsPage'

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <CaseProvider>
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />

              {/* Layout-wrapped routes */}
              <Route element={<MainLayout />}>
                <Route path="/" element={<LandingPage />} />
                {/* Protected routes */}
                <Route path="/dashboard" element={
                  <ProtectedRoute><DashboardPage /></ProtectedRoute>
                } />
                <Route path="/analyze" element={
                  <ProtectedRoute><CaseAnalysisPage /></ProtectedRoute>
                } />
                <Route path="/chatbot" element={
                  <ProtectedRoute><ChatbotPage /></ProtectedRoute>
                } />
                <Route path="/history" element={
                  <ProtectedRoute><CaseHistoryPage /></ProtectedRoute>
                } />
                <Route path="/settings" element={
                  <ProtectedRoute><SettingsPage /></ProtectedRoute>
                } />
                <Route path="/verifications" element={
                  <ProtectedRoute><VerificationsPage /></ProtectedRoute>
                } />
              </Route>

              {/* Catch-all redirect */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </CaseProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
