import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import { ConfigProvider } from './config/provider'

const root = createRoot(document.getElementById('root')!)
root.render(
  <ConfigProvider>
    <App />
  </ConfigProvider>
)
