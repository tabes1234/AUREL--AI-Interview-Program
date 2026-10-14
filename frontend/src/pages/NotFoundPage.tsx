import { Compass } from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'
import { AmbientBackground } from '../components/AmbientBackground'
import { ButtonLink } from '../components/ui/Button'
import { LogoMark } from '../components/LogoMark'

export default function NotFoundPage() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-surface px-4 text-center">
      <AmbientBackground />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="flex flex-col items-center"
      >
        <Link to="/" aria-label="返回观澜首页" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50">
          <LogoMark size={44} />
        </Link>
        <p className="mt-8 text-6xl font-bold tracking-tight text-brand-600">404</p>
        <h1 className="mt-4 text-xl font-semibold text-ink-strong">页面不存在</h1>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-ink-soft">
          你访问的页面不存在或已被移动。观其微澜，见其远势——让我们回到正确的航线上。
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <ButtonLink to="/" size="lg">
            返回首页
          </ButtonLink>
          <ButtonLink to="/app" variant="secondary" size="lg">
            <Compass className="h-4 w-4" aria-hidden="true" />
            进入行舟
          </ButtonLink>
        </div>
      </motion.div>
    </div>
  )
}
