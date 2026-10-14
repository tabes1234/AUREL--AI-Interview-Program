import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GullMascot } from './GullMascot'
import {
  XIAOU_CHAT_ROUTE,
  XIAOU_HOVER_DELAY_MS,
  XIAOU_LEAVE_DELAY_MS,
  XIAOU_TIPS,
} from '../lib/xiaouTips'
import { cn } from '../lib/cn'

/** 桌面精确指针设备判定：触屏无悬停能力，走「轻触出提示 → 再触进入」路径 */
function canFineHover(): boolean {
  return window.matchMedia('(hover: hover) and (pointer: fine)').matches
}

/**
 * 小鸥悬浮入口（全站共享组件；主页、观澜之意、澜讯与行舟工作区挂载，认证页不挂载）。
 * - 桌面：悬停 300ms 轻声提示，移入气泡保持显示，离开约 220ms 后自然收起；点击直达知途 AI 对话；
 * - 触屏：首次轻触显示提示，再次轻触进入；点按组件以外区域收起提示；
 * - 键盘：可 Tab 聚焦，Enter/Space 触发（与点击行为一致）。
 * 提示按序轮换，离开不重置回欢迎语；漂浮动画尊重 prefers-reduced-motion。
 */
export function XiaouCompanion() {
  const navigate = useNavigate()
  const [tipOpen, setTipOpen] = useState(false)
  const [tipIndex, setTipIndex] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const hoverTimer = useRef<number | undefined>(undefined)
  const leaveTimer = useRef<number | undefined>(undefined)

  const clearTimers = () => {
    window.clearTimeout(hoverTimer.current)
    window.clearTimeout(leaveTimer.current)
  }

  // 卸载时清理定时器，避免组件销毁后仍触发状态更新
  useEffect(() => clearTimers, [])

  /** 收起提示并推进轮换序号：下次展示下一条，且不重置回第一条欢迎语 */
  const closeTip = () => {
    setTipOpen(false)
    setTipIndex((i) => (i + 1) % XIAOU_TIPS.length)
  }

  const handleEnter = () => {
    clearTimers()
    if (!canFineHover()) return
    hoverTimer.current = window.setTimeout(() => setTipOpen(true), XIAOU_HOVER_DELAY_MS)
  }

  const handleLeave = () => {
    clearTimers()
    if (!canFineHover()) return
    leaveTimer.current = window.setTimeout(closeTip, XIAOU_LEAVE_DELAY_MS)
  }

  const handleActivate = () => {
    clearTimers()
    if (!canFineHover() && !tipOpen) {
      setTipOpen(true) // 触屏首次轻触：先给提示
      return
    }
    closeTip()
    navigate(XIAOU_CHAT_ROUTE)
  }

  // 提示展开期间，点按组件以外区域收起（主要服务触屏）
  useEffect(() => {
    if (!tipOpen) return undefined
    const onDocPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) closeTip()
    }
    document.addEventListener('pointerdown', onDocPointerDown)
    return () => document.removeEventListener('pointerdown', onDocPointerDown)
  }, [tipOpen])

  return (
    <div
      ref={rootRef}
      className="fixed bottom-3 right-3 z-40 p-3"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {/* 轻声提示气泡：右对齐向左展开，max-width 约束保证不超出视口 */}
      <div
        role="status"
        aria-hidden={!tipOpen}
        className={cn(
          'absolute bottom-full right-0 mb-2 w-max max-w-[min(280px,calc(100vw-2.5rem))] rounded-2xl border border-white/70 bg-white/80 px-4 py-3 text-left shadow-raised backdrop-blur-md transition-all duration-200 ease-out',
          tipOpen ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-1.5 opacity-0',
        )}
      >
        <div className="flex items-start gap-2.5">
          <GullMascot size={30} className="mt-0.5 shrink-0" />
          <p className="text-sm leading-relaxed text-ink">{XIAOU_TIPS[tipIndex]}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={handleActivate}
        aria-label="小鸥——AI 职业伙伴，点击进入知途对话"
        aria-expanded={tipOpen}
        className="flex h-16 w-16 items-center justify-center rounded-full border border-white/70 bg-white/75 shadow-raised backdrop-blur-md transition-[background-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:bg-white/90 hover:shadow-lg active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
      >
        {/* 漂浮动画作用于内层，避免与按钮自身的悬停位移变换叠加冲突 */}
        <span aria-hidden="true" className="xiaou-float pointer-events-none flex">
          <GullMascot size={46} status="idle" />
        </span>
      </button>
    </div>
  )
}
