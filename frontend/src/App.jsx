import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { CaseProvider } from './context/CaseContext'
import { ThemeProvider } from './context/ThemeContext'
import MainLayout from './components/layout/MainLayout'
import LandingPage from './pages/LandingPage'
import DashboardPage from './pages/DashboardPage'
import CaseAnalysisPage from './pages/CaseAnalysisPage'
import ChatbotPage from './pages/ChatbotPage'
import CaseHistoryPage from './pages/CaseHistoryPage'
import SettingsPage from './pages/SettingsPage'

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <CaseProvider>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/analyze" element={<CaseAnalysisPage />} />
              <Route path="/chatbot" element={<ChatbotPage />} />
              <Route path="/history" element={<CaseHistoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </CaseProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
