import { RefreshCw, WifiOff } from 'lucide-react'
import { useHealth } from '../hooks/useHealth'
import { cn } from '../lib/cn'

interface ServiceStatusProps {
  className?: string
}

/** 服务连接失败时警示（正常时静默，不打扰界面） */
export function ServiceStatus({ className }: ServiceStatusProps) {
  const { status, error, refresh } = useHealth()

  if (status === 'online') {
    return null
  }

  if (status === 'loading') {
    return null
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full bg-red-50 px-3 py-1.5 text-xs text-red-700 ring-1 ring-inset ring-red-600/20',
        className,
      )}
    >
      <WifiOff className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>无法连接后端服务（{error ?? '未知错误'}）</span>
      <button
        type="button"
        onClick={refresh}
        className="ml-1 inline-flex items-center gap-1 rounded px-1 font-medium text-brand-600 underline-offset-2 hover:underline"
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        重试
      </button>
    </span>
  )
}
