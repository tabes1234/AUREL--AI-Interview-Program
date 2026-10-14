import { CheckCircle2, CircleAlert, Loader2, Users, XCircle } from 'lucide-react'
import { useState } from 'react'
import { api, ApiError } from '../api/client'
import { PageHeading, SectionHead } from '../components/editorial/Editorial'
import { PageTransition } from '../components/motion/PageTransition'
import { Button, ButtonLink } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { TextAreaField } from '../components/ui/Field'
import type { ExpressionWorkflowResponse } from '../types'

/** 三个协奏席位：与听澜共用同一套多角色复盘流（SSE），此处强调同台并观。 */
const SEATS = [
  { role: 'structure_analyst', label: '结构分析师', scoreKey: 'logic_score', scoreHint: '逻辑结构得分' },
  { role: 'depth_analyst', label: '内容深度分析师', scoreKey: 'depth_score', scoreHint: '内容深度得分' },
  { role: 'expression_coach', label: '表达教练', scoreKey: '', scoreHint: '' },
] as const

type SeatStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped'

interface SeatState {
  status: SeatStatus
  title: string
  error: string | null
}

interface IssueItem {
  type?: string
  evidence?: string
  suggestion?: string
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function asIssues(value: unknown): IssueItem[] {
  return Array.isArray(value)
    ? value
        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
        .map((item) => ({
          type: asString(item.type),
          evidence: asString(item.evidence),
          suggestion: asString(item.suggestion),
        }))
    : []
}

function ScorePill({ score }: { score: number }) {
  const tone = score >= 8 ? 'text-emerald-600' : score >= 6 ? 'text-amber-600' : 'text-red-500'
  return (
    <span className={`text-2xl font-bold tabular-nums ${tone}`}>
      {score}
      <span className="text-sm font-medium text-ink-soft"> / 10</span>
    </span>
  )
}

function IssueList({ issues }: { issues: IssueItem[] }) {
  if (issues.length === 0) return null
  return (
    <ul className="space-y-2">
      {issues.map((issue, index) => (
        <li key={index} className="rounded-lg bg-amber-50/60 px-3 py-2 text-sm">
          <p className="font-medium text-ink">{issue.type || '待改进'}</p>
          {issue.evidence ? (
            <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">原文：「{issue.evidence}」</p>
          ) : null}
          {issue.suggestion ? (
            <p className="mt-0.5 text-xs leading-relaxed text-brand-700">建议：{issue.suggestion}</p>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

function SeatOutput({ role, output }: { role: string; output: Record<string, unknown> }) {
  if (role === 'structure_analyst') {
    const score = asNumber(output.logic_score)
    const markers = asStringList(output.discourse_markers)
    return (
      <div className="space-y-3">
        {score !== null ? (
          <div className="flex items-center gap-2">
            <ScorePill score={score} />
            <span className="text-xs text-ink-soft">逻辑结构得分</span>
          </div>
        ) : null}
        {asString(output.structure_summary) ? (
          <p className="text-sm leading-relaxed text-ink">{asString(output.structure_summary)}</p>
        ) : null}
        {markers.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {markers.map((marker) => (
              <span key={marker} className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs text-brand-700">
                {marker}
              </span>
            ))}
          </div>
        ) : null}
        <IssueList issues={asIssues(output.issues)} />
      </div>
    )
  }

  if (role === 'depth_analyst') {
    const score = asNumber(output.depth_score)
    const examples = asStringList(output.concrete_examples)
    const missing = asStringList(output.missing_substance)
    return (
      <div className="space-y-3">
        {score !== null ? (
          <div className="flex items-center gap-2">
            <ScorePill score={score} />
            <span className="text-xs text-ink-soft">内容深度得分</span>
          </div>
        ) : null}
        {examples.length > 0 ? (
          <div>
            <p className="mb-1 text-xs font-medium text-ink-soft">有具体例证支撑</p>
            <ul className="space-y-1">
              {examples.map((example) => (
                <li key={example} className="rounded-lg bg-emerald-50/70 px-3 py-2 text-sm text-emerald-800">
                  {example}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {missing.length > 0 ? (
          <div>
            <p className="mb-1 text-xs font-medium text-ink-soft">还缺少的实质内容</p>
            <div className="flex flex-wrap gap-1.5">
              {missing.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs text-red-700 ring-1 ring-inset ring-red-600/10"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        <IssueList issues={asIssues(output.issues)} />
      </div>
    )
  }

  // expression_coach
  const fixes = Array.isArray(output.priority_fixes)
    ? output.priority_fixes
        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
        .map((item) => ({ title: asString(item.title), detail: asString(item.detail) }))
        .filter((item) => item.title)
    : []
  const drills = asStringList(output.drill_suggestions)
  return (
    <div className="space-y-3">
      {asString(output.overall_assessment) ? (
        <p className="text-sm leading-relaxed text-ink">{asString(output.overall_assessment)}</p>
      ) : null}
      {fixes.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">优先改进</p>
          <ul className="space-y-1.5">
            {fixes.map((fix, index) => (
              <li key={fix.title} className="rounded-lg bg-brand-50/70 px-3 py-2 text-sm">
                <span className="font-semibold text-brand-700">
                  {index + 1}. {fix.title}
                </span>
                {fix.detail ? <span className="text-ink-soft"> — {fix.detail}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {drills.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">今天就能练</p>
          <ul className="space-y-1">
            {drills.map((drill) => (
              <li key={drill} className="flex items-start gap-2 text-sm text-ink">
                <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand-600" />
                {drill}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

const INITIAL_SEATS: Record<string, SeatState> = Object.fromEntries(
  SEATS.map((seat) => [seat.role, { status: 'pending', title: seat.label, error: null }]),
)

export default function ConcertoPage() {
  const [text, setText] = useState('')
  const [seats, setSeats] = useState<Record<string, SeatState>>(INITIAL_SEATS)
  const [running, setRunning] = useState(false)
  const [workflow, setWorkflow] = useState<ExpressionWorkflowResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const started = Object.values(seats).some((seat) => seat.status !== 'pending')

  async function handleRun() {
    const content = text.trim()
    if (content.length < 30) {
      setError('文字太短了——至少 30 字，三位分析师才有的可析。')
      return
    }
    setRunning(true)
    setError(null)
    setWorkflow(null)
    setSeats(INITIAL_SEATS)
    try {
      const result = await api.analyzeExpressionStream({ text: content }, (event, data) => {
        if (event === 'step_started') {
          setSeats((prev) => ({
            ...prev,
            [data.role]: { status: 'running', title: data.title, error: null },
          }))
        } else {
          const status: SeatStatus =
            data.status === 'failed'
              ? 'failed'
              : data.status === 'skipped'
                ? 'skipped'
                : 'done'
          setSeats((prev) => ({
            ...prev,
            [data.role]: {
              status,
              title: prev[data.role]?.title ?? data.title,
              error: data.error ?? null,
            },
          }))
        }
      })
      setWorkflow(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '协奏分析中断，请重试')
    } finally {
      setRunning(false)
    }
  }

  return (
    <PageTransition>
      <div className="space-y-10">
        <PageHeading
          kicker="洞察"
          title="协奏"
          subtitle="独弦不成音。三位分析师同台并听：结构、深度与表达各执一席，一段话，三面镜子。"
          actions={
            <Button onClick={() => void handleRun()} disabled={running}>
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Users className="h-4 w-4" aria-hidden="true" />
              )}
              {running ? '三位分析师正在同台工作…' : '开始协奏分析'}
            </Button>
          }
        />

        <section aria-label="协奏输入">
          <SectionHead
            title="开始协奏"
            note="一段话，三面镜子：三位分析师各执一席、同时作答。"
          />
          <div className="mt-4 space-y-4 rounded-xl border border-line bg-white p-5 sm:p-6">
            <TextAreaField
              label="把你想打磨的一段话交给乐团"
              value={text}
              onChange={setText}
              placeholder="自我介绍、项目陈述、求职动机……粘贴 30 字以上的文字"
              maxLength={8000}
              rows={7}
            />
            {error ? (
              <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => void handleRun()} disabled={running}>
                {running ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Users className="h-4 w-4" aria-hidden="true" />
                )}
                {running ? '三位分析师正在同台工作…' : '开始协奏分析'}
              </Button>
              <ButtonLink to="/expression" variant="ghost" size="sm">
                需要语音转写？去听澜
              </ButtonLink>
            </div>
          </div>
        </section>

        {/* 三席位并观：细线分隔的并排席位，无卡片边框 */}
        <section aria-label="三席位并观" aria-live="polite">
          <SectionHead
            title="三席并观"
            note={started ? '三位分析师依次落座，结果实时浮现' : '尚在后台静候你的文字'}
          />
          <div className="mt-2 grid gap-10 lg:grid-cols-3 lg:gap-0 lg:divide-x lg:divide-line/80">
            {SEATS.map((seat) => {
              const state = seats[seat.role]
              const step = workflow?.workflow.steps.find((item) => item.role === seat.role)
              const output = step?.output ?? null
              return (
                <div key={seat.role} className="min-w-0 py-2 lg:px-8 lg:first:pl-0 lg:last:pr-0 lg:py-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <SeatIcon status={state?.status ?? 'pending'} />
                      <h3 className="text-sm font-semibold text-ink-strong">{seat.label}</h3>
                    </div>
                    {state?.status === 'running' ? (
                      <span className="text-xs font-medium text-brand-700">正在分析</span>
                    ) : null}
                    {state?.status === 'done' ? (
                      <span className="text-xs font-medium text-emerald-700">已完成</span>
                    ) : null}
                    {state?.status === 'failed' ? (
                      <span className="text-xs font-medium text-red-600">未完成</span>
                    ) : null}
                  </div>
                  <div className="mt-3">
                    {state?.status === 'failed' ? (
                      <p className="text-sm text-red-600">{state.error ?? '该席位未能完成分析'}</p>
                    ) : output ? (
                      <SeatOutput role={seat.role} output={output} />
                    ) : state?.status === 'running' ? (
                      <p className="flex items-center gap-2 py-6 text-sm text-ink-soft">
                        <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-hidden="true" />
                        正在逐句推敲……
                      </p>
                    ) : (
                      <p className="py-6 text-sm text-ink-soft/80">
                        {started ? '等待同席开始。' : '尚在后台静候你的文字。'}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {workflow ? (
          <p className="text-xs text-ink-soft">
            本次协奏由模型 {workflow.model_name ?? '未知'} 参与 · 总评状态：
            {workflow.workflow.status === 'completed'
              ? '全部完成'
              : workflow.workflow.status === 'partial'
                ? '部分席位完成'
                : '未能完成'}
          </p>
        ) : null}

        {!started && !workflow ? (
          <EmptyState
            icon={Users}
            title="乐团尚未就位"
            description="粘贴一段你想打磨的表达，三位分析师会同时从结构、深度与表达三个侧面给出意见。"
          />
        ) : null}
      </div>
    </PageTransition>
  )
}

function SeatIcon({ status }: { status: SeatStatus }) {
  if (status === 'done') {
    return <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
  }
  if (status === 'failed') {
    return <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />
  }
  if (status === 'running') {
    return <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-hidden="true" />
  }
  if (status === 'skipped') {
    return <CircleAlert className="h-4 w-4 text-amber-500" aria-hidden="true" />
  }
  return <CircleAlert className="h-4 w-4 text-slate-300" aria-hidden="true" />
}
