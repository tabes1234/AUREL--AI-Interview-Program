import {
  ArrowLeft,
  ArrowRight,
  FileText,
  Lightbulb,
  Loader2,
  NotebookPen,
  Quote,
  ShieldCheck,
  Star,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { PageHeading, SectionHead } from '../components/editorial/Editorial'
import { PageTransition } from '../components/motion/PageTransition'
import { Badge } from '../components/ui/Badge'
import { Button, ButtonLink } from '../components/ui/Button'
import { difficultyLabel, formatDateTime, languageLabel } from '../lib/format'
import type { QuestionOut, ReportOut, TaskDetail } from '../types'

function scoreTone(score: number): string {
  if (score >= 8) return 'bg-accent'
  if (score >= 6) return 'bg-brand-600'
  if (score >= 4) return 'bg-amber-500'
  return 'bg-red-500'
}

/** 面试报告：Editorial 编辑式布局 —— 开放章节 + 细线行，无卡片。 */
export default function ReportDetailPage() {
  const { id } = useParams()
  const taskId = Number(id)

  const [report, setReport] = useState<ReportOut | null>(null)
  const [task, setTask] = useState<TaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [collectedIds, setCollectedIds] = useState<Set<number>>(new Set())
  const [collectingId, setCollectingId] = useState<number | null>(null)
  const [collectFlash, setCollectFlash] = useState<string | null>(null)

  const validId = Number.isFinite(taskId) && taskId > 0

  useEffect(() => {
    if (!validId) {
      return
    }
    let cancelled = false
    Promise.all([api.getReport(taskId), api.getInterview(taskId)]).then(
      ([reportData, taskData]) => {
        if (!cancelled) {
          setReport(reportData)
          setTask(taskData)
          setLoading(false)
        }
      },
      (err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : '加载报告失败')
          setLoading(false)
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [validId, taskId])

  async function collectQuestion(question: QuestionOut) {
    if (collectingId !== null) return
    setCollectingId(question.id)
    setCollectFlash(null)
    try {
      await api.collectMistake({ questionId: question.id, myAnswer: question.answer ?? '' })
      setCollectedIds((prev) => new Set(prev).add(question.id))
      setCollectFlash('已收进回澜错题本，回澜会为你安排下一次重温。')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setCollectedIds((prev) => new Set(prev).add(question.id))
        setCollectFlash('这道题已经在错题本里了。')
      } else {
        setCollectFlash(err instanceof ApiError ? err.message : '收进错题本失败，请稍后再试')
      }
    } finally {
      setCollectingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-ink-soft">
          <Loader2 className="h-8 w-8 animate-spin text-brand-600" aria-hidden="true" />
          <p className="text-sm">正在加载报告…</p>
        </div>
      </div>
    )
  }

  if (!report || !validId) {
    return (
      <PageTransition>
        <div className="mx-auto max-w-lg py-20 text-center">
          <FileText className="mx-auto h-10 w-10 text-slate-400" aria-hidden="true" />
          <h1 className="mt-4 text-lg font-semibold text-ink-strong">报告不可用</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            {!validId ? '无效的报告 ID' : (error ?? '该任务尚未生成报告。完成一次完整面试后即可查看。')}
          </p>
          <ButtonLink to="/reports" variant="secondary" size="sm" className="mt-6">
            返回回响
          </ButtonLink>
        </div>
      </PageTransition>
    )
  }

  const answeredQuestions: QuestionOut[] = task
    ? [...task.questions]
        .filter((q) => q.answer !== null)
        .sort((a, b) => {
          if (a.order_index !== b.order_index) return a.order_index - b.order_index
          const aMain = a.type === 'main' ? 0 : 1
          const bMain = b.type === 'main' ? 0 : 1
          return aMain - bMain || a.id - b.id
        })
    : []

  return (
    <PageTransition>
      {/* 返回链接保持在页首上方 */}
      <Link
        to="/reports"
        className="inline-flex items-center gap-1.5 text-sm text-ink-soft transition-colors hover:text-brand-600"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        返回回响
      </Link>

      <PageHeading
        className="mt-4"
        kicker="回响 · 报告"
        title={report.position}
        subtitle={
          <span>
            {difficultyLabel(report.difficulty)} · {languageLabel(report.language)} · 完成于{' '}
            {formatDateTime(report.created_at)}
          </span>
        }
        actions={
          <ButtonLink to="/interview/new" variant="secondary" size="sm">
            再练一次
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </ButtonLink>
        }
      />

      {/* 总评 */}
      <section className="mt-12" aria-label="总评">
        <SectionHead
          title="总评"
          note={
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              由 {report.model_name} 生成 · 总分为四维平均
            </span>
          }
        />
        <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
          <motion.span
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', bounce: 0.4, duration: 0.6 }}
            className="flex h-24 w-24 shrink-0 items-center justify-center rounded-full ring-4 ring-brand-50"
          >
            <span className="text-3xl font-bold text-ink-strong">
              {report.overall_score.toFixed(1)}
            </span>
          </motion.span>
          <p className="max-w-2xl text-base leading-relaxed text-ink">{report.summary}</p>
        </div>
      </section>

      {/* 分项评分（T1 可解释）：细线行列表，证据与理由直接展开 */}
      <section className="mt-12" aria-label="分项评分">
        <SectionHead title="分项评分" note="每个维度都附有回答原文证据与评分理由" />
        <div className="mt-2 divide-y divide-line/70">
          {report.dimensions.map((dimension, index) => (
            <motion.div
              key={dimension.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.08, duration: 0.35, ease: 'easeOut' }}
              className="group py-5 first:pt-2"
            >
              <div className="flex items-baseline justify-between gap-4">
                <h3 className="text-[15px] font-semibold text-ink-strong transition-colors group-hover:text-brand-700">
                  {dimension.name}
                </h3>
                <span className="text-lg font-bold text-ink-strong">
                  {dimension.score.toFixed(1)}
                  <span className="ml-0.5 text-xs font-normal text-ink-soft"> / 10</span>
                </span>
              </div>
              <div
                className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
                role="img"
                aria-label={`${dimension.name} ${dimension.score} 分`}
              >
                <motion.div
                  className={scoreTone(dimension.score)}
                  initial={{ width: 0 }}
                  animate={{ width: `${dimension.score * 10}%` }}
                  transition={{ delay: 0.15 + index * 0.08, duration: 0.5, ease: 'easeOut' }}
                />
              </div>
              <div className="mt-3.5 space-y-2">
                <div className="flex gap-2">
                  <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
                  <p className="text-sm leading-relaxed text-ink">
                    <span className="font-medium text-brand-700">证据：</span>
                    {dimension.evidence}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
                  <p className="text-sm leading-relaxed text-ink-soft">
                    <span className="font-medium text-ink-strong">理由：</span>
                    {dimension.rationale}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <div className="mt-12 grid gap-10 lg:grid-cols-2">
        {/* 亮点 */}
        <section aria-label="亮点">
          <SectionHead title="亮点" note="回答中值得保持的地方" />
          <ul className="mt-4 space-y-3">
            {report.strengths.map((strength) => (
              <li key={strength} className="flex gap-2.5">
                <Star className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
                <span className="text-sm leading-relaxed text-ink">{strength}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* 改进建议 */}
        <section aria-label="改进建议">
          <SectionHead title="改进建议" note="针对薄弱环节的具体练习方向" />
          <ul className="mt-2 divide-y divide-line/70">
            {report.improvements.map((item) => (
              <li key={item.title} className="py-3.5">
                <p className="text-[15px] font-semibold text-ink-strong">{item.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">{item.detail}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* 问答回顾 */}
      {answeredQuestions.length > 0 ? (
        <section className="mt-12" aria-label="问答回顾">
          <SectionHead title="问答回顾" note="本次面试的完整问答记录" />
          {collectFlash ? (
            <p className="mt-4 rounded-lg border border-ripple/60 bg-brand-50/60 px-4 py-2.5 text-sm text-brand-700">
              {collectFlash}
            </p>
          ) : null}
          <div className="mt-2 divide-y divide-line/70">
            {answeredQuestions.map((question) => (
              <article
                key={question.id}
                className="group -mx-3 px-3 py-5 transition-colors duration-200 hover:bg-white/70"
              >
                <div className="flex items-start justify-between gap-3">
                  <Badge tone={question.type === 'follow_up' ? 'accent' : 'neutral'}>
                    {question.type === 'follow_up' ? '追问' : `问题 ${question.order_index}`}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={collectedIds.has(question.id) || collectingId === question.id}
                    onClick={() => void collectQuestion(question)}
                    title="收进回澜错题本，按记忆节律复习"
                  >
                    {collectingId === question.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    ) : (
                      <NotebookPen className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {collectedIds.has(question.id) ? '已在错题本' : '收进错题本'}
                  </Button>
                </div>
                <p className="mt-2.5 text-[15px] font-medium text-ink-strong">{question.content}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
                  {question.answer}
                </p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </PageTransition>
  )
}
