import { Download, HelpCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { BarsChart, LineChart } from '../../components/admin/charts'
import { TimeRangePicker } from '../../components/admin/TimeRangePicker'
import { AurelLoading } from '../../components/aurel-progress/AurelLoading'
import { useAsyncTask } from '../../components/aurel-progress/useAsyncTask'
import { ApiError } from '../../api/client'
import type { AdminOverview, AdminTrends } from '../../types'
import { formatMs, formatNumber, formatRate, rangeParams, useAdminRange } from './shared'

function Metric({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: string
  hint?: string
  accent?: boolean
}) {
  return (
    <div className="min-w-[104px] flex-1 rounded-xl border border-line bg-white px-3.5 py-2.5">
      <p className="text-[11px] text-ink-soft">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tabular-nums ${accent ? 'text-brand-700' : 'text-ink'}`}>
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[10px] leading-4 text-ink-soft">{hint}</p>}
    </div>
  )
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {subtitle && <p className="text-[11px] text-ink-soft">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

/** 数据总览：核心指标、趋势、近期活动，全部来自真实统计接口 */
export default function AdminOverviewPage() {
  const [range, setRange] = useAdminRange()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [trends, setTrends] = useState<AdminTrends | null>(null)
  const [showDefinitions, setShowDefinitions] = useState(false)
  const overviewTask = useAsyncTask({ debugLabel: 'admin-overview' })
  const trendsTask = useAsyncTask({ debugLabel: 'admin-trends' })

  const load = useCallback(() => {
    overviewTask.run(async () => {
      const data = await api.adminOverview(rangeParams(range))
      setOverview(data)
    })
    trendsTask.run(async () => {
      const data = await api.adminTrends(rangeParams(range))
      setTrends(data)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range])

  useEffect(() => {
    load()
  }, [load])

  const exportCsv = async (kind: 'overview' | 'users' | 'ai') => {
    try {
      const { blob, filename } = await api.adminExport(kind, rangeParams(range))
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : '导出失败，请稍后重试'
      window.alert(message)
    }
  }

  if (overviewTask.running && !overview) {
    return (
      <div className="flex justify-center py-16">
        <AurelLoading scene="common.page" phase={overviewTask.status === 'preparing' ? 'preparing' : 'loading'} elapsedMs={overviewTask.elapsedMs} size="md" />
      </div>
    )
  }

  if (overviewTask.status === 'error') {
    return (
      <div className="flex justify-center py-12">
        <AurelLoading scene="common.page" status="error" error={overviewTask.error} onRetry={load} size="md" />
      </div>
    )
  }

  if (!overview) return null

  const users = overview.users
  const ai = overview.ai
  const trendDays = trends?.days ?? []
  const series = trends?.series

  return (
    <div className="space-y-5">
      {/* 标题行：周期筛选 + 导出 + 口径说明 */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">数据总览</h1>
          <p className="mt-1 text-xs text-ink-soft">
            统计窗口 {overview.range.start} ~ {overview.range.end} · {overview.timezone} · 生成于 {overview.generated_at.slice(0, 19).replace('T', ' ')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TimeRangePicker value={range} onChange={setRange} />
          <button
            type="button"
            onClick={() => setShowDefinitions((open) => !open)}
            className="flex items-center gap-1 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:border-ripple hover:text-ink"
          >
            <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
            统计口径
          </button>
          <button
            type="button"
            onClick={() => exportCsv('overview')}
            className="flex items-center gap-1 rounded-full bg-brand-600 px-3.5 py-1.5 text-xs font-medium text-white transition hover:bg-brand-700"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
            导出 CSV
          </button>
        </div>
      </div>

      {showDefinitions && (
        <div className="rounded-2xl border border-line bg-brand-pale/60 p-4 text-xs leading-6 text-ink-soft">
          <p className="mb-1 font-semibold text-ink">统计口径说明</p>
          <ul className="list-disc space-y-1 pl-5">
            {Object.entries(overview.definitions).map(([key, text]) => (
              <li key={key}>
                <span className="font-medium text-ink">{key}：</span>
                {text}
              </li>
            ))}
          </ul>
        </div>
      )}

      {overview.collection_started_at && (
        <p className="rounded-xl bg-brand-pale/60 px-3.5 py-2 text-[11px] text-ink-soft">
          使用事件自 {overview.collection_started_at.slice(0, 19).replace('T', ' ')}（UTC）开始采集；更早时期的功能使用量来自各业务表真实数据，页面访问没有历史数据。
        </p>
      )}

      {/* 核心指标行（紧凑） */}
      <div className="flex flex-wrap gap-2.5">
        <Metric label="累计注册用户" value={formatNumber(users.total)} hint={users.disabled > 0 ? `${users.disabled} 个账号已停用` : undefined} />
        <Metric label="窗口内新增" value={formatNumber(users.new_in_range)} />
        <Metric label="窗口内活跃" value={formatNumber(users.active_in_range)} accent />
        <Metric label="日活跃 DAU" value={formatNumber(users.dau)} />
        <Metric label="周活跃 WAU" value={formatNumber(users.wau)} />
        <Metric label="月活跃 MAU" value={formatNumber(users.mau)} />
        <Metric label="页面访问" value={formatNumber(overview.pages.views_in_range)} hint={overview.pages.note} />
        <Metric label="AI 请求数" value={formatNumber(ai.total)} />
        <Metric label="AI 成功率" value={formatRate(ai.success_rate)} hint={ai.failed > 0 ? `失败 ${ai.failed} 次` : undefined} accent={ai.failed > 0} />
        <Metric label="AI 平均耗时" value={formatMs(ai.avg_latency_ms)} hint={ai.p95_ms !== null ? `P95 ${formatMs(ai.p95_ms)}` : undefined} />
      </div>

      {/* 趋势图区 */}
      {trendsTask.running && !trends ? (
        <div className="flex justify-center py-10">
          <AurelLoading scene="common.page" phase="loading" size="sm" />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="新增与活跃用户" subtitle="按日（UTC+8）">
            <LineChart
              days={trendDays}
              series={[
                { def: { key: 'new', label: '新增用户', color: '#4D83D6' }, values: trendDays.map((d) => series?.new_users[d] ?? 0) },
                { def: { key: 'active', label: '活跃用户', color: '#7FB0EE' }, values: trendDays.map((d) => series?.active_users[d] ?? 0) },
              ]}
            />
          </ChartCard>
          <ChartCard title="AI 请求与失败量" subtitle="真实模型调用记录">
            <LineChart
              days={trendDays}
              series={[
                { def: { key: 'req', label: '请求数', color: '#4D83D6' }, values: trendDays.map((d) => series?.ai_requests[d] ?? 0) },
                { def: { key: 'err', label: '失败数', color: '#C97B6D' }, values: trendDays.map((d) => series?.ai_errors[d] ?? 0) },
              ]}
            />
          </ChartCard>
          <ChartCard title="AI 成功率与平均耗时" subtitle="成功率（%）/ 平均耗时（毫秒）">
            <LineChart
              days={trendDays}
              series={[
                {
                  def: { key: 'rate', label: '成功率%', color: '#5FA97C' },
                  values: trendDays.map((d) => {
                    const rate = series?.ai_success_rate[d]
                    return rate === null || rate === undefined ? null : Math.round(rate * 1000) / 10
                  }),
                },
                { def: { key: 'lat', label: '平均耗时ms', color: '#B0885E' }, values: trendDays.map((d) => series?.ai_avg_latency_ms[d] ?? null) },
              ]}
              formatValue={(v) => formatNumber(v)}
            />
          </ChartCard>
          <ChartCard title="页面访问" subtitle="登录用户页面访问（去重后）">
            <LineChart
              days={trendDays}
              series={[{ def: { key: 'pv', label: '页面访问', color: '#8E7CC3' }, values: trendDays.map((d) => series?.page_views[d] ?? 0) }]}
              emptyText="尚未采集（页面访问自管理中心上线开始记录）"
            />
          </ChartCard>
          <ChartCard title="模块使用排行" subtitle="窗口内真实业务操作次数">
            <BarsChart
              items={overview.modules.slice(0, 10).map((m) => ({ label: m.label, value: m.actions, sub: `${m.users} 人` }))}
              emptyText="窗口内暂无业务操作记录"
            />
          </ChartCard>
          {ai.tokens_total !== null && (
            <ChartCard title="Token 用量" subtitle="仅统计模型返回真实 usage 的调用">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-xl bg-brand-pale/60 px-3 py-3">
                  <p className="text-[11px] text-ink-soft">输入</p>
                  <p className="mt-1 text-base font-semibold tabular-nums">{formatNumber(ai.tokens_input)}</p>
                </div>
                <div className="rounded-xl bg-brand-pale/60 px-3 py-3">
                  <p className="text-[11px] text-ink-soft">输出</p>
                  <p className="mt-1 text-base font-semibold tabular-nums">{formatNumber(ai.tokens_output)}</p>
                </div>
                <div className="rounded-xl bg-brand-pale/60 px-3 py-3">
                  <p className="text-[11px] text-ink-soft">总量</p>
                  <p className="mt-1 text-base font-semibold tabular-nums">{formatNumber(ai.tokens_total)}</p>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-ink-soft">费用折算暂不提供：各渠道实际计价方式不同且可能变动，避免误导。</p>
            </ChartCard>
          )}
        </div>
      )}

      {/* 近期活动 */}
      <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-ink">近期活动</h2>
        {overview.recent_activity.items.length === 0 ? (
          <p className="py-6 text-center text-sm text-ink-soft">暂无活动记录</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {overview.recent_activity.items.map((item, index) => (
              <li key={`${item.at}-${index}`} className="flex flex-wrap items-center justify-between gap-2 py-2 text-xs">
                <span className="flex items-center gap-2">
                  <span
                    className={`inline-block h-1.5 w-1.5 rounded-full ${
                      item.type === 'ai_error' ? 'bg-[#C97B6D]' : item.type === 'register' ? 'bg-[#5FA97C]' : 'bg-brand-400'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="text-ink">{item.label}</span>
                  {item.detail && <span className="text-ink-soft">（{item.detail}）</span>}
                </span>
                <span className="tabular-nums text-ink-soft">{item.at.slice(0, 19).replace('T', ' ')} UTC</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[11px] text-ink-soft">活动摘要仅包含事件元数据，不含用户输入内容、聊天正文或简历内容。</p>
      </section>
    </div>
  )
}
