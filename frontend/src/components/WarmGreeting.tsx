import { useEffect, useState } from 'react'
import { WARM_MESSAGES, WARM_MESSAGE_INTERVAL_MS } from '../lib/warmMessages'
import { cn } from '../lib/cn'

/** 整句淡出时长（毫秒），与 index.css 中 .warm-greeting-inner 的过渡时间保持一致 */
const FADE_OUT_MS = 480

/**
 * 主页暖心寄语：有序轮换的整句文案 + 字符波浪式轻柔入场。
 * - 屏幕阅读器读取整句（sr-only），逐字动画层 aria-hidden，避免逐字重复朗读；
 * - 固定最小高度（2em），长短句切换不引起上下跳动；
 * - 页面转入后台时暂停轮换；prefers-reduced-motion 下关闭逐字波动（见 index.css）。
 */
export function WarmGreeting() {
  const [index, setIndex] = useState(0)
  const [out, setOut] = useState(false)

  useEffect(() => {
    if (WARM_MESSAGES.length <= 1) return undefined
    let disposed = false
    let rotateTimer: number | undefined
    let swapTimer: number | undefined

    const scheduleNext = () => {
      rotateTimer = window.setTimeout(() => {
        if (disposed) return
        if (document.hidden) {
          scheduleNext() // 页面在后台：本轮不切换，继续等待
          return
        }
        setOut(true)
        swapTimer = window.setTimeout(() => {
          if (disposed) return
          setIndex((i) => (i + 1) % WARM_MESSAGES.length)
          setOut(false)
          scheduleNext()
        }, FADE_OUT_MS)
      }, WARM_MESSAGE_INTERVAL_MS)
    }

    scheduleNext()
    return () => {
      disposed = true
      window.clearTimeout(rotateTimer)
      window.clearTimeout(swapTimer)
    }
  }, [])

  const message = WARM_MESSAGES[index]

  return (
    <p
      className={cn(
        'warm-greeting mt-8 min-h-[2em] text-base font-light tracking-[0.06em] text-shallow/90 sm:text-lg',
        out && 'warm-greeting-out',
      )}
      aria-live="off"
    >
      <span className="sr-only">{message}</span>
      {/* key=index 使切换时逐字动画重新播放 */}
      <span aria-hidden="true" className="warm-greeting-inner" key={index}>
        {Array.from(message).map((ch, i) => (
          <span
            key={`${i}-${ch}`}
            className="warm-greeting-char"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            {ch}
          </span>
        ))}
      </span>
    </p>
  )
}
