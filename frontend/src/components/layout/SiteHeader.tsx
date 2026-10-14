import { NavLink, Link } from 'react-router-dom'
import { LogoLockup } from '../LogoMark'
import { useOnboarding } from '../onboarding/onboarding-context'
import { cn } from '../../lib/cn'

/** 公共站点顶部导航：统一栏目（知途为 AI 职业顾问入口；引航为使用引导入口，点击直接开启） */
const PUBLIC_NAV_ITEMS = [
  { to: '/about', label: '观澜之意' },
  { to: '/app', label: '行舟' },
  { to: '/career-guide', label: '知途' },
  { to: '/announcements', label: '澜讯' },
] as const

interface SiteHeaderProps {
  /** overlay：悬浮于海景之上（首页）；solid：浅色页面页头 */
  variant?: 'overlay' | 'solid'
}

export function SiteHeader({ variant = 'solid' }: SiteHeaderProps) {
  const overlay = variant === 'overlay'
  const { startTour } = useOnboarding()
  return (
    <header
      className={cn(
        'hero-nav-in',
        // 两态均无底色：文字直接置于背景照片上，顶部无白色半透明条
        overlay ? 'sticky top-0 z-30 bg-transparent' : 'bg-transparent',
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          to="/"
          aria-label="返回观澜首页"
          className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-shallow"
        >
          <LogoLockup compact tone={overlay ? 'light' : 'dark'} />
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2" aria-label="主导航">
          {PUBLIC_NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'rounded-full px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-shallow sm:px-4',
                  overlay
                    ? isActive
                      ? 'bg-white/20 text-white'
                      : 'text-shallow hover:bg-white/10 hover:text-white'
                    : isActive
                      ? 'bg-shallow text-brand-700'
                      : 'text-ink hover:bg-mist hover:text-brand-700',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={startTour}
            className={cn(
              'rounded-full px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-shallow sm:px-4',
              overlay
                ? 'text-shallow hover:bg-white/10 hover:text-white'
                : 'text-ink hover:bg-mist hover:text-brand-700',
            )}
          >
            引航
          </button>
        </nav>
      </div>
    </header>
  )
}
