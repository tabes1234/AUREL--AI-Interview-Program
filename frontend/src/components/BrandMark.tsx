import { useId } from 'react'
import { cn } from '../lib/cn'

/**
 * 观澜品牌组件（全站唯一 Logo 来源，public/images/aurel-logo-mark.svg 与其同源）：
 * 圆角方印内的「海鸥掠过日出海平线」——AI 顾问「小鸥」展翅朝远方日光飞行，
 * 下方三层错落微澜；蓝色渐变底 + 白色负空间，24-32px 下依然可辨。
 */

interface BrandMarkProps {
  size?: number
  className?: string
}

export function BrandMark({ size = 36, className }: BrandMarkProps) {
  // 每个实例独立的渐变 id，避免同页多实例时 url(#) 冲突
  const uid = useId().replace(/:/g, '')
  const bgId = `aurel-logo-bg-${uid}`
  const glowId = `aurel-logo-glow-${uid}`

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      role="img"
      aria-label="观澜 AUREL 品牌标志"
      className={cn('shrink-0', className)}
    >
      <defs>
        <linearGradient id={bgId} x1="24" y1="0" x2="24" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5B92E2" />
          <stop offset="0.55" stopColor="#3E70BE" />
          <stop offset="1" stopColor="#2E5AA8" />
        </linearGradient>
        <radialGradient
          id={glowId}
          cx="0"
          cy="0"
          r="1"
          gradientUnits="userSpaceOnUse"
          gradientTransform="translate(33.5 13.5) scale(7.5)"
        >
          <stop stopColor="#FFFFFF" stopOpacity="0.5" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width="48" height="48" rx="13" fill={`url(#${bgId})`} />

      {/* 远方日光：柔和不喧宾夺主 */}
      <circle cx="33.5" cy="13.5" r="7.5" fill={`url(#${glowId})`} />
      <circle cx="33.5" cy="13.5" r="3.2" fill="#FFE9BE" />

      {/* 小鸥：双翼舒展，朝日光方向远行 */}
      <path
        d="M7 14.8 C10 10.6 14 10.6 16.8 13.6 C19.6 10.6 23.6 10.6 26.6 14.8"
        stroke="#FFFFFF"
        strokeWidth="2.6"
        strokeLinecap="round"
        fill="none"
      />

      {/* 海平线与三层微澜：白色负空间，越近越淡 */}
      <path
        d="M8 25.5c5.3-2.9 10.7-2.9 16 0s10.7 2.9 16 0"
        stroke="#FFFFFF"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M10 32.5c4.7-3.3 9.3-3.3 14 0s9.3 3.3 14 0"
        stroke="#DCEBFF"
        strokeWidth="2.7"
        strokeLinecap="round"
        opacity="0.88"
      />
      <path
        d="M12 39c4-2.5 8-2.5 12 0s8 2.5 12 0"
        stroke="#BDD8FC"
        strokeWidth="2.4"
        strokeLinecap="round"
        opacity="0.62"
      />
    </svg>
  )
}

interface BrandLockupProps {
  className?: string
  compact?: boolean
  /** overlay：置于海景之上，使用浅色文字 */
  tone?: 'dark' | 'light'
}

/** 横向品牌版本：标志 + 「观澜 AUREL」（非 compact 附座右铭短句） */
export function BrandLockup({ className, compact = false, tone = 'dark' }: BrandLockupProps) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <BrandMark size={compact ? 30 : 36} />
      <span className="flex flex-col leading-none">
        <span
          className={cn(
            'text-base font-bold tracking-wide',
            tone === 'light' ? 'text-white' : 'text-ink-strong',
          )}
        >
          观澜{' '}
          <span className={cn('font-semibold', tone === 'light' ? 'text-shallow' : 'text-ink-soft')}>
            AUREL
          </span>
        </span>
        {!compact ? (
          <span
            className={cn(
              'mt-1 text-[11px] tracking-wider',
              tone === 'light' ? 'text-shallow/85' : 'text-ink-soft',
            )}
          >
            见微知远 · 向新而行
          </span>
        ) : null}
      </span>
    </span>
  )
}
