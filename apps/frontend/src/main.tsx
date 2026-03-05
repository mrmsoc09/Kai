
import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import ToastContainer from './components/ToastContainer'

const root = createRoot(document.getElementById('root')!)
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
      <ToastContainer />
    </ErrorBoundary>
  </React.StrictMode>
)
