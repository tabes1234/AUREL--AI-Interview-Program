import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface PageTransitionProps {
  children: ReactNode
  className?: string
}

/** A1：常规路由切换的淡入与轻微位移（纯 CSS 实现，挂载即播放） */
export function PageTransition({ children, className }: PageTransitionProps) {
  return <div className={cn('page-enter', className)}>{children}</div>
}

interface StaggerListProps {
  children: ReactNode
  className?: string
}

/** A2：有明确顺序的流程使用的横向滑入编排容器 */
export function StaggerList({ children, className }: StaggerListProps) {
  return <div className={cn('space-y-0', className)}>{children}</div>
}

interface StaggerItemProps {
  children: ReactNode
  className?: string
  /** 在列表中的序号（从 0 开始），用于递增入场延迟 */
  index?: number
}

/** A2 子项：以递增延迟滑入（纯 CSS animation-delay） */
export function StaggerItem({ children, className, index = 0 }: StaggerItemProps) {
  return (
    <div
      className={cn('card-enter', className)}
      style={index > 0 ? { animationDelay: `${Math.min(index, 6) * 0.08}s` } : undefined}
    >
      {children}
    </div>
  )
}
