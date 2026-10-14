import { cn } from '../../lib/cn'
import { copyForPhase, copySequence, type WaitScene } from '../../lib/waitingCopy'
import { formatElapsed, type AsyncTaskStatus } from './useAsyncTask'
import { AurelProgress } from './AurelProgress'
import { useRotatingCopy } from './useRotatingCopy'

/**
 * AUREL AI 长任务进度面板：用于生成面试题、深度分析、报告生成等较长任务。
 *
 * - 明确展示任务名称与当前真实状态对应的等待文案；
 * - 大号流光条（不确定进度模式，不虚构百分比）；
 * - 显示真实已耗时；支持成功定格、失败/取消/超时提示与重试入口；
 * - 面板不阻塞页面交互（无遮罩、pointer-events 正常）。
 */

export interface AurelTaskStatusProps {
  /** 任务名称，如「生成面试题集」。 */
  title: string
  scene: WaitScene
  status: AsyncTaskStatus
  error?: string | null
  elapsedMs?: number
  onRetry?: () => void
  onCancel?: () => void
  className?: string
}

const STATUS_BADGE: Partial<Record<AsyncTaskStatus, { text: string; className: string }>> = {
  preparing: { text: '准备中', className: 'bg-shallow/70 text-brand-700' },
  loading: { text: '进行中', className: 'bg-shallow/70 text-brand-700' },
  streaming: { text: '生成中', className: 'bg-shallow/70 text-brand-700' },
  success: { text: '已完成', className: 'bg-mist text-brand-700' },
  error: { text: '失败', className: 'bg-rose-50 text-rose-600' },
  cancelled: { text: '已取消', className: 'bg-slate-100 text-ink-soft' },
  timeout: { text: '超时', className: 'bg-rose-50 text-rose-600' },
}

export function AurelTaskStatus({
  title,
  scene,
  status,
  error = null,
  elapsedMs = 0,
  onRetry,
  onCancel,
  className,
}: AurelTaskStatusProps) {
  const running = status === 'preparing' || status === 'loading' || status === 'streaming'
  const sequence = copySequence(scene)
  const waiting = useRotatingCopy(sequence, status === 'loading')

  const failed = status === 'error' || status === 'cancelled' || status === 'timeout'
  const badge = STATUS_BADGE[status]

  const copy = failed
    ? (error ?? (status === 'timeout' ? '请求超时：服务长时间未回应，请稍后重试' : '任务已取消'))
    : status === 'success'
      ? '已经整理完成，内容就在下方。'
      : copyForPhase(scene, status === 'preparing' ? 'preparing' : status === 'streaming' ? 'streaming' : 'loading')

  return (
    <section
      aria-live="polite"
      className={cn(
        'rounded-2xl border border-line/80 bg-white/75 px-5 py-4 shadow-[0_10px_28px_rgba(28,47,74,0.07)]',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <h3 className="text-sm font-semibold text-ink-strong">{title}</h3>
          {badge ? (
            <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', badge.className)}>
              {badge.text}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {running && elapsedMs > 0 ? (
            <span className="text-xs tabular-nums text-ink-soft/80">已耗时 {formatElapsed(elapsedMs)}</span>
          ) : null}
          {running && onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full px-2.5 py-1 text-xs text-ink-soft transition hover:bg-shallow/60 hover:text-brand-700"
            >
              取消
            </button>
          ) : null}
          {failed && onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-full border border-line bg-white/80 px-3.5 py-1 text-xs font-medium text-brand-700 transition hover:border-ripple hover:bg-shallow/60"
            >
              重试
            </button>
          ) : null}
        </div>
      </div>

      <p className={cn('mt-2 text-sm leading-relaxed', failed ? 'text-rose-600' : 'text-ink-soft')}>
        {waiting && status === 'loading' ? waiting : copy}
      </p>

      <AurelProgress
        className="mt-3"
        size="md"
        status={
          failed
            ? status === 'cancelled'
              ? 'cancelled'
              : status === 'timeout'
                ? 'timeout'
                : 'error'
            : status === 'success'
              ? 'success'
              : 'loading'
        }
      />
    </section>
  )
}
