import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

/** 受保护路由守卫：未登录跳转 /auth 并记录来路，登录成功后回到原页面 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-ink-soft">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600" aria-hidden="true" />
        <p className="text-sm">正在为你确认登录状态，请稍候…</p>
      </div>
    )
  }

  if (!user) {
    const redirect = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/auth?redirect=${redirect}`} replace />
  }

  return <>{children}</>
}
