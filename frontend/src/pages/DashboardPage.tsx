import {
  Briefcase,
  Flame,
  Loader2,
  PenLine,
  PlusCircle,
  Puzzle,
  BookOpenText,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import { PageTransition } from '../components/motion/PageTransition'
import { ServiceStatus } from '../components/ServiceStatus'
import { ButtonLink } from '../components/ui/Button'
import {
  EntryRow,
  PageHeading,
  QuietLink,
  SectionHead,
  StatStrip,
  TimelineList,
  TimelineRow,
} from '../components/editorial/Editorial'
import { difficultyLabel, formatDateTime, STATUS_LABELS } from '../lib/format'
import type { GrowthHeatmap, TaskSummary, WeeklyReport } from '../types'

function taskTone(status: TaskSummary['status']): 'idle' | 'done' | 'accent' | 'warn' {
  if (status === 'completed') return 'done'
  if (status === 'failed') return 'warn'
  if (status === 'in_progress' || status === 'generating_questions' || status === 'generating_report')
    return 'accent'
  return 'idle'
}

interface TasksState {
  loading: boolean
  tasks: TaskSummary[]
  error: string | null
}

/** 行舟工作区：Editorial 编辑式三层布局（开放标题区 / 核心操作区 / 信息流与成长轨迹）。 */
export default function DashboardPage() {
  const [tasksState, setTasksState] = useState<TasksState>({
    loading: true,
    tasks: [],
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    api
      .listInterviews(20)
      .then((tasks) => {
        if (!cancelled) setTasksState({ loading: false, tasks, error: null })
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setTasksState({
            loading: false,
            tasks: [],
            error: error instanceof ApiError ? error.message : '加载任务失败',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const completed = tasksState.tasks.filter(
    (t) => t.status === 'completed' && t.overall_score !== null,
  )
  const averageScore =
    completed.length > 0
      ? Math.round(
          (completed.reduce((sum, task) => sum + (task.overall_score ?? 0), 0) /
            completed.length) *
            10,
        ) / 10
      : null
  const latestTask = tasksState.tasks[0] ?? null

  return (
    <PageTransition>
      {/* ── 第一层：开放式标题区（无卡片） ─────────────────────────── */}
      <PageHeading
        kicker="观澜 · 见微知远"
        title="行舟"
        subtitle="循着目标启程，让每一次练习都留下回响。"
        actions={
          <>
            <div className="flex flex-wrap gap-2 text-xs">
              <ServiceStatus />
            </div>
            <ButtonStart />
          </>
        }
      />

      {/* ── 第二层：核心操作区 —— 问澜居视觉中心，功课以细线条目展开 ── */}
      <section className="mt-12 grid gap-10 lg:grid-cols-12" aria-label="核心操作">
        {/* 问澜：唯一的背景区域，占据视觉主体 */}
        <div className="lg:col-span-7">
          <div className="relative overflow-hidden rounded-3xl border border-ripple/40 bg-gradient-to-br from-mist via-white to-shallow/70 px-7 py-8 sm:px-9 sm:py-10">
            {/* 内部一抹水汽，替代阴影卡片感 */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-14 -top-16 h-48 w-48 rounded-full bg-shallow/60 blur-2xl"
            />
            <p className="relative text-xs font-semibold tracking-[0.28em] text-brand-600/85">
              今日启程
            </p>
            <h2 className="relative mt-3 text-3xl font-bold tracking-tight text-ink-strong">
              问澜
            </h2>
            <p className="relative mt-2 max-w-lg text-base leading-relaxed text-ink">
              选定行业与职业，AI 依你的资料生成针对性问题、逐题追问；答完即得可解释的评分与建议。
            </p>
            <div className="relative mt-6 flex flex-wrap items-center gap-4">
              <ButtonStart />
              <QuietLink to="/reports">回看训练记录</QuietLink>
            </div>
            {/* 最近一次任务的真实状态（非伪造） */}
            <div className="relative mt-7 border-t border-ripple/40 pt-4 text-sm text-ink-soft">
              {tasksState.loading ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  正在读取最近任务…
                </span>
              ) : latestTask ? (
                <span>
                  最近一次：
                  <span className="font-semibold text-ink">{latestTask.position}</span>
                  {' · '}
                  {STATUS_LABELS[latestTask.status]}
                  {' · '}
                  {formatDateTime(latestTask.created_at)}
                  {latestTask.status === 'completed' ? (
                    <>
                      {' · '}
                      <QuietLink to={`/reports/${latestTask.id}`}>查看报告</QuietLink>
                    </>
                  ) : null}
                </span>
              ) : (
                <span>尚未开始第一次训练 —— 万事开头，一苇以航。</span>
              )}
            </div>
          </div>
        </div>

        {/* 右列：行囊 —— 开放式条目列表，细线分隔，无卡片 */}
        <div className="lg:col-span-5">
          <SectionHead title="行囊" note="读岗、写履历、两相对照，皆有据可依" />
          <div className="mt-2">
            <EntryRow
              to="/jobs"
              icon={Briefcase}
              title="知岗"
              description="粘贴岗位描述，解析要求与考察方向"
            />
            <EntryRow
              to="/resume"
              icon={PenLine}
              title="履历成章"
              description="结构化编辑简历，导出真实文档"
            />
            <EntryRow
              to="/matching"
              icon={Puzzle}
              title="合契"
              description="简历与岗位对照，命中缺失皆有原文为证"
            />
            <EntryRow
              to="/knowledge"
              icon={BookOpenText}
              title="知藏"
              description="汇入资料建立知识库，出题有据可循"
            />
          </div>
          {/* 另有渡口：安静文字链接，不同视觉权重 */}
          <p className="mt-5 text-sm leading-7 text-ink-soft">
            另有渡口：
            <QuietLink to="/skills" className="mr-3">观己</QuietLink>
            <QuietLink to="/reports" className="mr-3">回响</QuietLink>
            <QuietLink to="/challenges" className="mr-3">度衡</QuietLink>
            <QuietLink to="/mistakes" className="mr-3">回澜</QuietLink>
            <QuietLink to="/expression" className="mr-3">听澜</QuietLink>
            <QuietLink to="/concerto">协奏</QuietLink>
          </p>
        </div>
      </section>

      {/* ── 第三层：信息流 —— 航程时间线 + 最近回响 ────────────────── */}
      <section className="mt-14 grid gap-10 lg:grid-cols-12" aria-label="航程记录">
        <div className="lg:col-span-7">
          <SectionHead
            title="航程"
            note={
              tasksState.loading
                ? '正在读取…'
                : tasksState.error
                  ? tasksState.error
                  : `共 ${tasksState.tasks.length} 个任务，全部来自真实练习`
            }
            action={
              tasksState.tasks.length > 0 ? (
                <QuietLink to="/reports">全部回响 →</QuietLink>
              ) : undefined
            }
          />
          <div className="mt-5">
            {tasksState.loading ? (
              <p className="flex items-center gap-2 text-sm text-ink-soft">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                正在汇聚你的航程…
              </p>
            ) : tasksState.tasks.length === 0 ? (
              <p className="text-sm leading-relaxed text-ink-soft">
                这里还没有航迹。完成第一次问澜训练后，每一次起笔与收束都会在此留痕。
              </p>
            ) : (
              <TimelineList>
                {tasksState.tasks.slice(0, 6).map((task, index) => (
                  <TimelineRow
                    key={task.id}
                    tone={taskTone(task.status)}
                    last={index === Math.min(6, tasksState.tasks.length) - 1}
                    title={
                      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        {task.position}
                        <span className="text-xs font-normal text-ink-soft">
                          {difficultyLabel(task.difficulty)}
                        </span>
                      </span>
                    }
                    meta={`${formatDateTime(task.created_at)} · ${STATUS_LABELS[task.status]}`}
                    action={
                      <span className="flex items-center gap-3">
                        {task.overall_score !== null ? (
                          <span className="text-lg font-bold text-ink-strong">
                            {task.overall_score.toFixed(1)}
                          </span>
                        ) : null}
                        {task.status === 'completed' ? (
                          <QuietLink to={`/reports/${task.id}`}>查看</QuietLink>
                        ) : null}
                      </span>
                    }
                  />
                ))}
              </TimelineList>
            )}
          </div>
        </div>

        <div className="lg:col-span-5">
          <SectionHead
            title="最近回响"
            note="已完成训练的评分报告"
            action={<QuietLink to="/skills">观己星图 →</QuietLink>}
          />
          <div className="mt-2">
            {tasksState.loading ? (
              <p className="flex items-center gap-2 text-sm text-ink-soft">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                正在读取…
              </p>
            ) : completed.length === 0 ? (
              <p className="text-sm leading-relaxed text-ink-soft">
                暂无评分报告。完成一次完整问澜训练后，报告会带着证据与建议在这里等你。
              </p>
            ) : (
              completed.slice(0, 5).map((task) => (
                <div
                  key={task.id}
                  className="flex items-center justify-between gap-4 border-b border-line/70 py-3.5 last:border-b-0"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[15px] font-semibold text-ink-strong">
                      {task.position}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      {formatDateTime(task.updated_at)} · {difficultyLabel(task.difficulty)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-xl font-bold text-ink-strong">
                      {task.overall_score?.toFixed(1)}
                    </span>
                    <QuietLink to={`/reports/${task.id}`}>查看</QuietLink>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* ── 第四层：澜迹 —— 统计带 + 热力图直接融入页面 ─────────────── */}
      <section className="mt-14" aria-label="成长轨迹">
        <SectionHead
          title="澜迹"
          note="每一次练习、复习与里程碑，都留下一格涟漪"
        />
        <div className="mt-6">
          <GrowthSection averageScore={averageScore} completedCount={completed.length} />
        </div>
      </section>
    </PageTransition>
  )
}

function ButtonStart() {
  return (
    <ButtonLink to="/interview/new" size="lg" className="self-start sm:self-auto">
      <PlusCircle className="h-4 w-4" aria-hidden="true" />
      开始问澜
    </ButtonLink>
  )
}

const KIND_LABELS: Record<string, string> = {
  interview: '问澜',
  challenge: '度衡',
  expression: '听澜',
  mistake: '回澜',
}

function heatmapColor(count: number): string {
  if (count <= 0) return 'bg-slate-100'
  if (count === 1) return 'bg-brand-600/25'
  if (count === 2) return 'bg-brand-600/50'
  if (count <= 4) return 'bg-brand-600/75'
  return 'bg-brand-600'
}

/** 成长轨迹：统计带 + 年度热力图，全部直接融入页面（无卡片边框）。 */
function GrowthSection({
  averageScore,
  completedCount,
}: {
  averageScore: number | null
  completedCount: number
}) {
  const [heatmap, setHeatmap] = useState<GrowthHeatmap | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .getGrowthHeatmap()
      .then((data) => {
        if (active) setHeatmap(data)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof ApiError ? err.message : '加载成长轨迹失败')
      })
    return () => {
      active = false
    }
  }, [])

  if (error) {
    return <p className="text-sm text-ink-soft">{error}</p>
  }

  if (!heatmap) {
    return (
      <p className="flex items-center gap-2 text-sm text-ink-soft">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        正在汇聚你的成长轨迹…
      </p>
    )
  }

  // 组装 GitHub 风格的周列网格：从当年第一周的周一起，到年末为止
  const byDate = new Map(heatmap.days.map((day) => [day.date, day]))
  const year = heatmap.year
  const firstDay = new Date(Date.UTC(year, 0, 1))
  const weekdayOfJan1 = (firstDay.getUTCDay() + 6) % 7
  const gridStart = new Date(Date.UTC(year, 0, 1 - weekdayOfJan1))
  const endMs = Date.UTC(year, 11, 31)
  const weeks: { date: string; count: number; kinds: string[]; inYear: boolean }[][] = []
  for (let cursor = gridStart; cursor.getTime() <= endMs; ) {
    const week: { date: string; count: number; kinds: string[]; inYear: boolean }[] = []
    for (let d = 0; d < 7; d++) {
      const day = new Date(cursor)
      day.setUTCDate(day.getUTCDate() + d)
      const iso = day.toISOString().slice(0, 10)
      const inYear = day.getUTCFullYear() === year
      const entry = byDate.get(iso)
      week.push({ date: iso, count: entry?.count ?? 0, kinds: entry?.kinds ?? [], inYear })
    }
    weeks.push(week)
    cursor.setUTCDate(cursor.getUTCDate() + 7)
  }
  const totalActive = heatmap.days.length
  const totalCount = heatmap.days.reduce((sum, day) => sum + day.count, 0)

  return (
    <div>
      <StatStrip
        items={[
          {
            label: '平均总分',
            value: averageScore !== null ? averageScore.toFixed(1) : '—',
            hint: averageScore !== null ? `${completedCount} 次完成训练` : '完成首次训练后显示',
          },
          {
            label: '活跃日',
            value: totalActive,
            hint: `${year} 年有行动的日子`,
          },
          {
            label: '累计行动',
            value: totalCount,
            hint: '练习、复习与里程碑',
          },
          {
            label: '连续行动',
            value: `${heatmap.streak.current} 天`,
            hint: `最长 ${heatmap.streak.longest} 天`,
          },
        ]}
      />
        <div className="mt-8 overflow-x-auto pb-2">
          <div className="flex gap-1" role="img" aria-label={`${year} 年成长热力图`}>
            {weeks.map((week, weekIndex) => (
              <div key={weekIndex} className="flex flex-col gap-1">
                {week.map((day) => (
                  <span
                    key={day.date}
                    title={
                      day.count > 0
                        ? `${day.date}：${day.count} 次（${day.kinds
                            .map((kind) => KIND_LABELS[kind] ?? kind)
                            .join('、')}）`
                        : day.date
                    }
                    className={
                      'h-3 w-3 rounded-[3px] ' +
                      (day.inYear ? heatmapColor(day.count) : 'bg-transparent')
                    }
                  />
                ))}
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-[11px] text-ink-soft">
            <Flame className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
            少
            <span className="h-3 w-3 rounded-[3px] bg-slate-100" />
            <span className="h-3 w-3 rounded-[3px] bg-brand-600/25" />
            <span className="h-3 w-3 rounded-[3px] bg-brand-600/50" />
            <span className="h-3 w-3 rounded-[3px] bg-brand-600/75" />
            <span className="h-3 w-3 rounded-[3px] bg-brand-600" />
            多
          </div>
        </div>
        {/* 本周澜记：AI 短评 + 近 7 日真实聚合 */}
        <WeeklyNote />
      </div>
    )
  }

/** 本周澜记：近 7 日真实活动聚合 + AI 短评（不可用时如实降级）。 */
function WeeklyNote() {
  const [report, setReport] = useState<WeeklyReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .getWeeklyReport()
      .then((data) => {
        if (active) setReport(data)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof ApiError ? err.message : '加载周记失败')
      })
    return () => {
      active = false
    }
  }, [])

  if (error) return null
  if (!report) {
    return (
      <p className="mt-8 flex items-center gap-2 text-sm text-ink-soft">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        正在整理本周澜记…
      </p>
    )
  }

  const totalWeek = report.days.reduce((sum, day) => sum + day.count, 0)
  const kindText = Object.entries(report.totals)
    .map(([kind, count]) => `${KIND_LABELS[kind] ?? kind} ${count} 次`)
    .join(' · ')

  return (
    <div className="mt-10" id="weekly">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-base font-semibold text-ink-strong">本周澜记</h3>
        <p className="text-xs text-ink-soft">
          {report.week_start} 至 {report.week_end} · {totalWeek} 次行动 · 连续{' '}
          {report.streak_current} 天
        </p>
      </div>
      {totalWeek === 0 ? (
        <p className="mt-3 text-sm leading-relaxed text-ink-soft">
          这一周还没有留下行动记录。轻舟已备好，随时可以启程。
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm leading-relaxed text-ink">{kindText || '本周有行动记录'}</p>
          {report.ai_note ? (
            <blockquote className="mt-4 border-l-2 border-brand-600/50 pl-4 text-sm leading-relaxed text-ink">
              {report.ai_note}
              <span className="mt-1.5 block text-xs text-ink-soft/80">
                —— 由 {report.average_score !== null ? `周均分 ${report.average_score.toFixed(1)} 的` : '本周'}真实数据写就
              </span>
            </blockquote>
          ) : (
            <p className="mt-4 text-xs text-ink-soft/85">
              AI 短评暂不可用，以上数据依旧全部真实。
            </p>
          )}
        </>
      )}
    </div>
  )
}
