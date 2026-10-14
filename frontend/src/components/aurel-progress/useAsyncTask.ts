import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 观澜统一异步任务状态机。
 *
 * 状态生命周期：idle → preparing → loading（→ streaming）→ success / error / cancelled / timeout。
 * - preparing：正在准备请求（真实存在的同步准备段，此时不显示「AI 正在思考」类文案）。
 * - loading：请求已真实发出，等待结果。
 * - streaming：任务方在收到真实流式内容后手动推进。
 * - 终态（success/error/cancelled/timeout）会立即结束进度动画与计时。
 *
 * 防重入：任务运行中再次 run() 直接拒绝（返回 undefined），避免重复请求。
 * 取消：cancel() 触发 AbortController，任务方应在中断后停止后续处理。
 * 超时：可选 timeoutMs，到点中止并进入 timeout 终态。
 * 计时：elapsedMs 每 500ms 刷新，用于展示真实已等待时长（不虚构剩余时间）。
 */

export type AsyncTaskStatus =
  | 'idle'
  | 'preparing'
  | 'loading'
  | 'streaming'
  | 'success'
  | 'error'
  | 'cancelled'
  | 'timeout'

export const TERMINAL_STATUSES: readonly AsyncTaskStatus[] = [
  'idle',
  'success',
  'error',
  'cancelled',
  'timeout',
]

export function isTerminal(status: AsyncTaskStatus): boolean {
  return TERMINAL_STATUSES.includes(status)
}

/** 把已等待毫秒格式化为「x.x 秒 / m 分 s 秒」。 */
export function formatElapsed(ms: number): string {
  if (ms < 10000) return `${(ms / 1000).toFixed(1)} 秒`
  const total = Math.floor(ms / 1000)
  if (total < 60) return `${total} 秒`
  return `${Math.floor(total / 60)} 分 ${total % 60} 秒`
}

export interface AsyncTaskRunOptions {
  /** 覆盖实例级超时（毫秒）。 */
  timeoutMs?: number
}

export interface UseAsyncTaskOptions {
  /** 默认超时毫秒数；不传则不限时（沿用后端/浏览器默认行为）。 */
  timeoutMs?: number
  /** 状态进入终态时的回调（error/cancelled/timeout/success 都会触发）。 */
  onSettled?: (status: AsyncTaskStatus, error: string | null) => void
  /** 开发诊断：任务结束时输出耗时到 console.debug（不含敏感信息）。 */
  debugLabel?: string
}

export interface UseAsyncTaskReturn {
  status: AsyncTaskStatus
  error: string | null
  elapsedMs: number
  /** 任务是否处于运行中（preparing/loading/streaming）。 */
  running: boolean
  /** 执行任务。运行中调用会被拒绝并返回 undefined。 */
  run: <T>(
    task: (signal: AbortSignal, helpers: { markStreaming: () => void }) => Promise<T>,
    options?: AsyncTaskRunOptions,
  ) => Promise<T | undefined>
  /** 手动推进到 streaming（仅流式任务使用）。 */
  markStreaming: () => void
  cancel: () => void
  reset: () => void
}

export function useAsyncTask(options: UseAsyncTaskOptions = {}): UseAsyncTaskReturn {
  const { timeoutMs, onSettled, debugLabel } = options
  const [status, setStatus] = useState<AsyncTaskStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [elapsedMs, setElapsedMs] = useState(0)

  const controllerRef = useRef<AbortController | null>(null)
  const startedAtRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const onSettledRef = useRef(onSettled)

  useEffect(() => {
    onSettledRef.current = onSettled
  }, [onSettled])

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      controllerRef.current?.abort()
      clearTimers()
    }
  }, [clearTimers])

  const settle = useCallback(
    (next: AsyncTaskStatus, message: string | null) => {
      if (!mountedRef.current) return
      clearTimers()
      controllerRef.current = null
      setStatus(next)
      setError(message)
      onSettledRef.current?.(next, message)
    },
    [clearTimers],
  )

  const markStreaming = useCallback(() => {
    if (!mountedRef.current) return
    setStatus((prev) => (prev === 'loading' || prev === 'preparing' ? 'streaming' : prev))
  }, [])

  const run = useCallback(
    async <T,>(
      task: (signal: AbortSignal, helpers: { markStreaming: () => void }) => Promise<T>,
      runOptions?: AsyncTaskRunOptions,
    ): Promise<T | undefined> => {
      if (controllerRef.current) {
        // 防重入：上一个任务尚未结束，拒绝重复触发
        return undefined
      }
      const controller = new AbortController()
      controllerRef.current = controller
      startedAtRef.current = performance.now()
      setElapsedMs(0)
      setError(null)
      // preparing：真实存在的同步准备段（创建控制器/启动计时）。
      // 随后请求立即发出，批处理后界面通常直接呈现 loading（场景文案）。
      setStatus('preparing')

      // 真实计时器：0.5s 粒度展示已等待时长
      timerRef.current = setInterval(() => {
        if (mountedRef.current) {
          setElapsedMs(performance.now() - startedAtRef.current)
        }
      }, 500)

      const effectiveTimeout = runOptions?.timeoutMs ?? timeoutMs
      if (effectiveTimeout && effectiveTimeout > 0) {
        timeoutRef.current = setTimeout(() => {
          if (controllerRef.current === controller) {
            controller.abort()
          }
        }, effectiveTimeout)
      }

      const startedAt = startedAtRef.current
      // 请求即将真实发出：进入 loading，展示与任务绑定的场景等待文案
      setStatus('loading')
      try {
        const result = await task(controller.signal, { markStreaming })
        if (controller.signal.aborted) {
          // 任务方未正确抛出取消异常时兜底
          settle('cancelled', null)
          return undefined
        }
        if (mountedRef.current && debugLabel) {
          console.debug(`[aurel] ${debugLabel} 完成，耗时 ${Math.round(performance.now() - startedAt)}ms`)
        }
        settle('success', null)
        return result
      } catch (err) {
        const elapsed = performance.now() - startedAt
        if (controller.signal.aborted) {
          // 超时 vs 用户取消：超时由我们主动 abort 且此时已过时限
          if (effectiveTimeout && effectiveTimeout > 0 && elapsed >= effectiveTimeout - 50) {
            settle('timeout', '请求超时：服务长时间未回应，请稍后重试')
          } else {
            settle('cancelled', null)
          }
          return undefined
        }
        const message = err instanceof Error ? err.message : '操作失败，请稍后重试'
        if (mountedRef.current && debugLabel) {
          console.debug(`[aurel] ${debugLabel} 失败（${Math.round(elapsed)}ms）：${message}`)
        }
        settle('error', message)
        return undefined
      }
    },
    [debugLabel, markStreaming, settle, timeoutMs],
  )

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
  }, [])

  const reset = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    clearTimers()
    setStatus('idle')
    setError(null)
    setElapsedMs(0)
  }, [clearTimers])

  return {
    status,
    error,
    elapsedMs,
    running: status === 'preparing' || status === 'loading' || status === 'streaming',
    run,
    markStreaming,
    cancel,
    reset,
  }
}
