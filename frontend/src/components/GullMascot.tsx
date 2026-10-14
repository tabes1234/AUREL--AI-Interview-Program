import { useId } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { cn } from '../lib/cn'

/**
 * AI 职业顾问「小鸥」吉祥物（原创矢量，public/images/aurel-gull-mascot.svg 与其同源）。
 *
 * 轻量状态动画（缓慢、精致、低干扰，尊重 prefers-reduced-motion）：
 * - idle：自然静态姿态
 * - thinking：极轻的呼吸浮动 + 脚下涟漪缓动
 * - speaking：双翼小幅起伏（绕肩部缓转）
 * - error：静态中性提示，不做夸张表情
 */
export type GullMascotStatus = 'idle' | 'thinking' | 'speaking' | 'error'

interface GullMascotProps {
  size?: number
  status?: GullMascotStatus
  /** 装饰性使用时隐藏无障碍名称 */
  className?: string
}

export function GullMascot({ size = 64, status = 'idle', className }: GullMascotProps) {
  const reduced = useReducedMotion()
  // 每个实例独立的渐变 id，避免同页多实例时 url(#) 冲突
  const uid = useId().replace(/:/g, '')
  const bodyId = `aurel-gull-body-${uid}`
  const wingId = `aurel-gull-wing-${uid}`
  const animateBody =
    !reduced && status === 'thinking' ? { y: [0, -1.8, 0] } : undefined
  const animateWing =
    !reduced && status === 'speaking' ? { rotate: [0, -4, 0, -2, 0] } : undefined
  const animateWingMirror =
    !reduced && status === 'speaking' ? { rotate: [0, 4, 0, 2, 0] } : undefined
  const animateRipple =
    !reduced && (status === 'thinking' || status === 'speaking')
      ? { opacity: [0.45, 0.85, 0.45], x: [0, 2.5, 0, -2.5, 0] }
      : undefined

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      role="img"
      aria-label={`小鸥${status === 'thinking' ? '（正在思考）' : status === 'speaking' ? '（正在回答）' : status === 'error' ? '（暂时没有回音）' : ''}`}
      className={cn(status === 'error' && 'opacity-90', className)}
    >
      <defs>
        <linearGradient id={bodyId} x1="48" y1="12" x2="48" y2="82" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#EAF3FF" />
        </linearGradient>
        <linearGradient id={wingId} x1="24" y1="48" x2="24" y2="66" gradientUnits="userSpaceOnUse">
          <stop stopColor="#DCEBFF" />
          <stop offset="1" stopColor="#BDD8FC" />
        </linearGradient>
      </defs>

      {/* 头身：呼吸/思考时整体轻微浮动 */}
      <motion.g
        animate={animateBody}
        transition={animateBody ? { duration: 3.2, repeat: Infinity, ease: 'easeInOut' } : undefined}
      >
        <path
          d="M48 12.5C58.5 12.5 66.5 20.5 66.5 30.5C66.5 37.5 63.5 43.5 58.8 47.6C65.5 53.8 68 62.5 64.2 70.2C60.2 78.3 54.6 81.8 48 81.8C41.4 81.8 35.8 78.3 31.8 70.2C28 62.5 30.5 53.8 37.2 47.6C32.5 43.5 29.5 37.5 29.5 30.5C29.5 20.5 37.5 12.5 48 12.5Z"
          fill={`url(#${bodyId})`}
          stroke="#4D83D6"
          strokeWidth="2.4"
          strokeLinejoin="round"
        />
        <ellipse cx="48" cy="63.5" rx="10.5" ry="9" fill="#F0F7FF" />
        {/* 头顶小羽尖 */}
        <path
          d="M48 12.5C47.4 9.2 49 6.6 51.6 6"
          stroke="#4D83D6"
          strokeWidth="1.8"
          strokeLinecap="round"
          fill="none"
        />
        {/* 眼睛 */}
        <circle cx="40.5" cy="32.5" r="2.5" fill="#315FAD" />
        <circle cx="55.5" cy="32.5" r="2.5" fill="#315FAD" />
        <circle cx="41.4" cy="31.6" r="0.9" fill="#FFFFFF" />
        <circle cx="56.4" cy="31.6" r="0.9" fill="#FFFFFF" />
        {/* 极淡腮红 */}
        <ellipse cx="35.8" cy="39.8" rx="3.1" ry="2.1" fill="#DCEBFF" />
        <ellipse cx="60.2" cy="39.8" rx="3.1" ry="2.1" fill="#DCEBFF" />
        {/* 喙 */}
        <path
          d="M43.6 40.6H52.4L48 46.8Z"
          fill="#4D83D6"
          stroke="#4D83D6"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
      </motion.g>

      {/* 双翼：回答时绕肩部小幅起伏 */}
      <motion.path
        d="M32.2 46.5C23 49 17.2 57.2 18.8 65.8C26 64.8 32 59 34.2 51.8C33.6 49.8 33 48 32.2 46.5Z"
        fill={`url(#${wingId})`}
        stroke="#4D83D6"
        strokeWidth="1.8"
        strokeLinejoin="round"
        style={{ transformOrigin: '32px 48px' }}
        animate={animateWing}
        transition={animateWing ? { duration: 3, repeat: Infinity, ease: 'easeInOut' } : undefined}
      />
      <motion.path
        d="M63.8 46.5C73 49 78.8 57.2 77.2 65.8C70 64.8 64 59 61.8 51.8C62.4 49.8 63 48 63.8 46.5Z"
        fill={`url(#${wingId})`}
        stroke="#4D83D6"
        strokeWidth="1.8"
        strokeLinejoin="round"
        style={{ transformOrigin: '64px 48px' }}
        animate={animateWingMirror}
        transition={animateWingMirror ? { duration: 3, repeat: Infinity, ease: 'easeInOut' } : undefined}
      />

      {/* 脚下涟漪：思考/回答时缓动 */}
      <motion.path
        d="M19 89.5Q26 85 33 89.5T47 89.5T61 89.5T75 89.5"
        stroke="#BDD8FC"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        animate={animateRipple}
        transition={animateRipple ? { duration: 3.6, repeat: Infinity, ease: 'easeInOut' } : undefined}
      />
      <path
        d="M31 94.5Q37 91 43 94.5T55 94.5T67 94.5"
        stroke="#4D83D6"
        strokeWidth="2.2"
        strokeLinecap="round"
        opacity="0.45"
        fill="none"
      />
    </svg>
  )
}
