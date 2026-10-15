// 管理中心页面共享工具：数字/时间格式化、时间范围 hook。

import { useCallback, useState } from 'react'
import { defaultTimeRange, type TimeRangeValue } from '../../components/admin/TimeRangePicker'

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('zh-CN')
}

export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value} ms`
}

/** 数据库存的是 naive UTC；展示统一转为 UTC+8 */
export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(`${iso}${iso.length === 19 ? 'Z' : ''}`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return formatUtc(iso).slice(0, 10)
}

/** 各管理页独立持有的统计周期状态（默认最近 30 天） */
export function useAdminRange(): [TimeRangeValue, (next: TimeRangeValue) => void] {
  const [range, setRange] = useState<TimeRangeValue>(defaultTimeRange)
  const update = useCallback((next: TimeRangeValue) => setRange(next), [])
  return [range, update]
}

export function rangeParams(range: TimeRangeValue): { start?: string; end?: string } {
  return { start: range.start, end: range.end }
}
