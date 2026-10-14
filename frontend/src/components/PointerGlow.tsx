import { useEffect, useRef } from 'react'

/**
 * 「海蓝微光」：指尖处一点若隐若现的海面反光。
 *
 * 设计要点：
 * - 主体仅约 48–72px，低透明度冰蓝/雾蓝，随页面用途分档（intensity），
 *   全站共用本组件，禁止各页面重复实现跟随光效
 * - pointermove 只记录目标坐标，位置经 rAF 轻缓动后写入 CSS 变量，
 *   不触发任何 React 组件树渲染；跟随系数 0.22，基本跟手但有呼吸感
 * - 滞后微光点（ambient 档专属）以更慢系数追踪，快速移动时自然带出
 *   一条极淡的短光痕，停止移动时两点贴合、光痕融入主体自然消散
 * - 鼠标停止约 0.9s 后微光淡出（CSS 过渡），移动时才重新点亮
 * - 仅在支持精确指针（pointer: fine）且未开启"减少动态效果"的设备激活；
 *   pointer-events: none、无 z-index（DOM 顺序位于正文之前），不拦截
 *   点击、不覆盖正文，触屏与降动效模式下完全不渲染动画
 */
export type PointerGlowIntensity = 'ambient' | 'soft' | 'deep' | 'faint' | 'whisper'

const TRAIL_ENABLED: Record<PointerGlowIntensity, boolean> = {
  ambient: true,
  soft: false,
  deep: false,
  faint: false,
  whisper: false,
}

export function PointerGlow({ intensity = 'whisper' }: { intensity?: PointerGlowIntensity }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!window.matchMedia('(pointer: fine)').matches) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const hasTrail = TRAIL_ENABLED[intensity]
    let raf = 0
    let targetX = window.innerWidth / 2
    let targetY = window.innerHeight / 3
    let x = targetX
    let y = targetY
    let trailX = targetX
    let trailY = targetY
    let lastMoveAt = 0
    let idle = true // 初始未移动，保持淡出状态，首次移动才点亮

    const tick = () => {
      x += (targetX - x) * 0.22
      y += (targetY - y) * 0.22
      el.style.setProperty('--glow-x', `${x}px`)
      el.style.setProperty('--glow-y', `${y}px`)

      if (hasTrail) {
        trailX += (x - trailX) * 0.07
        trailY += (y - trailY) * 0.07
        const dx = x - trailX
        const dy = y - trailY
        el.style.setProperty('--trail-x', `${dx}px`)
        el.style.setProperty('--trail-y', `${dy}px`)
        // 光痕透明度由两点距离自然驱动：移动越快越可见，停止即贴合归零
        const distance = Math.hypot(dx, dy)
        el.style.setProperty('--trail-o', String(Math.min(0.06, distance * 0.004)))
      }

      if (!idle && performance.now() - lastMoveAt > 900) {
        idle = true
        el.classList.add('pointer-glow--idle')
      }

      const settled =
        Math.abs(targetX - x) < 0.2 && Math.abs(targetY - y) < 0.2
      raf = settled && idle ? 0 : requestAnimationFrame(tick)
    }

    const onMove = (event: PointerEvent) => {
      targetX = event.clientX
      targetY = event.clientY
      lastMoveAt = performance.now()
      if (idle) {
        idle = false
        el.classList.remove('pointer-glow--idle')
      }
      if (!raf) raf = requestAnimationFrame(tick)
    }

    window.addEventListener('pointermove', onMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [intensity])

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className={`pointer-glow pointer-glow--idle pointer-glow--${intensity}`}
    />
  )
}
