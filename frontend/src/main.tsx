import { StrictMode } from 'react'
import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import App from './App'
import LoginPage from './LoginPage'
import './styles.css'

function RootRoutes() {
  const [isLoggedIn, setIsLoggedIn] = useState(() => sessionStorage.getItem('ecs-demo-authenticated') === 'true')
  const [userEmail, setUserEmail] = useState(() => sessionStorage.getItem('ecs-demo-user') ?? 'demo@ecs.local')

  return <Routes><Route path="/login" element={<LoginPage onLogin={(email) => { sessionStorage.setItem('ecs-demo-authenticated', 'true'); sessionStorage.setItem('ecs-demo-user', email); setUserEmail(email); setIsLoggedIn(true) }} />} /><Route path="/" element={<Navigate to={isLoggedIn ? '/retirement-builder' : '/login'} replace />} /><Route path="*" element={isLoggedIn ? <App userEmail={userEmail} /> : <Navigate to="/login" replace />} /></Routes>
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <RootRoutes />
    </BrowserRouter>
  </StrictMode>,
)

