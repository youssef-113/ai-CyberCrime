import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="top-right"
      toastOptions={{
        style: {
          background: '#171717',
          color: '#FAFAFA',
          border: '1px solid #262626',
        },
        success: { iconTheme: { primary: '#00BD7D', secondary: '#171717' } },
        error: { iconTheme: { primary: '#DC2626', secondary: '#171717' } },
      }}
    />
  </React.StrictMode>,
)
