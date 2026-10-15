import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { AurelLoading } from '../../components/aurel-progress/AurelLoading'
import { useAsyncTask } from '../../components/aurel-progress/useAsyncTask'
import type { AdminAuditResponse } from '../../types'
import { formatNumber, formatUtc } from './shared'

const ACTION_LABELS: Record<string, string> = {
  user_status_update: '变更账号状态',
  export_stats: '导出统计数据',
}

/** 操作审计：管理员敏感操作留痕（账号状态变更、数据导出） */
export default function AdminAuditPage() {
  const [data, setData] = useState<AdminAuditResponse | null>(null)
  const task = useAsyncTask({ debugLabel: 'admin-audit' })

  const load = useCallback(
    (targetPage: number) => {
      task.run(async () => {
        const result = await api.adminAudit(targetPage, 20)
        setData(result)
      })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  useEffect(() => {
    load(1)
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
        <AurelLoading scene="common.page" status="error" error={task.error} onRetry={() => load(1)} size="md" />
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">操作审计</h1>
        <p className="mt-1 text-xs text-ink-soft">
          管理员敏感操作（账号状态变更、统计数据导出）的完整留痕；时间显示为 UTC+8。
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-line bg-white shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-xs">
            <thead>
              <tr className="border-b border-line bg-brand-pale/40 text-ink-soft">
                <th className="px-4 py-2.5 font-medium">操作</th>
                <th className="px-3 py-2.5 font-medium">管理员</th>
                <th className="px-3 py-2.5 font-medium">对象</th>
                <th className="px-3 py-2.5 font-medium">详情</th>
                <th className="px-4 py-2.5 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-ink-soft">
                    暂无审计记录
                  </td>
                </tr>
              )}
              {data.items.map((entry) => (
                <tr key={entry.id} className="border-b border-line/50 last:border-0 hover:bg-brand-pale/20">
                  <td className="px-4 py-2.5 font-medium text-ink">{ACTION_LABELS[entry.action] ?? entry.action}</td>
                  <td className="px-3 py-2.5 text-ink-soft">{entry.admin}</td>
                  <td className="px-3 py-2.5 text-ink-soft">
                    {entry.target_type === 'user' ? `用户 #${entry.target_id}` : entry.target_type || '—'}
                  </td>
                  <td className="px-3 py-2.5 text-ink-soft">
                    {entry.detail
                      ? Object.entries(entry.detail)
                          .map(([key, value]) => `${key}: ${String(value)}`)
                          .join(' · ')
                      : '—'}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums text-ink-soft">{formatUtc(entry.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-xs text-ink-soft">
          <span>
            共 {formatNumber(data.total)} 条 · 第 {data.page} / {Math.max(1, Math.ceil(data.total / data.page_size))} 页
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => load(data.page - 1)}
              disabled={data.page <= 1 || task.running}
              className="rounded-lg border border-line bg-white p-1 disabled:opacity-40"
              aria-label="上一页"
            >
              <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => load(data.page + 1)}
              disabled={data.page * data.page_size >= data.total || task.running}
              className="rounded-lg border border-line bg-white p-1 disabled:opacity-40"
              aria-label="下一页"
            >
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
