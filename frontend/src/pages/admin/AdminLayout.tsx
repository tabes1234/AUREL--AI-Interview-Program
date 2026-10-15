import { ArrowLeft, BarChart3, Bot, ClipboardList, LayoutDashboard, Users } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LogoLockup } from '../../components/LogoMark'
import { useAuth } from '../../context/useAuth'

const NAV_ITEMS = [
  { to: '/admin', label: '数据总览', icon: LayoutDashboard, end: true },
  { to: '/admin/users', label: '用户使用', icon: Users, end: false },
  { to: '/admin/modules', label: '功能分析', icon: BarChart3, end: false },
  { to: '/admin/ai', label: 'AI 运行', icon: Bot, end: false },
  { to: '/admin/audit', label: '操作审计', icon: ClipboardList, end: false },
]

/** 观澜管理中心布局：独立于工作区的左侧管理导航，信息密度优先 */
export default function AdminLayout() {
  const location = useLocation()
  const { user } = useAuth()

  return (
    <div className="relative min-h-screen bg-surface text-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-[1440px]">
        {/* 左侧管理导航 */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-white/70 py-6 backdrop-blur-sm md:flex">
          <div className="px-5">
            <LogoLockup className="h-8" />
            <p className="mt-3 text-[13px] font-semibold text-ink">观澜管理中心</p>
            <p className="mt-0.5 text-xs leading-5 text-ink-soft">AUREL ADMIN</p>
          </div>
          <nav className="mt-6 flex-1 space-y-1 px-3" aria-label="管理中心导航">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                    isActive
                      ? 'bg-gradient-to-r from-brand-600 to-brand-500 text-white shadow-card'
                      : 'text-ink-soft hover:bg-brand-pale hover:text-ink'
                  }`
                }
              >
                <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mx-3 rounded-xl bg-brand-pale/70 px-3.5 py-3 text-xs text-ink-soft">
            <p className="font-medium text-ink">{user?.nickname || user?.username}</p>
            <p className="mt-0.5">管理员 · {user?.username}</p>
          </div>
        </aside>

        {/* 主内容 */}
        <div className="min-w-0 flex-1">
          {/* 顶部条：标题 + 身份 + 返回工作区（移动端导航在下方滚动区） */}
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5 md:px-8">
            <div className="flex items-center gap-3 md:hidden">
              <LogoLockup className="h-7" />
              <span className="text-sm font-semibold">管理中心</span>
            </div>
            <p className="hidden text-sm text-ink-soft md:block">洞察使用情况，持续优化每一次体验。</p>
            <div className="flex items-center gap-2 text-xs">
              <span className="hidden rounded-full bg-brand-pale px-3 py-1 font-medium text-brand-700 sm:inline">
                {user?.nickname || user?.username} · 管理员
              </span>
              <a
                href="/app"
                className="flex items-center gap-1 rounded-full border border-line bg-white px-3 py-1 font-medium text-ink-soft transition hover:border-ripple hover:text-ink"
              >
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                返回工作区
              </a>
            </div>
          </header>

          {/* 移动端横向导航 */}
          <nav className="flex gap-1 overflow-x-auto border-b border-line px-4 py-2 md:hidden" aria-label="管理中心导航">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-full px-3.5 py-1.5 text-xs font-medium transition ${
                    isActive ? 'bg-brand-600 text-white' : 'bg-white text-ink-soft hover:text-ink'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <main key={location.pathname} className="animate-fade-up px-5 py-6 md:px-8">
            <Outlet />
          </main>

          <footer className="border-t border-line px-5 py-4 text-xs text-ink-soft md:px-8">
            观澜管理中心 · 统计时区 UTC+8（北京时间）· 数据仅来自真实业务记录
          </footer>
        </div>
      </div>
    </div>
  )
}
