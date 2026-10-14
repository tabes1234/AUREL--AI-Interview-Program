import { Hourglass, Loader2, PlayCircle, RotateCcw, Scale, Swords } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { PageHeading, SectionHead } from '../components/editorial/Editorial'
import { PageTransition } from '../components/motion/PageTransition'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { RadioCardGroup, TextField } from '../components/ui/Field'
import { difficultyLabel, formatDateTime } from '../lib/format'
import type { ChallengeOut } from '../types'

const DIFFICULTY_OPTIONS = [
  { value: 'basic', label: '基础筑基', description: '稳住基本盘，题目偏基础' },
  { value: 'intermediate', label: '进阶砥砺', description: '常规面试强度' },
  { value: 'advanced', label: '高压淬炼', description: '追问深、时间紧' },
]

const DURATION_CHOICES = [5, 10, 15, 20, 30]
const QUESTION_COUNT_CHOICES = [3, 4, 5, 6, 7, 8]

function formatCountdown(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

/** 度衡：Editorial 编辑式布局 —— 限时作答渐变区（唯一强调区）+ 细线历史行。 */
export default function ChallengesPage() {
  const [position, setPosition] = useState('')
  const [difficulty, setDifficulty] = useState('intermediate')
  const [questionCount, setQuestionCount] = useState(5)
  const [durationMinutes, setDurationMinutes] = useState(15)
  // 出题与评分：统一任务状态机（真实计时、防重复提交）
  const createTask = useAsyncTask({ debugLabel: 'challenge-create' })
  const creating = createTask.running
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const [activeRun, setActiveRun] = useState<ChallengeOut | null>(null)
  const [activeFinished, setActiveFinished] = useState<ChallengeOut | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [remaining, setRemaining] = useState(0)
  const [starting, setStarting] = useState(false)
  const submitTask = useAsyncTask({ debugLabel: 'challenge-submit' })
  const submitting = submitTask.running
  const [history, setHistory] = useState<ChallengeOut[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const submittedRef = useRef(false)

  const refreshHistory = useCallback(async () => {
    try {
      const items = await api.listChallenges()
      setHistory(items.filter((item) => item.status === 'completed' || item.status === 'failed'))
      return items
    } catch {
      return []
    }
  }, [])

  useEffect(() => {
    let active = true
    api
      .listChallenges()
      .then((items) => {
        if (!active) return
        setHistory(items.filter((item) => item.status === 'completed' || item.status === 'failed'))
        const pending = items.find(
          (item) => item.status === 'created' || item.status === 'in_progress',
        )
        if (pending) {
          setActiveRun(pending)
          if (pending.status === 'in_progress' && pending.remaining_seconds != null) {
            setRemaining(pending.remaining_seconds)
          }
        }
      })
      .catch(() => {
        // 历史加载失败不阻塞新建流程，进入页面后可见
      })
      .finally(() => {
        if (active) setLoadingHistory(false)
      })
    return () => {
      active = false
    }
  }, [])

  // 本地倒计时（每秒递减；初始值来自服务端 remaining_seconds，避免时钟漂移）
  useEffect(() => {
    if (activeRun?.status !== 'in_progress') return
    const timer = window.setInterval(() => {
      setRemaining((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [activeRun?.status])

  async function handleCreate() {
    const name = position.trim()
    if (name.length < 2) {
      setFormError('请填写挑战岗位（至少 2 个字）')
      return
    }
    setFormError(null)
    setError(null)
    await createTask.run(async () => {
      const run = await api.createChallenge({
        position: name,
        difficulty,
        questionCount,
        durationMinutes,
      })
      setActiveRun(run)
      setAnswers({})
      submittedRef.current = false
    }, { timeoutMs: 180000 })
    if (createTask.error) {
      setFormError(createTask.error)
    }
  }

  async function handleStart() {
    if (!activeRun) return
    setStarting(true)
    setError(null)
    try {
      const started = await api.startChallenge(activeRun.id)
      setActiveRun(started)
      setRemaining(started.remaining_seconds ?? started.duration_minutes * 60)
      submittedRef.current = false
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '开始失败')
    } finally {
      setStarting(false)
    }
  }

  const submitRun = useCallback(
    async (currentAnswers: Record<number, string>) => {
      if (!activeRun || submittedRef.current) return
      submittedRef.current = true
      setError(null)
      await submitTask.run(async () => {
        const payload = activeRun.questions.map((question) => ({
          order_index: question.order_index,
          answer: currentAnswers[question.order_index] ?? '',
        }))
        const finished = await api.submitChallenge(activeRun.id, payload)
        setActiveRun(null)
        setAnswers({})
        await refreshHistory()
        if (finished.status === 'failed') {
          setError(finished.error_message ?? '本次挑战评分未完成，已如实记录。')
        } else {
          setActiveFinished(finished)
        }
      }, { timeoutMs: 240000 })
      if (submitTask.error) {
        submittedRef.current = false
        setError(submitTask.error)
      }
    },
    [activeRun, refreshHistory, submitTask],
  )

  // 倒计时归零自动交卷（延时回调触发；服务端仍按服务端时钟如实判定超时）
  useEffect(() => {
    if (activeRun?.status === 'in_progress' && remaining === 0 && !submitting) {
      const timer = window.setTimeout(() => void submitRun(answers), 0)
      return () => window.clearTimeout(timer)
    }
  }, [activeRun?.status, remaining, submitting, submitRun, answers])

  async function openHistoryDetail(runId: number) {
    try {
      const detail = await api.getChallenge(runId)
      if (detail.status === 'completed' || detail.status === 'failed') {
        setActiveFinished(detail)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '加载历史挑战失败')
    }
  }

  function resetToSetup() {
    setActiveRun(null)
    setActiveFinished(null)
    setAnswers({})
    submittedRef.current = false
  }

  const lowTime = activeRun?.status === 'in_progress' && remaining <= 60

  return (
    <PageTransition>
      <PageHeading
        kicker="洞察"
        title="度衡"
        subtitle="衡者，所以权轻重也。限时作答，服务端计时判卷——超时与否，以钟为准，不作粉饰。"
      />

      {error ? (
        <p
          role="alert"
          className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </p>
      ) : null}

      {/* 已完成的挑战结果：开放式章节，大分数直接融入页面 */}
      {activeFinished ? (
        <section className="mt-10" aria-label="挑战结果">
          <SectionHead
            title={`${activeFinished.position} · 挑战结果`}
            note={`${formatDateTime(activeFinished.submitted_at ?? activeFinished.created_at)}${
              activeFinished.overtime ? ' · 超时提交（服务端如实标记）' : ' · 限时之内完成'
            }`}
            action={
              <Button variant="ghost" size="sm" onClick={resetToSetup}>
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                再来一局
              </Button>
            }
          />
          {activeFinished.status === 'completed' && activeFinished.result ? (
            <>
              <div className="mt-6 flex flex-wrap items-baseline gap-4">
                <span className="text-5xl font-bold leading-none tracking-tight text-ink-strong">
                  {activeFinished.overall_score?.toFixed(1)}
                </span>
                <span className="text-sm text-ink-soft">总分（0–10，维度均分）</span>
                {activeFinished.overtime ? <Badge tone="preview">超时</Badge> : null}
              </div>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-ink">
                {activeFinished.result.summary}
              </p>
              <div className="mt-8 divide-y divide-line/70">
                {activeFinished.result.dimensions.map((dimension) => (
                  <div key={dimension.name} className="py-4 first:pt-0">
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-[15px] font-semibold text-ink-strong">
                        {dimension.name}
                      </span>
                      <span className="text-lg font-bold text-ink-strong">
                        {dimension.score.toFixed(1)}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-brand-600"
                        style={{ width: `${Math.min(dimension.score * 10, 100)}%` }}
                      />
                    </div>
                    {dimension.rationale ? (
                      <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                        {dimension.rationale}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
              {activeFinished.result.improvements.length > 0 ? (
                <div className="mt-8">
                  <h3 className="text-sm font-bold text-ink-strong">下一步精进</h3>
                  <ul className="mt-2 divide-y divide-line/70">
                    {activeFinished.result.improvements.map((item) => (
                      <li key={item.title} className="py-3 text-sm leading-relaxed text-ink">
                        <strong>{item.title}</strong>
                        {item.detail ? `——${item.detail}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : (
            <p className="mt-4 text-sm text-ink-soft">
              {activeFinished.error_message ?? '该局未能完成评分。'}
            </p>
          )}
        </section>
      ) : null}

      {/* 进行中 / 待开始：页面唯一的浅蓝渐变强调区 */}
      {activeRun ? (
        <section className="mt-10" aria-label="限时作答">
          <div className="relative overflow-hidden rounded-xl border border-ripple/40 bg-gradient-to-br from-mist via-white to-shallow/60 px-6 py-6 sm:px-8 sm:py-8">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-14 -top-16 h-44 w-44 rounded-full bg-shallow/50 blur-2xl"
            />
            <div className="relative flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold tracking-[0.28em] text-brand-600/85">
                  限时作答
                </p>
                <h2 className="mt-2 text-2xl font-bold tracking-tight text-ink-strong">
                  {activeRun.position} · {activeRun.question_count} 题
                </h2>
                <p className="mt-1 text-sm text-ink-soft">
                  限时 {activeRun.duration_minutes} 分钟 · {difficultyLabel(activeRun.difficulty)}
                </p>
              </div>
              {activeRun.status === 'in_progress' ? (
                <span
                  className={
                    'relative font-mono text-3xl font-bold tabular-nums ' +
                    (lowTime ? 'text-red-600' : 'text-brand-700')
                  }
                  aria-label={`剩余时间 ${formatCountdown(remaining)}`}
                >
                  {formatCountdown(remaining)}
                </span>
              ) : (
                <Badge tone="brand">待开始</Badge>
              )}
            </div>

            <div className="relative mt-6">
              {activeRun.status === 'created' ? (
                <div className="flex flex-col items-start gap-3">
                  <p className="max-w-xl text-sm leading-relaxed text-ink">
                    题目已经备好。点「开始作答」后服务端开始计时，到点未交卷会如实标记超时。
                  </p>
                  <Button onClick={() => void handleStart()} disabled={starting}>
                    {starting ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <PlayCircle className="h-4 w-4" aria-hidden="true" />
                    )}
                    {starting ? '正在计时…' : '开始作答'}
                  </Button>
                </div>
              ) : (
                <>
                  <ol className="divide-y divide-line/70">
                    {activeRun.questions.map((question) => (
                      <li key={question.order_index} className="py-4 first:pt-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone="neutral">第 {question.order_index} 题</Badge>
                          <Badge tone="brand">{question.category}</Badge>
                          {question.dimension ? (
                            <Badge tone="accent">{question.dimension}</Badge>
                          ) : null}
                        </div>
                        <p className="mt-2.5 text-sm font-medium leading-relaxed text-ink-strong">
                          {question.content}
                        </p>
                        <textarea
                          value={answers[question.order_index] ?? ''}
                          onChange={(event) =>
                            setAnswers((prev) => ({
                              ...prev,
                              [question.order_index]: event.target.value,
                            }))
                          }
                          rows={3}
                          maxLength={4000}
                          placeholder="在时间之内写下你的回答……"
                          className="mt-3 w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                        />
                      </li>
                    ))}
                  </ol>
                  <div className="mt-4 flex items-center gap-3">
                    <Button onClick={() => void submitRun(answers)} disabled={submitting}>
                      {submitting ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Swords className="h-4 w-4" aria-hidden="true" />
                      )}
                      {submitting ? '正在交卷评分…' : remaining === 0 ? '时间已到，交卷' : '交卷'}
                    </Button>
                    {remaining === 0 ? (
                      <span className="flex items-center gap-1.5 text-xs text-amber-600">
                        <Hourglass className="h-3.5 w-3.5" aria-hidden="true" />
                        已超时，服务端将如实记录。
                      </span>
                    ) : null}
                  </div>

                  {submitTask.running ? (
                    <AurelTaskStatus
                      className="mt-4"
                      title="挑战评分"
                      scene="ai.organizing"
                      status={submitTask.status}
                      elapsedMs={submitTask.elapsedMs}
                    />
                  ) : null}
                </>
              )}
            </div>
          </div>
        </section>
      ) : (
        /* 新建挑战：表单轻面板 */
        <section className="mt-10" aria-label="发起挑战">
          <SectionHead title="发起一场挑战" note="选定岗位与强度，题目即时生成，全程服务端计时" />
          <div className="mt-4 rounded-xl border border-line bg-white px-6 py-6 sm:px-8">
            <div className="space-y-5">
              <TextField
                label="挑战岗位"
                required
                value={position}
                onChange={setPosition}
                placeholder="例如：产品经理"
                maxLength={60}
              />
              <RadioCardGroup
                legend="强度"
                name="challenge-difficulty"
                options={DIFFICULTY_OPTIONS}
                value={difficulty}
                onChange={setDifficulty}
              />
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <p className="mb-1.5 text-sm font-medium text-ink-strong">题量</p>
                  <div className="flex flex-wrap gap-2">
                    {QUESTION_COUNT_CHOICES.map((count) => (
                      <button
                        key={count}
                        type="button"
                        onClick={() => setQuestionCount(count)}
                        className={
                          'h-9 w-11 rounded-lg border text-sm font-medium transition-colors ' +
                          (questionCount === count
                            ? 'border-brand-600 bg-brand-50 text-brand-700 ring-1 ring-brand-600/30'
                            : 'border-slate-300 bg-white text-ink-soft hover:border-brand-600/50')
                        }
                        aria-pressed={questionCount === count}
                      >
                        {count}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-sm font-medium text-ink-strong">时长（分钟）</p>
                  <div className="flex flex-wrap gap-2">
                    {DURATION_CHOICES.map((minutes) => (
                      <button
                        key={minutes}
                        type="button"
                        onClick={() => setDurationMinutes(minutes)}
                        className={
                          'h-9 rounded-lg border px-3.5 text-sm font-medium transition-colors ' +
                          (durationMinutes === minutes
                            ? 'border-brand-600 bg-brand-50 text-brand-700 ring-1 ring-brand-600/30'
                            : 'border-slate-300 bg-white text-ink-soft hover:border-brand-600/50')
                        }
                        aria-pressed={durationMinutes === minutes}
                      >
                        {minutes}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              {formError ? (
                <p role="alert" className="text-sm text-red-600">
                  {formError}
                </p>
              ) : null}
              <Button onClick={() => void handleCreate()} disabled={creating}>
                {creating ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Scale className="h-4 w-4" aria-hidden="true" />
                )}
                {creating ? '正在出题…' : '生成挑战'}
              </Button>

              {createTask.running ? (
                <AurelTaskStatus
                  title="限时挑战出题"
                  scene="ai.start"
                  status={createTask.status}
                  elapsedMs={createTask.elapsedMs}
                />
              ) : null}
            </div>
          </div>
        </section>
      )}

      {/* 往期挑战：细线行列表，无卡片 */}
      <section className="mt-12" aria-label="往期挑战">
        <SectionHead title="往期挑战" note="每一次限时之内的自我较量" />
        <div className="mt-2">
          {loadingHistory ? (
            <p className="flex items-center gap-2 py-4 text-sm text-ink-soft">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              正在读取历史…
            </p>
          ) : history.length === 0 ? (
            <p className="py-6 text-sm leading-relaxed text-ink-soft">
              还没有挑战记录。发起第一场限时挑战，看看时间压力下的自己。
            </p>
          ) : (
            <ul className="divide-y divide-line/70">
              {history.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => void openHistoryDetail(item.id)}
                    className="group -mx-3 flex w-[calc(100%+1.5rem)] items-center justify-between gap-3 px-3 py-3.5 text-left transition-colors duration-200 hover:bg-white/70"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-[15px] font-semibold text-ink-strong transition-colors group-hover:text-brand-700">
                        {item.position}
                      </p>
                      <p className="mt-0.5 text-xs text-ink-soft">
                        {formatDateTime(item.created_at)} · {difficultyLabel(item.difficulty)} ·{' '}
                        {item.question_count} 题 / {item.duration_minutes} 分钟
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {item.overtime ? <Badge tone="preview">超时</Badge> : null}
                      {item.overall_score !== null ? (
                        <span className="text-lg font-bold leading-none text-ink-strong">
                          {item.overall_score.toFixed(1)}
                        </span>
                      ) : (
                        <Badge tone="neutral">
                          {item.status === 'failed' ? '未完成' : item.status}
                        </Badge>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </PageTransition>
  )
}
