import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'

export function RequireAuth() {
  const auth = useAuthStore((s) => s.authenticated)
  const loc = useLocation()
  if (!auth) return <Navigate to="/login" replace state={{ from: loc }} />
  return <Outlet />
}
