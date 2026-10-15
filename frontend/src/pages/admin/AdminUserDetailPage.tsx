import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { LineChart } from '../../components/admin/charts'
import { TimeRangePicker } from '../../components/admin/TimeRangePicker'
import { AurelLoading } from '../../components/aurel-progress/AurelLoading'
import { useAsyncTask } from '../../components/aurel-progress/useAsyncTask'
import type { AdminUserDetail } from '../../types'
import { formatDate, formatMs, formatNumber, formatRate, rangeParams, useAdminRange } from './shared'

/** 单个用户的使用情况详情：功能使用、AI 调用与趋势（不含任何私人内容） */
export default function AdminUserDetailPage() {
  const { userId } = useParams()
  const [range, setRange] = useAdminRange()
  const [detail, setDetail] = useState<AdminUserDetail | null>(null)
  const detailTask = useAsyncTask({ debugLabel: 'admin-user-detail' })

  const load = useCallback(() => {
    if (!userId) return
    detailTask.run(async () => {
      const data = await api.adminUserDetail(Number(userId), rangeParams(range))
      setDetail(data)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, userId])

  useEffect(() => {
    load()
  }, [load])

  if (detailTask.running && !detail) {
    return (
      <div className="flex justify-center py-14">
        <AurelLoading scene="common.page" phase={detailTask.status === 'preparing' ? 'preparing' : 'loading'} elapsedMs={detailTask.elapsedMs} size="md" />
      </div>
    )
  }

  if (detailTask.status === 'error') {
    return (
      <div className="flex justify-center py-12">
        <AurelLoading scene="common.page" status="error" error={detailTask.error} onRetry={load} size="md" />
      </div>
    )
  }

  if (!detail) return null

  const profile = detail.user
  const ai = detail.ai_in_range
  const aiAll = detail.ai_all_time
  const totalActions = detail.modules_in_range.reduce((sum, m) => sum + m.actions, 0)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/admin/users" className="inline-flex items-center gap-1 text-xs text-ink-soft transition hover:text-ink">
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            返回用户列表
          </Link>
          <h1 className="mt-1 text-xl font-semibold">
            {profile.nickname || profile.username}
            <span className="ml-2 text-sm font-normal text-ink-soft">
              {profile.username} · #{profile.id}
              {profile.role === 'admin' && <span className="ml-1.5 rounded-full bg-brand-pale px-2 py-0.5 text-[11px] text-brand-700">管理员</span>}
            </span>
          </h1>
        </div>
        <TimeRangePicker value={range} onChange={setRange} />
      </div>

      {/* 基本信息 */}
      <div className="grid gap-2.5 rounded-2xl border border-line bg-white p-4 shadow-card sm:grid-cols-4">
        <div>
          <p className="text-[11px] text-ink-soft">账号状态</p>
          <p className="mt-0.5 text-sm font-medium">{profile.status === 'active' ? '正常' : '已停用'}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">注册时间</p>
          <p className="mt-0.5 text-sm tabular-nums">{formatDate(profile.created_at)}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">最近登录</p>
          <p className="mt-0.5 text-sm tabular-nums">{formatDate(profile.last_login_at)}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-soft">最近活跃</p>
          <p className="mt-0.5 text-sm tabular-nums">{formatDate(profile.last_active_at)}</p>
        </div>
      </div>

      {/* 窗口内使用概况 */}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
          <h2 className="text-sm font-semibold text-ink">功能使用（窗口内）</h2>
          {detail.modules_in_range.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-soft">窗口内暂无使用记录</p>
          ) : (
            <table className="mt-3 w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line text-ink-soft">
                  <th className="py-1.5 font-medium">模块</th>
                  <th className="py-1.5 text-right font-medium">页面访问</th>
                  <th className="py-1.5 text-right font-medium">操作次数</th>
                  <th className="py-1.5 text-right font-medium">操作失败</th>
                  <th className="py-1.5 text-right font-medium">最近使用</th>
                </tr>
              </thead>
              <tbody>
                {detail.modules_in_range.map((m) => (
                  <tr key={m.module} className="border-b border-line/50 last:border-0">
                    <td className="py-1.5 text-ink">{m.label}</td>
                    <td className="py-1.5 text-right tabular-nums">{formatNumber(m.page_views)}</td>
                    <td className="py-1.5 text-right tabular-nums">{formatNumber(m.actions)}</td>
                    <td className="py-1.5 text-right tabular-nums">{m.action_errors > 0 ? formatNumber(m.action_errors) : '—'}</td>
                    <td className="py-1.5 text-right tabular-nums text-ink-soft">{m.last_used ? m.last_used.slice(5, 16).replace('T', ' ') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
          <h2 className="text-sm font-semibold text-ink">功能历史累计</h2>
          <p className="mt-0.5 text-[11px] text-ink-soft">直接来自各业务表的真实落库记录（含统计采集开始之前）</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            {detail.historical_counts.map((item) => (
              <div key={item.feature} className="flex items-center justify-between rounded-xl bg-brand-pale/50 px-3 py-2">
                <span className="text-ink-soft">{item.feature}</span>
                <span className="font-semibold tabular-nums text-ink">{formatNumber(item.count)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* AI 使用 */}
      <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-ink">AI 调用情况</h2>
        <div className="mt-3 grid gap-2.5 sm:grid-cols-4">
          <div className="rounded-xl bg-brand-pale/50 px-3.5 py-3">
            <p className="text-[11px] text-ink-soft">窗口内请求数</p>
            <p className="mt-0.5 text-base font-semibold tabular-nums">{formatNumber(ai.total)}</p>
            <p className="mt-0.5 text-[10px] text-ink-soft">成功率 {formatRate(ai.success_rate)}</p>
          </div>
          <div className="rounded-xl bg-brand-pale/50 px-3.5 py-3">
            <p className="text-[11px] text-ink-soft">窗口内平均耗时</p>
            <p className="mt-0.5 text-base font-semibold tabular-nums">{formatMs(ai.avg_latency_ms)}</p>
            <p className="mt-0.5 text-[10px] text-ink-soft">P95 {formatMs(ai.p95_ms)}</p>
          </div>
          <div className="rounded-xl bg-brand-pale/50 px-3.5 py-3">
            <p className="text-[11px] text-ink-soft">累计请求数</p>
            <p className="mt-0.5 text-base font-semibold tabular-nums">{formatNumber(aiAll.total)}</p>
            <p className="mt-0.5 text-[10px] text-ink-soft">成功率 {formatRate(aiAll.success_rate)}</p>
          </div>
          <div className="rounded-xl bg-brand-pale/50 px-3.5 py-3">
            <p className="text-[11px] text-ink-soft">窗口内 Token 用量</p>
            <p className="mt-0.5 text-base font-semibold tabular-nums">{ai.tokens_total !== null ? formatNumber(ai.tokens_total) : '未返回用量'}</p>
            <p className="mt-0.5 text-[10px] text-ink-soft">仅统计真实 usage</p>
          </div>
        </div>
      </section>

      {/* 使用趋势 */}
      <section className="rounded-2xl border border-line bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-ink">使用趋势（窗口内，按日）</h2>
        <div className="mt-3">
          <LineChart
            days={detail.trend.days}
            series={[
              { def: { key: 'pv', label: '页面访问', color: '#8E7CC3' }, values: detail.trend.days.map((d) => detail.trend.page_views[d] ?? 0) },
              { def: { key: 'act', label: '业务操作', color: '#4D83D6' }, values: detail.trend.days.map((d) => detail.trend.actions[d] ?? 0) },
            ]}
            emptyText={totalActions === 0 ? '窗口内暂无使用记录' : '暂无数据'}
          />
        </div>
      </section>

      <p className="text-[11px] text-ink-soft">
        本页仅展示使用统计与调用指标；用户的聊天正文、简历内容与输入内容不在展示范围内。
      </p>
    </div>
  )
}
