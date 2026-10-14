import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  /** 可交互卡片：悬停时轻微上移、阴影加深、边框略微清晰 */
  interactive?: boolean
}

export function Card({ className, interactive = false, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-line bg-white shadow-card',
        interactive &&
          'transition-all duration-200 hover:-translate-y-1 hover:border-ripple/80 hover:shadow-raised',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
}

export function CardHeader({ title, description, action, className, ...rest }: CardHeaderProps) {
  return (
    <div
      className={cn('flex items-start justify-between gap-4 px-6 pb-4 pt-5', className)}
      {...rest}
    >
      <div>
        <h2 className="text-base font-semibold text-ink-strong">{title}</h2>
        {description ? <p className="mt-1 text-sm text-ink-soft">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

export function CardBody({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-6 pb-6', className)} {...rest}>
      {children}
    </div>
  )
}
