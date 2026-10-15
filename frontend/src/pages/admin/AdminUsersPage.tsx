import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import { TimeRangePicker } from '../../components/admin/TimeRangePicker'
import { AurelLoading } from '../../components/aurel-progress/AurelLoading'
import { useAsyncTask } from '../../components/aurel-progress/useAsyncTask'
import type { AdminUsersPage as AdminUsersData } from '../../types'
import { formatDate, formatNumber, rangeParams, useAdminRange } from './shared'

const SORT_OPTIONS = [
  { key: 'created_at', label: '按注册时间' },
  { key: 'last_active', label: '按最近活跃' },
  { key: 'usage', label: '按使用次数' },
  { key: 'ai', label: '按 AI 调用' },
]

/** 用户使用管理：搜索、筛选、分页、状态操作（全部由服务端完成） */
export default function AdminUsersPage() {
  const [range, setRange] = useAdminRange()
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState('created_at')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AdminUsersData | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const listTask = useAsyncTask({ debugLabel: 'admin-users' })

  const load = useCallback(
    (targetPage: number) => {
      listTask.run(async () => {
        const result = await api.adminUsers({
          ...rangeParams(range),
          q: query.trim() || undefined,
          status: statusFilter || undefined,
          sort,
          page: targetPage,
          page_size: 20,
        })
        setData(result)
        setPage(targetPage)
      })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [range, query, statusFilter, sort],
  )

  useEffect(() => {
    load(1)
  }, [load])

  const toggleStatus = async (userId: number, current: string) => {
    const next = current === 'active' ? 'disabled' : 'active'
    const verb = next === 'disabled' ? '暂停' : '恢复'
    if (!window.confirm(`确认${verb}该账号？${next === 'disabled' ? '该用户的所有登录会话将被立即撤销。' : ''}`)) {
      return
    }
    try {
      await api.adminUpdateUserStatus(userId, next)
      setActionError(null)
      load(page)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '操作失败，请稍后重试')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">用户使用</h1>
          <p className="mt-1 text-xs text-ink-soft">
            使用次数与 AI 调用统计窗口：{range.start} ~ {range.end}（UTC+8）；仅展示管理必需信息，不含用户私人内容。
          </p>
        </div>
        <TimeRangePicker value={range} onChange={setRange} />
      </div>

      {/* 筛选行 */}
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs text-ink-soft shadow-card">
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load(1)}
            placeholder="搜索用户名或昵称"
            className="w-40 bg-transparent text-ink outline-none placeholder:text-ink-soft/70"
          />
        </label>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-full border border-line bg-white px-3 py-1.5 text-xs text-ink outline-none shadow-card"
          aria-label="账号状态筛选"
        >
          <option value="">全部状态</option>
          <option value="active">正常</option>
          <option value="disabled">已停用</option>
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="rounded-full border border-line bg-white px-3 py-1.5 text-xs text-ink outline-none shadow-card"
          aria-label="排序方式"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => load(1)}
          className="rounded-full bg-brand-600 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-brand-700"
        >
          查询
        </button>
      </div>

      {actionError && <p className="rounded-xl bg-[#FDF3F2] px-3.5 py-2 text-xs text-[#B4574B]">{actionError}</p>}

      {listTask.running && !data ? (
        <div className="flex justify-center py-14">
          <AurelLoading scene="common.page" phase={listTask.status === 'preparing' ? 'preparing' : 'loading'} elapsedMs={listTask.elapsedMs} size="md" />
        </div>
      ) : listTask.status === 'error' ? (
        <div className="flex justify-center py-10">
          <AurelLoading scene="common.page" status="error" error={listTask.error} onRetry={() => load(1)} size="md" />
        </div>
      ) : data ? (
        <div className="overflow-hidden rounded-2xl border border-line bg-white shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-line bg-brand-pale/40 text-ink-soft">
                  <th className="px-4 py-2.5 font-medium">用户</th>
                  <th className="px-3 py-2.5 font-medium">状态</th>
                  <th className="px-3 py-2.5 font-medium">注册时间</th>
                  <th className="px-3 py-2.5 font-medium">最近活跃</th>
                  <th className="px-3 py-2.5 text-right font-medium">窗口内使用</th>
                  <th className="px-3 py-2.5 text-right font-medium">AI 调用</th>
                  <th className="px-3 py-2.5 font-medium">最近使用模块</th>
                  <th className="px-4 py-2.5 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-10 text-center text-ink-soft">
                      没有符合条件的用户
                    </td>
                  </tr>
                )}
                {data.items.map((user) => (
                  <tr key={user.id} className="border-b border-line/60 last:border-0 hover:bg-brand-pale/30">
                    <td className="px-4 py-2.5">
                      <Link to={`/admin/users/${user.id}`} className="font-medium text-brand-700 hover:underline">
                        {user.nickname || user.username}
                      </Link>
                      <p className="mt-0.5 text-[11px] text-ink-soft">
                        {user.username} · #{user.id}
                        {user.role === 'admin' && <span className="ml-1 rounded-full bg-brand-pale px-1.5 py-0.5 text-[10px] text-brand-700">管理员</span>}
                      </p>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] ${user.status === 'active' ? 'bg-[#EDF7F0] text-[#3F7D5A]' : 'bg-[#FBF1EF] text-[#A3543F]'}`}>
                        {user.status === 'active' ? '正常' : '已停用'}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-ink-soft">{formatDate(user.created_at)}</td>
                    <td className="px-3 py-2.5 tabular-nums text-ink-soft">{user.last_active_at ? formatDate(user.last_active_at) : '—'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(user.usage_count)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(user.ai_calls)}</td>
                    <td className="px-3 py-2.5 text-ink-soft">{user.last_module ?? '—'}</td>
                    <td className="px-4 py-2.5 text-right">
                      {user.status === 'active' ? (
                        <button
                          type="button"
                          onClick={() => toggleStatus(user.id, user.status)}
                          className="rounded-full border border-line px-2.5 py-1 text-[11px] text-ink-soft transition hover:border-[#D9A79B] hover:text-[#A3543F]"
                        >
                          暂停账号
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => toggleStatus(user.id, user.status)}
                          className="rounded-full border border-line px-2.5 py-1 text-[11px] text-ink-soft transition hover:border-ripple hover:text-brand-700"
                        >
                          恢复账号
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* 分页 */}
          <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-xs text-ink-soft">
            <span>
              共 {formatNumber(data.total)} 位用户 · 第 {data.page} / {Math.max(1, data.pages)} 页
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => load(data.page - 1)}
                disabled={data.page <= 1 || listTask.running}
                className="rounded-lg border border-line bg-white p-1 disabled:opacity-40"
                aria-label="上一页"
              >
                <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => load(data.page + 1)}
                disabled={data.page >= data.pages || listTask.running}
                className="rounded-lg border border-line bg-white p-1 disabled:opacity-40"
                aria-label="下一页"
              >
                <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <p className="text-[11px] text-ink-soft">
        暂停账号将立即撤销其全部登录会话（服务端真实生效）；所有账号状态变更都会记录到操作审计。
      </p>
    </div>
  )
}
