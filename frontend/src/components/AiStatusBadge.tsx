import { Sparkles } from 'lucide-react'
import { useAiStatus } from '../hooks/useAiStatus'
import { cn } from '../lib/cn'

interface AiStatusBadgeProps {
  className?: string
}

/** AI 未配置时如实警示（已配置时静默，不打扰界面） */
export function AiStatusBadge({ className }: AiStatusBadgeProps) {
  const { loading, data, error } = useAiStatus()

  if (loading) {
    return null
  }

  if (data?.configured) {
    return null
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-xs text-amber-700 ring-1 ring-inset ring-amber-600/20',
        className,
      )}
      title={error ?? data?.message ?? ''}
    >
      <Sparkles className="h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden="true" />
      AI 未配置（模型调用不可用）
    </span>
  )
}
