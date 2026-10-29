import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './styles/style.css'
import './styles/interface.css'
import './styles/stage.css'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
