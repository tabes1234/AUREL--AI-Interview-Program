import { ArrowRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'

/**
 * Editorial 编辑式排版原语。
 *
 * 目标：让页面像一本排好版的杂志，而不是等宽卡片铺成的后台。
 * 原则：开放式布局、细线与留白划分区域、大小与粗细建立层级；
 * 仅对话框 / 表单等确需边界的内容使用面板。
 */

/** 页首：眉题 + 大标题 + 副题 + 右侧动作。不包任何卡片。 */
export function PageHeading({
  kicker,
  title,
  subtitle,
  actions,
  className,
}: {
  kicker?: string
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <header className={cn('relative', className)}>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          {kicker ? (
            <p className="text-xs font-semibold tracking-[0.28em] text-brand-600/85">{kicker}</p>
          ) : null}
          <h1 className="mt-2 text-4xl font-bold leading-tight tracking-tight text-ink-strong sm:text-[2.75rem]">
            {title}
          </h1>
          {subtitle ? (
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-ink">{subtitle}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-col items-start gap-3 sm:items-end">{actions}</div> : null}
      </div>
      {/* 标题区下的极淡渐隐细线：编辑式章节起笔 */}
      <div
        aria-hidden="true"
        className="mt-8 h-px bg-gradient-to-r from-ripple/70 via-line to-transparent"
      />
    </header>
  )
}

/** 章节标题：编号 + 标题 + 向右渐隐细线，可带说明与动作。 */
export function SectionHead({
  title,
  note,
  action,
  className,
}: {
  title: ReactNode
  note?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-end justify-between gap-4', className)}>
      <div className="min-w-0">
        <div className="flex items-baseline gap-3">
          <h2 className="text-xl font-bold tracking-tight text-ink-strong">{title}</h2>
          {/* 细线向右渐隐，把视线送回正文 */}
          <span
            aria-hidden="true"
            className="hidden h-px w-16 self-center bg-gradient-to-r from-ripple/60 to-transparent sm:block"
          />
        </div>
        {note ? <p className="mt-1 text-sm text-ink-soft">{note}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

/** 开放式功能条目：细线分隔的导航行，无卡片边框。整行可点。 */
export function EntryRow({
  to,
  icon: Icon,
  title,
  description,
  meta,
  onClick,
}: {
  to?: string
  icon: LucideIcon
  title: ReactNode
  description?: ReactNode
  meta?: ReactNode
  onClick?: () => void
}) {
  const inner = (
    <>
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-mist text-brand-700 transition-colors group-hover:bg-shallow group-hover:text-brand-600">
        <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-ink-strong">{title}</span>
          {meta}
        </span>
        {description ? (
          <span className="mt-0.5 block truncate text-sm leading-relaxed text-ink-soft">
            {description}
          </span>
        ) : null}
      </span>
      <ArrowRight
        className="mt-1 h-4 w-4 shrink-0 text-ink-soft/50 transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-brand-600"
        aria-hidden="true"
      />
    </>
  )
  const classes =
    'group -mx-3 flex items-start gap-4 rounded-lg border-b border-line/70 px-3 py-4 text-left transition-colors duration-200 last:border-b-0 hover:bg-white/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40'
  if (to) {
    return (
      <Link to={to} onClick={onClick} className={classes}>
        {inner}
      </Link>
    )
  }
  return (
    <button type="button" onClick={onClick} className={cn(classes, 'w-[calc(100%+1.5rem)]')}>
      {inner}
    </button>
  )
}

/** 连续统计带：大数字 + 标签，细线分隔，无边框无卡片。 */
export function StatStrip({
  items,
  className,
}: {
  items: { label: ReactNode; value: ReactNode; hint?: ReactNode }[]
  className?: string
}) {
  return (
    <dl
      className={cn(
        'grid grid-cols-2 gap-y-6 sm:grid-cols-4 sm:divide-x sm:divide-line/80',
        className,
      )}
    >
      {items.map((item, index) => (
        <div key={index} className={cn('min-w-0', index > 0 && 'sm:pl-6')}>
          <dd className="text-3xl font-bold leading-none tracking-tight text-ink-strong">
            {item.value}
          </dd>
          <dt className="mt-2 text-sm font-medium text-ink">{item.label}</dt>
          {item.hint ? <p className="mt-0.5 text-xs text-ink-soft">{item.hint}</p> : null}
        </div>
      ))}
    </dl>
  )
}

/** 纵向时间线：圆点 + 贯穿细线，开放式行内容。 */
export function TimelineList({ children, className }: { children: ReactNode; className?: string }) {
  return <ol className={cn('relative', className)}>{children}</ol>
}

export function TimelineRow({
  title,
  meta,
  action,
  tone = 'idle',
  children,
  last = false,
}: {
  title: ReactNode
  meta?: ReactNode
  action?: ReactNode
  /** idle=灰蓝（进行中/未完） done=主蓝（完成） accent=清亮蓝 warn=琥珀 */
  tone?: 'idle' | 'done' | 'accent' | 'warn'
  children?: ReactNode
  last?: boolean
}) {
  const dotColor =
    tone === 'done'
      ? 'border-brand-600 bg-white'
      : tone === 'accent'
        ? 'border-accent bg-white'
        : tone === 'warn'
          ? 'border-amber-500 bg-white'
          : 'border-ink-soft/40 bg-white'
  return (
    <li className="relative flex gap-4 pb-5 last:pb-0">
      {/* 贯穿细线：最后一行不画 */}
      {!last ? (
        <span
          aria-hidden="true"
          className="absolute bottom-0 left-[5px] top-4 w-px bg-line"
        />
      ) : null}
      <span
        aria-hidden="true"
        className={cn('relative mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2', dotColor)}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[15px] font-semibold text-ink-strong">{title}</p>
          {action ? <div className="shrink-0">{action}</div> : null}
        </div>
        {meta ? <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">{meta}</p> : null}
        {children}
      </div>
    </li>
  )
}

/** 安静文字链接：hover 才出现下划线，用于行内导航。 */
export function QuietLink({
  to,
  children,
  className,
}: {
  to: string
  children: ReactNode
  className?: string
}) {
  return (
    <Link
      to={to}
      className={cn(
        'text-sm font-medium text-ink-soft underline-offset-4 transition-colors hover:text-brand-600 hover:underline hover:decoration-brand-600/40',
        className,
      )}
    >
      {children}
    </Link>
  )
}
