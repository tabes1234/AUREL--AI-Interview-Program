import { BadgeCheck, CalendarDays, Clock3, LogOut, AtSign, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

const STATUS_LABELS: Record<string, string> = {
  active: '使用中',
  disabled: '已停用',
}

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export default function MePage() {
  const { user, refresh, signOut } = useAuth()
  const navigate = useNavigate()
  const [loggingOut, setLoggingOut] = useState(false)

  // 进入名笺页时向服务器核实一次最新账户资料，不使用静态假数据
  useEffect(() => {
    void refresh()
  }, [refresh])

  if (!user) return null

  const handleLogout = async () => {
    if (loggingOut) return
    if (!window.confirm('确定要退出观澜吗？之后凭用户名与密码随时可以回来。')) return
    setLoggingOut(true)
    try {
      await signOut()
      navigate('/auth', { replace: true })
    } finally {
      setLoggingOut(false)
    }
  }

  const rows = [
    { icon: UserRound, label: '昵称', value: user.nickname },
    { icon: AtSign, label: '用户名', value: user.username },
    { icon: BadgeCheck, label: '账户状态', value: STATUS_LABELS[user.status] ?? user.status },
    { icon: CalendarDays, label: '加入观澜', value: formatDateTime(user.created_at) },
    { icon: Clock3, label: '最近归来', value: formatDateTime(user.last_login_at) },
  ]

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-ink-strong">我的名笺</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          这里记录着你在观澜的印记，资料来自观澜服务器的真实账户档案。
        </p>
      </header>

      <section className="rounded-2xl border border-line/80 bg-white/90 p-6 shadow-card sm:p-8">
        <div className="flex items-center gap-4 border-b border-line/70 pb-6">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-shallow to-mist text-xl font-bold text-brand-700">
            {user.nickname.slice(0, 1)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-lg font-bold text-ink-strong">{user.nickname}</p>
            <p className="mt-0.5 truncate text-sm text-ink-soft">@{user.username}</p>
          </div>
          <span className="ml-auto shrink-0 rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
            {STATUS_LABELS[user.status] ?? user.status}
          </span>
        </div>

        <dl className="mt-6 space-y-4">
          {rows.map((row) => (
            <div key={row.label} className="flex items-start gap-3">
              <row.icon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600/80" aria-hidden="true" />
              <dt className="w-24 shrink-0 text-sm text-ink-soft">{row.label}</dt>
              <dd className="min-w-0 break-words text-sm font-medium text-ink">{row.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="mt-6 flex justify-end">
        <button
          type="button"
          onClick={handleLogout}
          disabled={loggingOut}
          className="inline-flex items-center gap-2 rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          {loggingOut ? '正在告别…' : '退出登录'}
        </button>
      </div>
    </div>
  )
}
