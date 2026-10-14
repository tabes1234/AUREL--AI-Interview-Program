import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type BadgeTone = 'brand' | 'accent' | 'neutral' | 'preview'

const toneClasses: Record<BadgeTone, string> = {
  brand: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  accent: 'bg-accent-50 text-accent-700 ring-accent/20',
  neutral: 'bg-slate-100 text-ink-soft ring-slate-300/50',
  preview: 'bg-amber-50 text-amber-700 ring-amber-600/20',
}

interface BadgeProps {
  tone?: BadgeTone
  icon?: ReactNode
  className?: string
  children: ReactNode
}

export function Badge({ tone = 'neutral', icon, className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        toneClasses[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
