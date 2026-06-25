import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Swal from 'sweetalert2'
import { forceCloseAllAlerts } from '../utils/alertConfig'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  // Force-close any leftover alert overlays that would block interactions
  useEffect(() => {
    Swal.close()
    forceCloseAllAlerts()
  }, [])

  if (!isAuthenticated) {
    // Save the attempted URL for redirect after login
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
