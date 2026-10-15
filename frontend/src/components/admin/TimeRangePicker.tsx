import { CalendarRange, Check } from 'lucide-react'
import { useState } from 'react'

export interface TimeRangeValue {
  /** 起始日期 YYYY-MM-DD（UTC+8 语义） */
  start?: string
  /** 结束日期 YYYY-MM-DD（UTC+8 语义） */
  end?: string
  /** 预设档位标识（自定义时为 'custom'） */
  preset: '7d' | '30d' | '90d' | 'custom'
}

const PRESETS: { key: TimeRangeValue['preset']; label: string; days: number }[] = [
  { key: '7d', label: '最近 7 天', days: 7 },
  { key: '30d', label: '最近 30 天', days: 30 },
  { key: '90d', label: '最近 90 天', days: 90 },
]

function shiftDate(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - (days - 1))
  return d.toISOString().slice(0, 10)
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/** 统计周期选择：预设档位 + 自定义日期范围（统一 UTC+8 口径） */
export function TimeRangePicker({
  value,
  onChange,
}: {
  value: TimeRangeValue
  onChange: (next: TimeRangeValue) => void
}) {
  const [customOpen, setCustomOpen] = useState(false)
  const [draftStart, setDraftStart] = useState(value.start ?? shiftDate(30))
  const [draftEnd, setDraftEnd] = useState(value.end ?? today())

  const applyPreset = (preset: TimeRangeValue['preset'], days: number) => {
    setCustomOpen(false)
    onChange({ preset, start: shiftDate(days), end: today() })
  }

  const applyCustom = () => {
    if (!draftStart || !draftEnd || draftStart > draftEnd) return
    onChange({ preset: 'custom', start: draftStart, end: draftEnd })
    setCustomOpen(false)
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center rounded-full border border-line bg-white p-0.5 shadow-card" role="group" aria-label="统计周期">
        {PRESETS.map((preset) => {
          const active = value.preset === preset.key
          return (
            <button
              key={preset.key}
              type="button"
              onClick={() => applyPreset(preset.key, preset.days)}
              className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 text-xs font-medium transition ${
                active
                  ? 'bg-gradient-to-r from-brand-600 to-brand-500 text-white shadow-card'
                  : 'text-ink-soft hover:text-ink'
              }`}
            >
              {active && <Check className="h-3 w-3" aria-hidden="true" />}
              {preset.label}
            </button>
          )
        })}
        <button
          type="button"
          onClick={() => setCustomOpen((open) => !open)}
          className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 text-xs font-medium transition ${
            value.preset === 'custom'
              ? 'bg-gradient-to-r from-brand-600 to-brand-500 text-white shadow-card'
              : 'text-ink-soft hover:text-ink'
          }`}
        >
          <CalendarRange className="h-3 w-3" aria-hidden="true" />
          自定义
        </button>
      </div>

      {customOpen && (
        <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-white px-3 py-2 shadow-card">
          <label className="flex items-center gap-1.5 text-xs text-ink-soft">
            开始
            <input
              type="date"
              value={draftStart}
              max={draftEnd}
              onChange={(e) => setDraftStart(e.target.value)}
              className="rounded-lg border border-line bg-white px-2 py-1 text-xs text-ink outline-none focus:border-ripple"
            />
          </label>
          <span className="text-xs text-ink-soft">至</span>
          <label className="flex items-center gap-1.5 text-xs text-ink-soft">
            结束
            <input
              type="date"
              value={draftEnd}
              min={draftStart}
              max={today()}
              onChange={(e) => setDraftEnd(e.target.value)}
              className="rounded-lg border border-line bg-white px-2 py-1 text-xs text-ink outline-none focus:border-ripple"
            />
          </label>
          <button
            type="button"
            onClick={applyCustom}
            className="rounded-full bg-brand-600 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
            disabled={!draftStart || !draftEnd || draftStart > draftEnd}
          >
            应用
          </button>
        </div>
      )}
    </div>
  )
}

/* eslint-disable-next-line react-refresh/only-export-components */
export function defaultTimeRange(): TimeRangeValue {
  return { preset: '30d', start: shiftDate(30), end: today() }
}
