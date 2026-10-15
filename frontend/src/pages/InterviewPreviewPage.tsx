import { ArrowLeft, Check, ClipboardList, Info, MessageSquareText, Send } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { PageBackground } from '../components/PageBackground'
import { LogoMark } from '../components/LogoMark'
import { PreviewBanner } from '../components/PreviewBanner'
import { Badge } from '../components/ui/Badge'
import { Button, ButtonLink } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { DIFFICULTY_LABELS, LANGUAGE_LABELS } from '../lib/brand'
import { cn } from '../lib/cn'
import type { InterviewConfig } from '../types'

interface InterviewPreviewLocationState {
  config?: InterviewConfig
}

const ANSWER_MAX_LENGTH = 2000

export default function InterviewPreviewPage() {
  const location = useLocation()
  const config = (location.state as InterviewPreviewLocationState | null)?.config ?? null

  const [currentStep, setCurrentStep] = useState(1)
  const [answer, setAnswer] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  function handleStepChange(step: number) {
    setCurrentStep(step)
    setNotice(null)
  }

  function handleSubmitAnswer() {
    if (!answer.trim()) {
      setNotice('请先输入回答内容，再尝试提交。')
      return
    }
    setNotice('预览模式：回答不会被评分或保存。真实的 AI 评分与追问将在第二阶段接入。')
  }

  return (
    <div className="relative min-h-screen bg-surface">
      <PageBackground scene="workspace" />
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
                {config ? `${config.position} · 模拟面试` : '模拟面试 · 预览'}
              </span>
              {config ? (
                <Badge tone="brand" className="hidden sm:inline-flex">
                  {DIFFICULTY_LABELS[config.difficulty]} ·{' '}
                  {LANGUAGE_LABELS[config.language]}
                </Badge>
              ) : null}
            </div>
          </div>
          <Badge tone="preview">预览</Badge>
        </div>
      </header>

      {/* 工作区玻璃画布：与行舟布局一致的冰白玻璃承载内容 */}
      <div className="glass-surface glass-workspace mx-3 mb-12 mt-6 rounded-3xl sm:mx-5 lg:mx-8">
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <PreviewBanner
          title="预览：真实 AI 面试尚未接入"
          description="本页展示面试工作台的完整界面与交互。题目生成、回答评分与 AI 反馈将在第二阶段接入火山方舟模型后提供。"
        />

        {config ? (
          <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            {/* 左列：步骤进度 + 问题区 */}
            <div className="space-y-5">
              <Card>
                <CardHeader title="练习进度" description={`共 ${config.questionCount} 题`} />
                <CardBody>
                  <ol className="flex flex-wrap items-center gap-2" aria-label="题目步骤">
                    {Array.from({ length: config.questionCount }, (_, index) => index + 1).map(
                      (step) => {
                        const active = step === currentStep
                        return (
                          <li key={step}>
                            <button
                              type="button"
                              onClick={() => handleStepChange(step)}
                              aria-current={active ? 'step' : undefined}
                              className={cn(
                                'relative flex h-9 w-9 items-center justify-center rounded-full text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50',
                                active
                                  ? 'text-white'
                                  : 'border border-line bg-white text-ink-soft hover:border-brand-600/50 hover:text-brand-600',
                              )}
                            >
                              {active ? (
                                <motion.span
                                  layoutId="step-indicator"
                                  className="absolute inset-0 rounded-full bg-brand-600"
                                  transition={{ type: 'spring', bounce: 0.3, duration: 0.55 }}
                                  aria-hidden="true"
                                />
                              ) : null}
                              <span className={active ? 'relative' : undefined}>
                                {step < currentStep ? (
                                  <Check className="h-4 w-4" aria-hidden="true" />
                                ) : (
                                  step
                                )}
                              </span>
                            </button>
                          </li>
                        )
                      },
                    )}
                  </ol>
                  <p className="mt-4 text-xs text-ink-soft">
                    当前查看：第 {currentStep} / {config.questionCount} 题（可点击步骤查看界面布局）
                  </p>
                </CardBody>
              </Card>

              <Card className="border-dashed">
                <CardHeader title={`第 ${currentStep} 题`} description="题目区域" />
                <CardBody>
                  <div className="flex flex-col items-center rounded-lg border border-dashed border-slate-300 bg-surface px-6 py-8 text-center">
                    <ClipboardList
                      className="h-8 w-8 text-slate-400"
                      aria-hidden="true"
                    />
                    <p className="mt-3 text-sm font-medium text-ink-strong">题目待生成</p>
                    <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-ink-soft">
                      真实题目将在第二阶段由 AI 根据目标岗位
                      {config.position}、{DIFFICULTY_LABELS[config.difficulty]}难度与
                      {LANGUAGE_LABELS[config.language]}语言生成。
                    </p>
                  </div>
                </CardBody>
              </Card>
            </div>

            {/* 右列：回答区 + 反馈区 */}
            <div className="space-y-5">
              <Card>
                <CardHeader
                  title="你的回答"
                  description={`建议使用 ${LANGUAGE_LABELS[config.language]}作答`}
                  action={
                    <span className="text-xs text-ink-soft">
                      {answer.length}/{ANSWER_MAX_LENGTH}
                    </span>
                  }
                />
                <CardBody>
                  <textarea
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value.slice(0, ANSWER_MAX_LENGTH))}
                    rows={6}
                    placeholder="在这里输入你的回答。预览模式下可以自由输入，但内容不会被评分或保存。"
                    aria-label="回答输入区"
                    className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm leading-relaxed text-ink placeholder:text-slate-400 transition-colors focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                  />
                  <div className="mt-4 flex items-center justify-between gap-3">
                    {notice ? (
                      <p className="flex items-start gap-1.5 text-xs text-amber-700" role="status">
                        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        {notice}
                      </p>
                    ) : (
                      <p className="text-xs text-ink-soft">提交后由 AI 进行评分与追问</p>
                    )}
                    <Button size="sm" onClick={handleSubmitAnswer} className="shrink-0">
                      <Send className="h-3.5 w-3.5" aria-hidden="true" />
                      提交回答
                    </Button>
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="AI 反馈" description="逐题评分与改进建议" />
                <EmptyState
                  icon={MessageSquareText}
                  title="AI 反馈尚未接入"
                  description="真实面试中，提交回答后会在这里展示评分、亮点与改进建议。该能力将在第二阶段上线。"
                />
              </Card>
            </div>
          </div>
        ) : (
          <Card className="mt-6">
            <EmptyState
              icon={ClipboardList}
              title="尚未创建面试任务"
              description="请先在创建页填写目标岗位与练习偏好，再进入面试工作台预览。"
              action={
                <ButtonLink to="/interview/new" size="sm">
                  去问澜训练
                </ButtonLink>
              }
            />
          </Card>
        )}
      </main>
      </div>
    </div>
  )
}
