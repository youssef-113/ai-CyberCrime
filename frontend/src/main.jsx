import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { initializeAlertStyles } from './utils/alertConfig'

// Initialize SweetAlert2 custom styles
initializeAlertStyles()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
