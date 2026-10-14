import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronDown,
  FileText,
  Loader2,
  MessageCircleQuestion,
  Send,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { PageBackground } from '../components/PageBackground'
import { PointerGlow } from '../components/PointerGlow'
import { LogoMark } from '../components/LogoMark'
import { AurelLoading, AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { Badge } from '../components/ui/Badge'
import { Button, ButtonLink } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { difficultyLabel, languageLabel, QUESTION_CATEGORY_LABELS } from '../lib/format'
import { cn } from '../lib/cn'
import type { QuestionOut, TaskDetail } from '../types'

const ANSWER_MAX_LENGTH = 4000

type Phase = 'loading' | 'answering' | 'submitting' | 'finishing' | 'error'

function orderedQuestions(task: TaskDetail): QuestionOut[] {
  return [...task.questions].sort((a, b) => {
    if (a.order_index !== b.order_index) return a.order_index - b.order_index
    const aMain = a.type === 'main' ? 0 : 1
    const bMain = b.type === 'main' ? 0 : 1
    return aMain - bMain || a.id - b.id
  })
}

/** 问澜题元数据展示：题型 / 能力维度 / 考查目标 / 评分要点（旧任务无此数据时不渲染） */
function QuestionMeta({ question }: { question: QuestionOut }) {
  const rubric = question.rubric ?? []
  const hasMeta =
    Boolean(question.category) ||
    Boolean(question.dimension) ||
    Boolean(question.goal) ||
    rubric.length > 0
  if (!hasMeta) return null
  return (
    <div className="mt-3 space-y-2 rounded-lg border border-line bg-slate-50/70 px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {question.category ? (
          <Badge tone="brand">
            {QUESTION_CATEGORY_LABELS[question.category] ?? question.category}
          </Badge>
        ) : null}
        {question.dimension ? (
          <span className="text-xs text-ink-soft">能力维度：{question.dimension}</span>
        ) : null}
      </div>
      {question.goal ? (
        <p className="text-xs leading-relaxed text-ink-soft">考查目标：{question.goal}</p>
      ) : null}
      {rubric.length > 0 ? (
        <div>
          <p className="text-xs font-medium text-ink-strong">评分要点</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {rubric.map((item, index) => (
              <li key={index} className="text-xs leading-relaxed text-ink-soft">
                {item}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export default function InterviewSessionPage() {
  const { id } = useParams()
  const taskId = Number(id)
  const navigate = useNavigate()

  const [task, setTask] = useState<TaskDetail | null>(null)
  const [phase, setPhase] = useState<Phase>('loading')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<QuestionOut | null>(null)
  const [answer, setAnswer] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  // 提交/鉴析链路的统一任务状态：真实计时、终态即时结束动画
  const busy = useAsyncTask({ debugLabel: 'interview-submit' })

  const applyTaskDetail = useCallback((detail: TaskDetail) => {
    setTask(detail)
    setCurrentQuestion(detail.questions.find((q) => q.id === detail.current_question_id) ?? null)
    if (detail.status === 'failed') {
      setPhase('error')
      setLoadError(detail.error_message ?? '任务处于失败状态')
    } else if (detail.status === 'completed') {
      setPhase('error')
      setLoadError(null)
    } else {
      setPhase('answering')
    }
  }, [])

  const validId = Number.isFinite(taskId) && taskId > 0

  useEffect(() => {
    if (!validId) {
      return
    }
    let cancelled = false
    api.getInterview(taskId).then(
      (detail) => {
        if (!cancelled) {
          applyTaskDetail(detail)
        }
      },
      (error) => {
        if (!cancelled) {
          setPhase('error')
          setLoadError(error instanceof ApiError ? error.message : '加载任务失败')
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [applyTaskDetail, validId, taskId])

  async function reloadTask() {
    setPhase('loading')
    try {
      const detail = await api.getInterview(taskId)
      applyTaskDetail(detail)
    } catch (error) {
      setPhase('error')
      setLoadError(error instanceof ApiError ? error.message : '加载任务失败')
    }
  }

  const sorted = useMemo(() => (task ? orderedQuestions(task) : []), [task])
  const answeredCount = sorted.filter((q) => q.answer !== null).length
  const mainProgress = useMemo(() => {
    if (!currentQuestion || !task) return 0
    if (currentQuestion.type === 'follow_up') return currentQuestion.order_index
    return Math.max(0, currentQuestion.order_index - 1)
  }, [currentQuestion, task])

  async function handleSubmit() {
    if (!currentQuestion || !answer.trim()) {
      setActionError('请先输入回答内容')
      return
    }
    setPhase('submitting')
    setActionError(null)
    await busy.run(async () => {
      try {
        const response = await api.submitAnswer(taskId, currentQuestion.id, answer.trim())
        if (response.all_answered) {
          setCurrentQuestion(null)
          setPhase('finishing')
          // 报告生成失败时保持 finishing 态：由「观澜鉴析」面板展示失败与重试
          await api.finishInterview(taskId)
          navigate(`/reports/${taskId}`)
          return
        }
        setCurrentQuestion(response.next_question)
        setAnswer('')
        setPhase('answering')
      } catch (error) {
        // 回答已保存，但追问/下一步决策失败 → 允许重试
        setPhase('answering')
        setActionError(
          error instanceof ApiError ? error.message : '提交回答失败，请重试',
        )
        // 回答已保存，但追问/下一步决策失败：静默刷新任务状态，提供重试入口
        api.getInterview(taskId).then(applyTaskDetail, () => undefined)
      }
    })
  }

  /** 报告生成失败后的重试：仅重试鉴析环节（回答已保存，不会重复创建）。 */
  async function handleRetryFinish() {
    setPhase('finishing')
    await busy.run(async () => {
      await api.finishInterview(taskId)
      navigate(`/reports/${taskId}`)
    })
  }

  async function handleRetryNext() {
    setPhase('submitting')
    setActionError(null)
    await busy.run(async () => {
      try {
        const response = await api.resolveNext(taskId)
        if (response.all_answered) {
          setPhase('finishing')
          await api.finishInterview(taskId)
          navigate(`/reports/${taskId}`)
          return
        }
        setCurrentQuestion(response.next_question)
        setPhase('answering')
      } catch (error) {
        setPhase('answering')
        setActionError(error instanceof ApiError ? error.message : '重试失败')
      }
    })
  }

  if (phase === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-4">
        <div className="w-full max-w-sm">
          <AurelLoading scene="common.page" size="md" layout="row" className="rounded-2xl border border-line/70 bg-white/70 px-5 py-4" />
        </div>
      </div>
    )
  }

  if (!task || !validId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-4">
        <Card className="max-w-md">
          <CardBody className="pt-8 text-center">
            <AlertTriangle className="mx-auto h-10 w-10 text-amber-500" aria-hidden="true" />
            <h1 className="mt-4 text-lg font-semibold text-ink-strong">无法加载面试任务</h1>
            <p className="mt-2 text-sm text-ink-soft">
              {!validId ? '无效的任务 ID' : (loadError ?? '任务不存在')}
            </p>
            <ButtonLink to="/app" variant="secondary" size="sm" className="mt-6">
              返回行舟
            </ButtonLink>
          </CardBody>
        </Card>
      </div>
    )
  }

  const isFinished = task.status === 'completed'

  return (
    <div className="relative min-h-screen bg-surface">
      <PageBackground scene="workspace" />
      <PointerGlow intensity="whisper" />
      {/* 顶栏：无底色，直接置于雪景之上 */}
      <header className="relative">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              to="/app"
              className="inline-flex items-center gap-1.5 rounded-md px-1 py-1 text-sm text-ink-soft transition-colors hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">返回行舟</span>
            </Link>
            <span className="hidden h-5 w-px bg-line sm:block" aria-hidden="true" />
            <div className="flex min-w-0 items-center gap-2.5">
              <LogoMark size={28} />
              <span className="truncate text-sm font-semibold text-ink-strong">
                {task.position} · 模拟面试
              </span>
              <Badge tone="brand" className="hidden sm:inline-flex">
                {difficultyLabel(task.difficulty)} · {languageLabel(task.language)}
              </Badge>
            </div>
          </div>
          {isFinished ? (
            <ButtonLink to={`/reports/${taskId}`} size="sm">
              <FileText className="h-4 w-4" aria-hidden="true" />
              查看报告
            </ButtonLink>
          ) : currentQuestion ? (
            currentQuestion.type === 'follow_up' ? (
              <Badge tone="accent">第 {currentQuestion.order_index} 题追问</Badge>
            ) : (
              <Badge tone="accent">
                第 {currentQuestion.order_index} / {task.question_count} 题
              </Badge>
            )
          ) : (
            <Badge tone="accent">全部题目已回答</Badge>
          )}
        </div>
        {/* 主问题进度条 */}
        <div className="h-1 w-full bg-slate-100">
          <div
            className="h-full bg-brand-600 transition-[width] duration-300 ease-out"
            style={{ width: `${(mainProgress / task.question_count) * 100}%` }}
          />
        </div>
      </header>

      {/* 工作区玻璃画布：与行舟布局一致的冰白玻璃承载内容 */}
      <div className="glass-surface glass-workspace mx-3 mb-12 mt-6 rounded-3xl sm:mx-5 lg:mx-8">
      <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        {isFinished ? (
          <Card>
            <CardBody className="pt-8 text-center">
              <Check className="mx-auto h-12 w-12 text-accent" aria-hidden="true" />
              <h1 className="mt-4 text-xl font-bold text-ink-strong">面试已完成</h1>
              <p className="mt-2 text-sm text-ink-soft">评分报告已生成。</p>
              <ButtonLink to={`/reports/${taskId}`} className="mt-6">
                <FileText className="h-4 w-4" aria-hidden="true" />
                查看评分报告
              </ButtonLink>
            </CardBody>
          </Card>
        ) : phase === 'error' && loadError ? (
          <Card>
            <CardBody className="pt-8 text-center">
              <AlertTriangle className="mx-auto h-10 w-10 text-amber-500" aria-hidden="true" />
              <h1 className="mt-4 text-lg font-semibold text-ink-strong">任务遇到问题</h1>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">{loadError}</p>
              <div className="mt-6 flex justify-center gap-3">
                <Button variant="secondary" size="sm" onClick={() => void reloadTask()}>
                  重新加载
                </Button>
                <ButtonLink to="/interview/new" size="sm">
                  创建新任务
                </ButtonLink>
              </div>
            </CardBody>
          </Card>
        ) : (
          <div className="space-y-5">
            {/* 当前问题 */}
            {phase === 'finishing' ? (
              <div key="finishing" className="page-enter">
                <AurelTaskStatus
                  title="观澜鉴析"
                  scene="wenlan.report"
                  status={busy.status === 'idle' ? 'loading' : busy.status}
                  error={busy.error}
                  elapsedMs={busy.elapsedMs}
                  onRetry={handleRetryFinish}
                />
                <p className="mt-3 text-center text-xs text-ink-soft">
                  观其微澜，鉴其远势——评鉴将成
                </p>
              </div>
            ) : currentQuestion ? (
              <div key={currentQuestion.id} className="card-enter">
                  <Card>
                    <CardHeader
                      title={
                        currentQuestion.type === 'follow_up'
                          ? `面试官追问`
                          : `问题 ${currentQuestion.order_index}`
                      }
                      description={
                        currentQuestion.type === 'follow_up'
                          ? '基于你刚才的回答，面试官想了解更多'
                          : `建议使用${languageLabel(task.language)}作答，尽量结合真实经历`
                      }
                      action={
                        currentQuestion.type === 'follow_up' ? (
                          <Badge tone="accent" icon={<MessageCircleQuestion className="h-3 w-3" aria-hidden="true" />}>
                            追问
                          </Badge>
                        ) : undefined
                      }
                    />
                    <CardBody>
                      <p className="rounded-lg bg-surface px-5 py-4 text-base font-medium leading-relaxed text-ink-strong">
                        {currentQuestion.content}
                      </p>

                      <QuestionMeta question={currentQuestion} />

                      <div className="mt-5">
                        <label htmlFor="answer" className="mb-1.5 block text-sm font-medium text-ink-strong">
                          你的回答
                        </label>
                        <textarea
                          id="answer"
                          value={answer}
                          rows={7}
                          maxLength={ANSWER_MAX_LENGTH}
                          disabled={phase === 'submitting'}
                          placeholder="像真实面试一样作答：先给结论，再讲依据，最好带上具体例子。"
                          onChange={(event) => setAnswer(event.target.value)}
                          className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm leading-relaxed text-ink placeholder:text-slate-400 transition-colors focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25 disabled:bg-slate-50"
                        />
                        <div className="mt-1 flex items-center justify-between text-xs text-ink-soft">
                          <span>落笔之后，或有一问相随</span>
                          <span>
                            {answer.length}/{ANSWER_MAX_LENGTH}
                          </span>
                        </div>
                      </div>

                      {actionError ? (
                        <div
                          role="alert"
                          className="mt-4 flex flex-col gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <p className="text-sm text-red-700">{actionError}</p>
                          <Button variant="secondary" size="sm" onClick={handleRetryNext}>
                            重试生成下一步
                          </Button>
                        </div>
                      ) : null}

                      <div className="mt-5 flex justify-end">
                        <Button
                          onClick={handleSubmit}
                          disabled={phase === 'submitting' || !answer.trim()}
                        >
                          {phase === 'submitting' ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                              面试官凝思中…
                            </>
                          ) : (
                            <>
                              <Send className="h-4 w-4" aria-hidden="true" />
                              提交回答
                            </>
                          )}
                        </Button>
                      </div>

                      {/* 凝思等待期长任务面板：真实状态 + 已耗时（不虚构进度） */}
                      {phase === 'submitting' && busy.running ? (
                        <AurelTaskStatus
                          className="mt-5"
                          title="面试官凝思"
                          scene="wenlan.followup"
                          status={busy.status}
                          elapsedMs={busy.elapsedMs}
                        />
                      ) : null}
                    </CardBody>
                  </Card>
              </div>
            ) : null}

            {/* 已回答记录 */}
            {answeredCount > 0 ? (
              <Card>
                <button
                  type="button"
                  onClick={() => setShowHistory((prev) => !prev)}
                  className="flex w-full items-center justify-between px-6 py-4 text-left"
                  aria-expanded={showHistory}
                >
                  <span className="text-sm font-semibold text-ink-strong">
                    已回答记录（{answeredCount} 条）
                  </span>
                  <ChevronDown
                    className={cn(
                      'h-4 w-4 text-ink-soft transition-transform',
                      showHistory && 'rotate-180',
                    )}
                    aria-hidden="true"
                  />
                </button>
                {showHistory ? (
                  <CardBody className="space-y-4 border-t border-line pt-5">
                    {sorted
                      .filter((q) => q.answer !== null)
                      .map((q) => (
                        <div key={q.id} className="rounded-lg border border-line bg-surface p-4">
                          <div className="flex items-center gap-2">
                            <Badge tone={q.type === 'follow_up' ? 'accent' : 'neutral'}>
                              {q.type === 'follow_up' ? '追问' : `问题 ${q.order_index}`}
                            </Badge>
                          </div>
                          <p className="mt-2 text-sm font-medium text-ink-strong">{q.content}</p>
                          <QuestionMeta question={q} />
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
                            {q.answer}
                          </p>
                        </div>
                      ))}
                  </CardBody>
                ) : null}
              </Card>
            ) : null}
          </div>
        )}
      </main>
      </div>
    </div>
  )
}
