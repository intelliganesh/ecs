import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const DEMO_EMAIL = 'demo@ecs.local'
const DEMO_PASSWORD = 'EcsDemo123!'

function PasswordIcon({ hidden }: { hidden: boolean }) {
  return hidden
    ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A10.9 10.9 0 0 1 12 5c5.2 0 8.8 4.5 9.8 7-.3.8-.9 1.8-1.8 2.8M6.2 6.2C3.8 7.7 2.5 10 2.2 12c.6 1.5 2.2 3.9 5 5.7A10.8 10.8 0 0 0 12 19c1 0 2-.2 2.9-.5" /></svg>
    : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.2 12C3.2 9.5 6.8 5 12 5s8.8 4.5 9.8 7c-1 2.5-4.6 7-9.8 7s-8.8-4.5-9.8-7Z" /><circle cx="12" cy="12" r="2.8" /></svg>
}

export default function LoginPage({ onLogin }: { onLogin: (email: string) => void }) {
  const navigate = useNavigate()
  const [email, setEmail] = useState(DEMO_EMAIL)
  const [password, setPassword] = useState(DEMO_PASSWORD)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  const submitLogin = (event: FormEvent) => {
    event.preventDefault()
    if (email.trim().toLowerCase() !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
      setError('Incorrect email or password.')
      return
    }
    onLogin(email.trim())
    navigate('/retirement-builder', { replace: true })
  }

  return <main className="login-page"><section className="login-card"><div className="login-brand">ESC</div><form onSubmit={submitLogin}><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" /></label><label>Password<span className="password-field"><input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /><button type="button" className="password-toggle" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Hide password' : 'Show password'}><PasswordIcon hidden={showPassword} /></button></span></label>{error && <p className="login-error">{error}</p>}<button className="button button-primary login-button" type="submit">Sign in</button></form></section></main>
}
