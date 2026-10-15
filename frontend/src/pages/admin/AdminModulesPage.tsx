import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { LineChart } from '../../components/admin/charts'
import { TimeRangePicker } from '../../components/admin/TimeRangePicker'
import { AurelLoading } from '../../components/aurel-progress/AurelLoading'
import { useAsyncTask } from '../../components/aurel-progress/useAsyncTask'
import type { AdminModulesResponse } from '../../types'
import { formatNumber, rangeParams, useAdminRange } from './shared'

/** 功能分析：页面访问与真实业务操作分开统计，可查看单模块按日趋势 */
export default function AdminModulesPage() {
  const [range, setRange] = useAdminRange()
  const [data, setData] = useState<AdminModulesResponse | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const task = useAsyncTask({ debugLabel: 'admin-modules' })

  const load = useCallback(() => {
    task.run(async () => {
      const result = await api.adminModules(rangeParams(range))
      setData(result)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range])

  useEffect(() => {
    load()
  }, [load])

  if (task.running && !data) {
    return (
      <div className="flex justify-center py-14">
        <AurelLoading scene="common.page" phase={task.status === 'preparing' ? 'preparing' : 'loading'} elapsedMs={task.elapsedMs} size="md" />
      </div>
    )
  }

  if (task.status === 'error') {
    return (
      <div className="flex justify-center py-12">
        <AurelLoading scene="common.page" status="error" error={task.error} onRetry={load} size="md" />
      </div>
    )
  }

  if (!data) return null

  const selectedModule = data.items.find((item) => item.module === selected) ?? null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">功能分析</h1>
          <p className="mt-1 text-xs text-ink-soft">
            统计窗口 {data.range.start} ~ {data.range.end} · {data.timezone} · {data.note}
          </p>
        </div>
        <TimeRangePicker value={range} onChange={setRange} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-line bg-white shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead>
              <tr className="border-b border-line bg-brand-pale/40 text-ink-soft">
                <th className="px-4 py-2.5 font-medium">功能模块</th>
                <th className="px-3 py-2.5 text-right font-medium">页面访问</th>
                <th className="px-3 py-2.5 text-right font-medium">操作成功</th>
                <th className="px-3 py-2.5 text-right font-medium">操作失败</th>
                <th className="px-3 py-2.5 text-right font-medium">使用用户</th>
                <th className="px-3 py-2.5 text-right font-medium">最近使用</th>
                <th className="px-4 py-2.5 text-right font-medium">趋势</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => {
                const hasData = item.page_views + item.actions > 0
                return (
                  <tr
                    key={item.module}
                    className={`border-b border-line/50 last:border-0 ${selected === item.module ? 'bg-brand-pale/40' : 'hover:bg-brand-pale/20'}`}
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-medium text-ink">{item.label}</span>
                      {!hasData && <span className="ml-2 rounded-full bg-brand-pale px-1.5 py-0.5 text-[10px] text-ink-soft">窗口内暂无记录</span>}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(item.page_views)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(item.action_success)}</td>
                    <td className={`px-3 py-2.5 text-right tabular-nums ${item.action_errors > 0 ? 'text-[#A3543F]' : ''}`}>
                      {item.action_errors > 0 ? formatNumber(item.action_errors) : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(item.users)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-ink-soft">{item.last_used ? item.last_used.slice(5, 16).replace('T', ' ') : '—'}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={() => setSelected(selected === item.module ? null : item.module)}
                        className="rounded-full border border-line px-2.5 py-1 text-[11px] text-ink-soft transition hover:border-ripple hover:text-brand-700"
                      >
                        {selected === item.module ? '收起' : '查看'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selectedModule && (
        <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
          <h2 className="text-sm font-semibold text-ink">「{selectedModule.label}」操作量趋势</h2>
          <p className="mt-0.5 text-[11px] text-ink-soft">按日（UTC+8）真实业务操作次数</p>
          <div className="mt-3">
            <LineChart
              days={data.days}
              series={[
                {
                  def: { key: selectedModule.module, label: selectedModule.label, color: '#4D83D6' },
                  values: data.days.map((d) => selectedModule.trend[d] ?? 0),
                },
              ]}
              emptyText="窗口内暂无操作记录"
            />
          </div>
        </section>
      )}

      <p className="text-[11px] text-ink-soft">
        页面访问与业务操作是两类不同事件：打开功能页面不等于完成一次真实操作（如打开面试页不等于已生成题目）。功能历史累计量请结合各业务表数据。
      </p>
    </div>
  )
}
