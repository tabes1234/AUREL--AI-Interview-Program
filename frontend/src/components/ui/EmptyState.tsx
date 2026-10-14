import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center px-6 py-10 text-center', className)}>
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
        <Icon className="h-6 w-6 text-ink-soft" aria-hidden="true" />
      </div>
      <p className="mt-4 text-sm font-semibold text-ink-strong">{title}</p>
      <p className="mt-1 max-w-xs text-sm leading-relaxed text-ink-soft">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}
