import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { TimeRangePicker } from '../../components/admin/TimeRangePicker'
import { AurelLoading } from '../../components/aurel-progress/AurelLoading'
import { useAsyncTask } from '../../components/aurel-progress/useAsyncTask'
import type { AdminAiResponse } from '../../types'
import { formatMs, formatNumber, formatRate, rangeParams, useAdminRange } from './shared'

function Metric({ label, value, hint, warn }: { label: string; value: string; hint?: string; warn?: boolean }) {
  return (
    <div className="min-w-[120px] flex-1 rounded-xl border border-line bg-white px-3.5 py-2.5">
      <p className="text-[11px] text-ink-soft">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tabular-nums ${warn ? 'text-[#A3543F]' : 'text-ink'}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[10px] leading-4 text-ink-soft">{hint}</p>}
    </div>
  )
}

/** AI 运行情况：请求量、成功率、耗时分布、错误分类与 Token 用量（全部真实记录） */
export default function AdminAiPage() {
  const [range, setRange] = useAdminRange()
  const [data, setData] = useState<AdminAiResponse | null>(null)
  const task = useAsyncTask({ debugLabel: 'admin-ai' })

  const load = useCallback(() => {
    task.run(async () => {
      const result = await api.adminAi(rangeParams(range))
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

  const totals = data.totals

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">AI 运行</h1>
          <p className="mt-1 text-xs text-ink-soft">
            统计窗口 {data.range.start} ~ {data.range.end} · {data.timezone} · 数据来自模型调用观测记录（llm_call_records）
          </p>
        </div>
        <TimeRangePicker value={range} onChange={setRange} />
      </div>

      {/* 核心指标 */}
      <div className="flex flex-wrap gap-2.5">
        <Metric label="请求总量" value={formatNumber(totals.total)} />
        <Metric label="成功" value={formatNumber(totals.success)} />
        <Metric label="失败" value={formatNumber(totals.failed)} warn={totals.failed > 0} />
        <Metric label="成功率" value={formatRate(totals.success_rate)} warn={totals.success_rate !== null && totals.success_rate < 0.9} />
        <Metric label="平均耗时" value={formatMs(totals.avg_latency_ms)} />
        <Metric label="P50" value={formatMs(totals.p50_ms)} />
        <Metric label="P95" value={formatMs(totals.p95_ms)} />
        <Metric label="超时" value={totals.timeouts !== null ? formatNumber(totals.timeouts) : '—'} warn={(totals.timeouts ?? 0) > 0} />
        <Metric
          label="Token 总量"
          value={totals.tokens_total !== null ? formatNumber(totals.tokens_total) : '未返回'}
          hint={totals.tokens_total !== null ? `有用量记录 ${totals.calls_with_usage} 次` : '当前服务未提供该项数据'}
        />
      </div>

      {/* 采集说明 */}
      <div className="rounded-2xl border border-line bg-brand-pale/50 p-3.5 text-[11px] leading-5 text-ink-soft">
        <p>· 耗时口径：从发起模型请求到拿到最终结果/错误的总耗时（含重试等待）。{data.notes.first_output}</p>
        <p>· {data.notes.cancelled}；{data.notes.tokens}；{data.notes.cost}</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* 按服务 */}
        <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
          <h2 className="text-sm font-semibold text-ink">按功能服务分布</h2>
          {data.by_service.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-soft">窗口内暂无 AI 调用</p>
          ) : (
            <table className="mt-3 w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line text-ink-soft">
                  <th className="py-1.5 font-medium">服务 / 模块</th>
                  <th className="py-1.5 text-right font-medium">请求</th>
                  <th className="py-1.5 text-right font-medium">成功率</th>
                  <th className="py-1.5 text-right font-medium">平均耗时</th>
                  <th className="py-1.5 text-right font-medium">P95</th>
                  <th className="py-1.5 text-right font-medium">Token</th>
                </tr>
              </thead>
              <tbody>
                {data.by_service.map((service) => (
                  <tr key={service.service} className="border-b border-line/50 last:border-0">
                    <td className="py-1.5">
                      <p className="font-medium text-ink">{service.module_label}</p>
                      <p className="text-[10px] text-ink-soft">{service.service}</p>
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{formatNumber(service.total)}</td>
                    <td className={`py-1.5 text-right tabular-nums ${service.success_rate !== null && service.success_rate < 0.9 ? 'text-[#A3543F]' : ''}`}>
                      {formatRate(service.success_rate)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{formatMs(service.avg_latency_ms)}</td>
                    <td className="py-1.5 text-right tabular-nums">{formatMs(service.p95_ms)}</td>
                    <td className="py-1.5 text-right tabular-nums">{service.tokens_total !== null ? formatNumber(service.tokens_total) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* 模型与错误分类 */}
        <div className="space-y-4">
          <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
            <h2 className="text-sm font-semibold text-ink">按模型分布</h2>
            {data.by_model.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-soft">窗口内暂无 AI 调用</p>
            ) : (
              <ul className="mt-3 space-y-1.5 text-xs">
                {data.by_model.map((model) => (
                  <li key={model.model} className="flex items-center justify-between rounded-xl bg-brand-pale/40 px-3 py-2">
                    <span className="truncate text-ink" title={model.model}>
                      {model.model}
                    </span>
                    <span className="ml-3 shrink-0 tabular-nums text-ink-soft">
                      {formatNumber(model.total)} 次{model.has_usage ? ` · ${formatNumber(model.tokens_total)} tokens` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
            <h2 className="text-sm font-semibold text-ink">错误分类</h2>
            {data.error_categories.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-soft">窗口内没有失败调用</p>
            ) : (
              <ul className="mt-3 space-y-1.5 text-xs">
                {data.error_categories.map((category) => (
                  <li key={category.category} className="flex items-center justify-between">
                    <span className="text-ink">{category.category}</span>
                    <span className="font-semibold tabular-nums text-[#A3543F]">{formatNumber(category.count)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      {/* 近期失败明细（已脱敏） */}
      <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-ink">近期失败调用（已脱敏）</h2>
        {data.recent_errors.length === 0 ? (
          <p className="py-6 text-center text-sm text-ink-soft">窗口内没有失败调用</p>
        ) : (
          <ul className="mt-3 space-y-2 text-xs">
            {data.recent_errors.map((error) => (
              <li key={error.id} className="rounded-xl border border-line/70 px-3.5 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-ink">
                    {error.module_label}
                    <span className="ml-2 font-normal text-ink-soft">{error.category}</span>
                  </span>
                  <span className="tabular-nums text-ink-soft">{error.created_at.slice(0, 19).replace('T', ' ')} UTC</span>
                </div>
                {error.message && <p className="mt-1 break-all text-[11px] leading-5 text-ink-soft">{error.message}</p>}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[11px] text-ink-soft">错误摘要已剔除凭证类字段并截断长度，不含用户输入内容。</p>
      </section>
    </div>
  )
}
