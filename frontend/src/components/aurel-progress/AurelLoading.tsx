import { cn } from '../../lib/cn'
import { copyForPhase, copySequence, type WaitScene } from '../../lib/waitingCopy'
import { formatElapsed } from './useAsyncTask'
import { AurelProgress, type AurelProgressStatus } from './AurelProgress'
import { useRotatingCopy } from './useRotatingCopy'

/**
 * AUREL 统一加载状态容器：流光进度条 + 与真实任务绑定的等待文案 + 可选已耗时。
 *
 * - 局部内容加载与 AI 等待共用；失败时停止等待文案、展示真实错误与重试入口。
 * - phase='preparing' 时使用「准备请求」文案，不声称 AI 已在思考。
 * - elapsed>0 时显示真实已等待时长（不虚构剩余时间）。
 */

export interface AurelLoadingProps {
  scene: WaitScene
  phase?: 'preparing' | 'loading' | 'streaming'
  /** 终态：成功展示定格流光，失败/取消/超时展示错误与重试。 */
  status?: AurelProgressStatus
  error?: string | null
  onRetry?: () => void
  /** 显示真实已等待时长（运行中计时）。 */
  elapsedMs?: number
  size?: 'sm' | 'md'
  className?: string
  /** 文案与进度条的排布方向。 */
  layout?: 'column' | 'row'
}

export function AurelLoading({
  scene,
  phase = 'loading',
  status,
  error = null,
  onRetry,
  elapsedMs = 0,
  size = 'sm',
  className,
  layout = 'column',
}: AurelLoadingProps) {
  const running = !status || status === 'loading' || status === 'streaming'
  const sequence = copySequence(scene)
  const waiting = useRotatingCopy(sequence, running && phase === 'loading')

  const copy =
    error != null
      ? error
      : status === 'success'
        ? null
        : phase === 'preparing'
          ? copyForPhase(scene, 'preparing')
          : phase === 'streaming'
            ? copyForPhase(scene, 'streaming')
            : waiting

  const failed = error != null || status === 'error' || status === 'cancelled' || status === 'timeout'

  return (
    <div className={cn('w-full', className)}>
      <div
        className={cn(
          'flex gap-3',
          layout === 'column' ? 'flex-col' : 'flex-col-reverse sm:flex-row sm:items-center sm:justify-between',
        )}
      >
        <p
          className={cn(
            'text-sm leading-relaxed',
            failed ? 'text-rose-600' : 'text-ink-soft',
          )}
        >
          {copy}
        </p>
        {elapsedMs > 0 && running ? (
          <span className="shrink-0 text-xs tabular-nums text-ink-soft/80">
            已等待 {formatElapsed(elapsedMs)}
          </span>
        ) : null}
      </div>
      <AurelProgress
        className="mt-2.5"
        size={size}
        status={failed ? (status === 'cancelled' ? 'cancelled' : status === 'timeout' ? 'timeout' : 'error') : status}
      />
      {failed && onRetry ? (
        <div className="mt-2.5">
          <button
            type="button"
            onClick={onRetry}
            className="rounded-full border border-line bg-white/80 px-4 py-1.5 text-xs font-medium text-brand-700 transition hover:border-ripple hover:bg-shallow/60"
          >
            重试
          </button>
        </div>
      ) : null}
    </div>
  )
}
