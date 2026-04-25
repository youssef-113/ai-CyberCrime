import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import Scene3D from '../Scene3D'
import clsx from 'clsx'

export default function MainLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const isLanding = location.pathname === '/'
  const isAuthPage = location.pathname === '/login' || location.pathname === '/signup'

  // Auth pages render without layout chrome
  if (isAuthPage) {
    return (
      <div className="min-h-screen relative">
        <Scene3D />
        <div className="relative z-10">
          <Header onMenuToggle={() => setMobileMenuOpen(!mobileMenuOpen)} />
          <main>
            <Outlet />
          </main>
        </div>
      </div>
    )
  }

  if (isLanding) {
    return (
      <div className="min-h-screen relative">
        <Scene3D />
        <div className="relative z-10">
          <Header onMenuToggle={() => setMobileMenuOpen(!mobileMenuOpen)} />
          <main>
            <Outlet />
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col relative">
      <Scene3D />
      <div className="relative z-10 flex flex-col min-h-screen">
        <Header onMenuToggle={() => setMobileMenuOpen(!mobileMenuOpen)} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-neutral-950/80 backdrop-blur-sm perspective-grid">
            <div className="max-w-7xl mx-auto px-4 lg:px-6 py-6">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-56 bg-neutral-950 border-r border-neutral-800 p-4">
            <Sidebar />
          </div>
        </div>
      )}
    </div>
  )
}
