import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './style.css'
import './interface.css'
import './stage.css'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
