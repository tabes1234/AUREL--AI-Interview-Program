import { Menu, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { PageBackground } from '../PageBackground'
import { PointerGlow } from '../PointerGlow'
import { XiaouCompanion } from '../XiaouCompanion'
import { LogoLockup } from '../LogoMark'
import { useOnboardingAutoStart } from '../onboarding/use-onboarding-autostart'
import { trackPageView } from '../../lib/usageTracker'
import { SidebarNav } from './SidebarNav'

/** 行舟布局：桌面端左侧渐变导航 + 移动端抽屉导航 + 页面切换动画 */
export default function AppLayout() {
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [prevPathname, setPrevPathname] = useState(location.pathname)

  // 首次进入行舟时自动开启一次引航（已完成或跳过后不再弹出）
  useOnboardingAutoStart(location.pathname)

  // 页面访问上报（观澜管理中心数据源；失败静默，不影响页面）
  useEffect(() => {
    trackPageView(location.pathname)
  }, [location.pathname])

  // 路由变化时关闭移动端抽屉（渲染期间调整 state 的官方推荐模式）
  if (prevPathname !== location.pathname) {
    setPrevPathname(location.pathname)
    setMobileOpen(false)
  }

  return (
    <div className="relative min-h-screen bg-surface">
      {/* 蓝调雪景场景背景（固定底层，pointer-events: none）+ 鼠标柔和光晕 */}
      <PageBackground scene="workspace" />
      <PointerGlow intensity="whisper" />
      {/* 小鸥悬浮入口：全工作区共用，点击直达知途 AI 对话 */}
      <XiaouCompanion />

      {/* 桌面侧栏：浅蓝白渐变底 + 细腻蓝白分隔线 */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-sidebar-wash lg:block">
        <div className="sidebar-edge absolute inset-y-0 right-0 w-px" aria-hidden="true" />
        <SidebarNav indicatorId="desktop" />
      </aside>

      <AnimatePresence>
        {mobileOpen ? (
          <>
            <motion.div
              key="drawer-backdrop"
              className="fixed inset-0 z-40 bg-ink-strong/40 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <motion.aside
              key="drawer"
              className="fixed inset-y-0 left-0 z-50 w-72 bg-sidebar-wash shadow-raised lg:hidden"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.24, ease: 'easeOut' }}
              aria-label="导航菜单"
            >
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="absolute right-3 top-4 rounded-md p-1.5 text-ink-soft transition-colors hover:bg-white/80 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                aria-label="关闭导航菜单"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
              <SidebarNav indicatorId="mobile" onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>

      <div className="relative lg:pl-64">
        {/* 主区顶部一抹极淡水汽（纯背景装饰） */}
        <div
          aria-hidden="true"
          className="workspace-haze pointer-events-none absolute inset-x-0 top-0 h-80"
        />

        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line/70 bg-white/70 px-4 py-3 backdrop-blur-md lg:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-ink-soft transition-colors hover:bg-mist hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
            aria-label="打开导航菜单"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
          <Link
            to="/"
            aria-label="返回观澜首页"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
          >
            <LogoLockup compact />
          </Link>
        </header>

        {/* A1 路由切换淡入位移：纯 CSS 挂载即播放，不依赖 JS 动画生命周期 */}
        <div key={location.pathname} className="page-enter">
          {/* 工作区玻璃画布：一整张冰白玻璃承载主体内容，与雪景隔离且不遮挡交互 */}
          <div className="glass-surface glass-workspace mx-3 rounded-3xl sm:mx-5 lg:mx-8">
            <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-12 lg:py-12">
              <Outlet />
            </main>
          </div>
          {/* 页脚留白：编辑式页面以呼吸感收尾 */}
          <div aria-hidden="true" className="h-16" />
        </div>
      </div>
    </div>
  )
}
