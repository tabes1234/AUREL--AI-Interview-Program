import { useEffect, useState } from 'react'

/**
 * 长任务等待文案轮换。
 *
 * 规则（与进度真实性约束一致）：
 * - 仅在任务处于 loading/streaming 等待期轮换，且序列多于一条时才轮换；
 * - 轮换间隔较长（默认 7 秒），文案变化不代表任务进度增加；
 * - 失败/结束后立即停止轮换（active=false，展示第一条主文案）；
 * - prefers-reduced-motion 下不轮换（保持静态文案）；
 * - 不使用随机跳换，按序列循环。
 */
export function useRotatingCopy(
  sequence: string[],
  active: boolean,
  intervalMs = 7000,
): string {
  const [index, setIndex] = useState(0)

  const canRotate =
    active &&
    sequence.length > 1 &&
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches === false

  useEffect(() => {
    if (!canRotate) return
    const timer = setInterval(() => {
      setIndex((prev) => prev + 1)
    }, intervalMs)
    return () => clearInterval(timer)
  }, [canRotate, intervalMs])

  return canRotate
    ? sequence[index % sequence.length]
    : sequence[0]
}
