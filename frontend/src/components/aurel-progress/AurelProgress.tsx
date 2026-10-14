import { cn } from '../../lib/cn'

/**
 * AUREL 海洋流光进度条。
 *
 * - value 为 null（默认）：不确定进度——优雅的无限循环流光，
 *   仅表示任务正在进行，不虚构百分比。
 * - value 为 0-100：确定进度——只在存在可信进度来源时由调用方传入。
 * - status 决定视觉语义：loading/streaming 流光流动，success 静止定格，
 *   error/cancelled/timeout 静止并转为柔和警示色。
 * - 轨道与填充均为纯 CSS 动画，尊重 prefers-reduced-motion（全局降级）。
 */

export type AurelProgressStatus =
  | 'loading'
  | 'streaming'
  | 'success'
  | 'error'
  | 'cancelled'
  | 'timeout'

export interface AurelProgressProps {
  /** 真实进度百分比（0-100）；不传则展示不确定流光。 */
  value?: number | null
  status?: AurelProgressStatus
  /** xs=3px（按钮内嵌）sm=5px md=6px */
  size?: 'xs' | 'sm' | 'md'
  className?: string
}

const SIZE_CLASS: Record<NonNullable<AurelProgressProps['size']>, string> = {
  xs: 'h-[3px]',
  sm: 'h-[5px]',
  md: 'h-[6px]',
}

const SETTLED_STATUS: AurelProgressStatus[] = ['success', 'error', 'cancelled', 'timeout']

export function AurelProgress({
  value = null,
  status = 'loading',
  size = 'sm',
  className,
}: AurelProgressProps) {
  const settled = SETTLED_STATUS.includes(status)
  const determinate = value != null && Number.isFinite(value)
  const clamped = determinate ? Math.min(100, Math.max(0, value as number)) : null

  const toneClass =
    status === 'error' || status === 'cancelled' || status === 'timeout'
      ? 'aurel-progress-fill-error'
      : 'aurel-progress-fill'

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clamped ?? undefined}
      aria-hidden={settled && status !== 'success'}
      className={cn(
        'aurel-progress-track relative w-full overflow-hidden rounded-full',
        SIZE_CLASS[size],
        className,
      )}
    >
      <div
        className={cn('aurel-progress-fill', toneClass)}
        style={
          determinate
            ? { width: `${clamped}%` }
            : undefined
        }
        data-mode={determinate ? 'determinate' : 'indeterminate'}
        data-status={status}
      >
        {/* 前沿高光：流光推进端的一抹柔和亮斑 */}
        <span className="aurel-progress-tip" aria-hidden />
      </div>
    </div>
  )
}
