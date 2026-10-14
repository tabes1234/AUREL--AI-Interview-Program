import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { AuthUser } from '../types'
import { AuthContext } from './AuthContext'

async function queryMe(): Promise<AuthUser | null> {
  try {
    const me = await api.authMe()
    return me.authenticated ? me.user : null
  } catch {
    // 会话失效/网络异常时按未登录处理，不在前端缓存虚假登录态
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async (): Promise<AuthUser | null> => {
    const next = await queryMe()
    setUser(next)
    setLoading(false)
    return next
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      // 无论后端响应如何，前端都不再保留用户资料；服务端会话已真实撤销
      setUser(null)
    }
  }, [])

  useEffect(() => {
    let active = true
    queryMe().then((next) => {
      if (!active) return
      setUser(next)
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [])

  const value = useMemo(() => ({ user, loading, refresh, signOut }), [user, loading, refresh, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
