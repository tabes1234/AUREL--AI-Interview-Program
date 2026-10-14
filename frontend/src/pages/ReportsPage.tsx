import { Loader2, PlusCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import { PageHeading, QuietLink } from '../components/editorial/Editorial'
import { PageTransition, StaggerItem, StaggerList } from '../components/motion/PageTransition'
import { Badge, type BadgeTone } from '../components/ui/Badge'
import { ButtonLink } from '../components/ui/Button'
import { difficultyLabel, formatDateTime, languageLabel, STATUS_LABELS } from '../lib/format'
import type { TaskSummary } from '../types'

type ListState =
  | { phase: 'loading' }
  | { phase: 'error'; message: string }
  | { phase: 'loaded'; tasks: TaskSummary[] }

function statusTone(status: TaskSummary['status']): BadgeTone {
  if (status === 'completed') return 'accent'
  if (status === 'failed') return 'preview'
  return 'brand'
}

/** 回响：Editorial 编辑式布局 —— 开放页首 + 细线行列表，无卡片。 */
export default function ReportsPage() {
  const [state, setState] = useState<ListState>({ phase: 'loading' })

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const tasks = await api.listInterviews(50)
        if (!cancelled) {
          setState({ phase: 'loaded', tasks })
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            phase: 'error',
            message: error instanceof ApiError ? error.message : '加载历史记录失败',
          })
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <PageTransition>
      <PageHeading
        kicker="洞察"
        title="回响"
        subtitle="每一次练习都留下回响：训练历史、评分报告与改进建议。"
        actions={
          <ButtonLink to="/interview/new" size="sm">
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            前往问澜
          </ButtonLink>
        }
      />

      <section className="mt-10" aria-label="训练历史">
        {state.phase === 'loading' ? (
          <p className="flex items-center gap-2 py-10 text-sm text-ink-soft">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            正在加载历史记录…
          </p>
        ) : state.phase === 'error' ? (
          <div className="py-10">
            <p className="max-w-xl text-sm leading-relaxed text-ink-soft">
              无法加载历史记录：{state.message}
            </p>
            <ButtonLink to="/app" variant="secondary" size="sm" className="mt-4">
              返回行舟
            </ButtonLink>
          </div>
        ) : state.tasks.length === 0 ? (
          <div className="py-10">
            <p className="max-w-xl text-sm leading-relaxed text-ink-soft">
              这里还没有回响。创建第一个模拟面试任务，完成后评分报告与改进建议都会在这里等你。
            </p>
            <ButtonLink to="/interview/new" size="sm" className="mt-4">
              前往问澜
            </ButtonLink>
          </div>
        ) : (
          <StaggerList className="divide-y divide-line/70">
            {state.tasks.map((task, index) => (
              <StaggerItem key={task.id} index={index}>
                <article className="group -mx-3 flex flex-col gap-3 px-3 py-4 transition-colors duration-200 hover:bg-white/70 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-[15px] font-semibold text-ink-strong transition-colors group-hover:text-brand-700">
                        {task.position}
                      </h2>
                      <Badge tone={statusTone(task.status)}>{STATUS_LABELS[task.status]}</Badge>
                      <span className="text-xs text-ink-soft">
                        {difficultyLabel(task.difficulty)} · {languageLabel(task.language)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-ink-soft">
                      {task.question_count} 题 · 创建于 {formatDateTime(task.created_at)}
                      {task.error_message ? ` · ${task.error_message}` : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-4">
                    {task.overall_score !== null ? (
                      <span className="text-2xl font-bold leading-none text-ink-strong">
                        {task.overall_score.toFixed(1)}
                      </span>
                    ) : null}
                    {task.status === 'completed' ? (
                      <QuietLink to={`/reports/${task.id}`}>查看报告</QuietLink>
                    ) : task.status === 'failed' ? (
                      <QuietLink to="/interview/new">重新创建</QuietLink>
                    ) : (
                      <QuietLink to={`/interview/${task.id}`}>继续面试 →</QuietLink>
                    )}
                  </div>
                </article>
              </StaggerItem>
            ))}
          </StaggerList>
        )}
      </section>
    </PageTransition>
  )
}
