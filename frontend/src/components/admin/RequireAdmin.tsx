import { Loader2, ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { LogoLockup } from '../LogoMark'

/**
 * 管理中心路由守卫：未登录跳认证页；已登录但非管理员显示 403。
 * 前端判断仅为展示层，所有 /api/v1/admin 接口都在服务端二次校验角色。
 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-ink-soft">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600" aria-hidden="true" />
        <p className="text-sm">正在确认访问身份…</p>
      </div>
    )
  }

  if (!user) {
    const redirect = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/auth?redirect=${redirect}`} replace />
  }

  if (user.role !== 'admin') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface px-6 text-center">
        <LogoLockup className="h-9" />
        <div className="flex items-center gap-2 text-ink">
          <ShieldAlert className="h-5 w-5 text-brand-600" aria-hidden="true" />
          <h1 className="text-lg font-semibold">需要管理员权限</h1>
        </div>
        <p className="max-w-md text-sm leading-6 text-ink-soft">
          观澜管理中心仅对管理员开放。如需访问，请联系项目负责人为你的账号开通权限。
        </p>
        <a href="/" className="rounded-full border border-line bg-white px-5 py-2 text-sm font-medium text-brand-700 transition hover:border-ripple hover:shadow-card">
          返回观澜首页
        </a>
      </div>
    )
  }

  return <>{children}</>
}
