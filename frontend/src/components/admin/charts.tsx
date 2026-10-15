// 轻量 SVG 图表：无第三方依赖、支持悬停读数与空数据状态。
// 数据来自管理中心真实接口；无数据时展示「暂无数据」，绝不填充随机值。

import { useMemo, useState } from 'react'

export interface SeriesDef {
  key: string
  label: string
  color: string
}

function niceMax(max: number): number {
  if (max <= 5) return 5
  const magnitude = Math.pow(10, Math.floor(Math.log10(max)))
  const normalized = max / magnitude
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return step * magnitude
}

function shortDay(day: string): string {
  return day.slice(5) // MM-DD
}

interface LineChartProps {
  days: string[]
  series: { def: SeriesDef; values: (number | null)[] }[]
  height?: number
  formatValue?: (value: number) => string
  emptyText?: string
}

/** 折线趋势图：悬停显示各序列当日数值 */
export function LineChart({ days, series, height = 200, formatValue = (v) => String(v), emptyText = '暂无数据' }: LineChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const width = 640
  const padding = { top: 12, right: 12, bottom: 24, left: 40 }

  const flat = series.flatMap((s) => s.values.filter((v): v is number => v !== null))
  const maxValue = niceMax(Math.max(1, ...flat))

  const hasData = flat.length > 0
  const points = useMemo(() => {
    if (!hasData || days.length === 0) return []
    return series.map((s) => ({
      ...s,
      coords: s.values.map((v, i) => {
        const x = padding.left + (i / Math.max(1, days.length - 1)) * (width - padding.left - padding.right)
        const y = height - padding.bottom - ((v ?? 0) / maxValue) * (height - padding.top - padding.bottom)
        return { x, y, value: v }
      }),
    }))
  }, [series, days.length, hasData, height, maxValue, padding.bottom, padding.left, padding.right, padding.top])

  if (!hasData) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-line text-sm text-ink-soft">
        {emptyText}
      </div>
    )
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full select-none"
        role="img"
        aria-label="趋势图"
        onMouseLeave={() => setHoverIndex(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const ratio = (e.clientX - rect.left) / rect.width
          const x = ratio * width
          const idx = Math.round(
            ((x - padding.left) / Math.max(1, width - padding.left - padding.right)) * (days.length - 1),
          )
          setHoverIndex(Math.max(0, Math.min(days.length - 1, idx)))
        }}
      >
        {/* 水平网格线 */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = height - padding.bottom - ratio * (height - padding.top - padding.bottom)
          return (
            <g key={ratio}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#DCE8F7" strokeWidth="1" />
              <text x={padding.left - 6} y={y + 3} textAnchor="end" className="fill-[#7185A2]" fontSize="9">
                {formatValue(Math.round(maxValue * ratio))}
              </text>
            </g>
          )
        })}
        {/* X 轴日期（最多 8 个刻度） */}
        {days.map((day, i) => {
          const tickEvery = Math.max(1, Math.ceil(days.length / 8))
          if (i % tickEvery !== 0 && i !== days.length - 1) return null
          const x = padding.left + (i / Math.max(1, days.length - 1)) * (width - padding.left - padding.right)
          return (
            <text key={day} x={x} y={height - 6} textAnchor="middle" className="fill-[#7185A2]" fontSize="9">
              {shortDay(day)}
            </text>
          )
        })}
        {/* 悬停参考线 */}
        {hoverIndex !== null && (
          <line
            x1={padding.left + (hoverIndex / Math.max(1, days.length - 1)) * (width - padding.left - padding.right)}
            x2={padding.left + (hoverIndex / Math.max(1, days.length - 1)) * (width - padding.left - padding.right)}
            y1={padding.top}
            y2={height - padding.bottom}
            stroke="#BDD8FC"
            strokeDasharray="3 3"
          />
        )}
        {/* 折线 */}
        {points.map((line) => (
          <g key={line.def.key}>
            <polyline
              fill="none"
              stroke={line.def.color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              points={line.coords.map((c) => `${c.x},${c.y}`).join(' ')}
            />
            {hoverIndex !== null && line.coords[hoverIndex] && (
              <circle
                cx={line.coords[hoverIndex].x}
                cy={line.coords[hoverIndex].y}
                r="3.5"
                fill="white"
                stroke={line.def.color}
                strokeWidth="2"
              />
            )}
          </g>
        ))}
      </svg>
      {/* 图例 + 悬停读数 */}
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-ink-soft">
        <div className="flex flex-wrap gap-3">
          {series.map((s) => (
            <span key={s.def.key} className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.def.color }} aria-hidden="true" />
              {s.def.label}
            </span>
          ))}
        </div>
        {hoverIndex !== null && (
          <span className="text-ink">
            {days[hoverIndex]}
            {series.map((s) =>
              s.values[hoverIndex] === null || s.values[hoverIndex] === undefined ? null : (
                <span key={s.def.key}> · {s.def.label} {formatValue(s.values[hoverIndex] as number)}</span>
              ),
            )}
          </span>
        )}
      </div>
    </div>
  )
}

interface BarsChartProps {
  items: { label: string; value: number; sub?: string; color?: string }[]
  emptyText?: string
  formatValue?: (value: number) => string
}

/** 水平柱状对比图（模块使用量排行等） */
export function BarsChart({ items, emptyText = '暂无数据', formatValue = (v) => String(v) }: BarsChartProps) {
  const meaningful = items.filter((item) => item.value > 0)
  if (meaningful.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-line text-sm text-ink-soft">
        {emptyText}
      </div>
    )
  }
  const max = Math.max(...meaningful.map((item) => item.value))
  return (
    <div className="space-y-2.5">
      {meaningful.map((item) => (
        <div key={item.label} className="flex items-center gap-3 text-xs">
          <span className="w-24 shrink-0 truncate text-right text-ink-soft" title={item.label}>
            {item.label}
          </span>
          <div className="h-4 flex-1 overflow-hidden rounded-full bg-[#F0F7FF]">
            <div
              className="flex h-full items-center justify-end rounded-full bg-gradient-to-r from-brand-400 to-brand-600 px-1.5 transition-all duration-500"
              style={{ width: `${Math.max(8, (item.value / max) * 100)}%` }}
            >
              <span className="text-[10px] font-medium text-white">{formatValue(item.value)}</span>
            </div>
          </div>
          {item.sub && <span className="w-16 shrink-0 text-ink-soft">{item.sub}</span>}
        </div>
      ))}
    </div>
  )
}
