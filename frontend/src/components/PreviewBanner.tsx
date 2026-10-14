import { Eye } from 'lucide-react'
import { cn } from '../lib/cn'

interface PreviewBannerProps {
  title: string
  description: string
  className?: string
}

/** 预览状态横幅：明确标注功能尚未接入，不伪装为已实现 */
export function PreviewBanner({ title, description, className }: PreviewBannerProps) {
  return (
    <div
      role="status"
      className={cn(
        'flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3',
        className,
      )}
    >
      <Eye className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-amber-800">{title}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-amber-700">{description}</p>
      </div>
    </div>
  )
}
