import { Compass, Loader2, Sparkles, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import { SkillRadar } from '../components/SkillRadar'
import { SectionHead } from '../components/editorial/Editorial'
import { Button, ButtonLink } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import type {
  GapAnalysisResponse,
  JobAnalysisSummary,
  SkillGraph,
  TrainingRecommendation,
} from '../types'

const DIFFICULTY_LABELS: Record<string, string> = {
  basic: '基础筑基',
  intermediate: '进阶砥砺',
  advanced: '高压淬炼',
}

export function SkillsPage() {
  const [graph, setGraph] = useState<SkillGraph | null>(null)
  const [recommendation, setRecommendation] = useState<TrainingRecommendation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([api.getSkillGraph(), api.getTrainingRecommendation()])
      .then(([graphData, recData]) => {
        if (!active) return
        setGraph(graphData)
        setRecommendation(recData)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof ApiError ? err.message : '加载失败')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-ink-soft">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        正在读取你的成长轨迹…
      </div>
    )
  }

  if (error) {
    return (
      <p role="alert" className="py-16 text-sm text-red-600">
        {error}
      </p>
    )
  }

  const hasData = graph?.available === true

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-ink-strong">观己 · 能力星图</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          由你每一场真实面试的评分汇成：维度为节点，走势为脉络，薄弱处指引下一程。
        </p>
      </div>

      {!hasData || !graph ? (
        <Card>
          <EmptyState
            icon={Compass}
            title="图谱尚未成形"
            description="完成第一场模拟面试后，这里会呈现你的能力维度与成长走势。"
            action={<ButtonLink to="/interview/new">开始第一场面试</ButtonLink>}
          />
        </Card>
      ) : (
        <>
          {recommendation?.available ? (
            <Card className="border-brand-600/30 bg-brand-50/40">
              <CardHeader
                title="下一程建议"
                description={`基于最近 ${recommendation.based_on?.completed_interviews ?? 0} 场面试的真实评分`}
              />
              <CardBody>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-brand-600 px-3 py-1 text-xs font-semibold text-white">
                    {DIFFICULTY_LABELS[recommendation.suggested_difficulty ?? 'intermediate'] ?? '进阶砥砺'}
                  </span>
                  {recommendation.weakest_dimension ? (
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-brand-700 ring-1 ring-inset ring-brand-600/30">
                      侧重：{recommendation.weakest_dimension}
                    </span>
                  ) : null}
                </div>
                {recommendation.focus_hint ? (
                  <p className="mt-3 text-sm leading-relaxed text-ink">
                    {recommendation.focus_hint}
                  </p>
                ) : null}
                <ul className="mt-3 space-y-1.5">
                  {recommendation.reasons.map((reason) => (
                    <li key={reason} className="flex gap-2 text-xs leading-relaxed text-ink-soft">
                      <span aria-hidden="true" className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-600" />
                      {reason}
                    </li>
                  ))}
                </ul>
                <div className="mt-4">
                  <ButtonLink
                    to="/interview/new"
                    size="sm"
                  >
                    按建议开一场
                  </ButtonLink>
                </div>
              </CardBody>
            </Card>
          ) : null}

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="能力维度"
                description={`综合均分 ${graph.average_score ?? '-'} · 最新 ${graph.latest_score ?? '-'}`}
              />
              <CardBody className="space-y-4">
                {graph.nodes.map((node) => {
                  const TrendIcon =
                    node.trend_delta > 0.5 ? TrendingUp : node.trend_delta < -0.5 ? TrendingDown : Minus
                  const trendColor =
                    node.trend_delta > 0.5
                      ? 'text-emerald-600'
                      : node.trend_delta < -0.5
                        ? 'text-red-500'
                        : 'text-slate-400'
                  return (
                    <div key={node.name}>
                      <div className="mb-1.5 flex items-center justify-between text-sm">
                        <span className="font-medium text-ink-strong">
                          {node.name}
                          {node.is_weakest ? (
                            <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                              待加强
                            </span>
                          ) : null}
                          {node.is_strongest ? (
                            <span className="ml-2 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                              优势
                            </span>
                          ) : null}
                        </span>
                        <span className="flex items-center gap-2 text-ink-soft">
                          <span className="font-semibold text-ink-strong">{node.score}</span>
                          <span className={`flex items-center gap-0.5 text-xs ${trendColor}`}>
                            <TrendIcon className="h-3.5 w-3.5" aria-hidden="true" />
                            {node.trend_delta > 0 ? '+' : ''}
                            {node.trend_delta}
                          </span>
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${node.is_weakest ? 'bg-amber-500' : 'bg-brand-600'}`}
                          style={{ width: `${Math.min(node.score, 100)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="总分走势" description="每一场都是一步脚印" />
              <CardBody>
                {graph.score_history.length === 0 ? (
                  <p className="text-sm text-ink-soft">暂无走势数据。</p>
                ) : (
                  <ScoreTrend history={graph.score_history} />
                )}
                {graph.positions_practiced.length > 0 ? (
                  <p className="mt-4 text-xs text-ink-soft">
                    练习方向：{graph.positions_practiced.join('、')}
                  </p>
                ) : null}
              </CardBody>
            </Card>
          </div>
        </>
      )}

      <GapCompareSection />
    </div>
  )
}

/** 星图对照：选一份知岗解析，把真实现值与岗位目标放进同一张雷达图。 */
function GapCompareSection() {
  const [analyses, setAnalyses] = useState<JobAnalysisSummary[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [result, setResult] = useState<GapAnalysisResponse | null>(null)
  const [generating, setGenerating] = useState(false)
  const [resultError, setResultError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .listJobAnalyses()
      .then((items) => {
        if (active) setAnalyses(items)
      })
      .catch((err: unknown) => {
        if (active) setListError(err instanceof ApiError ? err.message : '加载知岗解析列表失败')
      })
    return () => {
      active = false
    }
  }, [])

  const readyAnalyses = (analyses ?? []).filter((item) => item.status === 'ready')

  const generate = () => {
    const id = Number(selectedId)
    if (!selectedId || Number.isNaN(id)) return
    setGenerating(true)
    setResultError(null)
    api
      .gapAnalysis(id)
      .then((data) => {
        setResult(data)
      })
      .catch((err: unknown) => {
        setResultError(err instanceof ApiError ? err.message : '对照生成失败，请稍后再试')
      })
      .finally(() => {
        setGenerating(false)
      })
  }

  return (
    <section aria-label="星图对照" className="pt-4">
      <SectionHead
        title="星图对照"
        note="选一份知岗解析，把你的现值与岗位目标放进同一张星图，差距与下一步一目了然"
      />
      <div className="mt-4">
        {listError ? (
          <p role="alert" className="text-sm text-red-600">
            {listError}
          </p>
        ) : analyses === null ? (
          <p className="flex items-center gap-2 text-sm text-ink-soft">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            正在读取知岗解析…
          </p>
        ) : readyAnalyses.length === 0 ? (
          <EmptyState
            icon={Compass}
            title="还没有可对照的知岗解析"
            description="先去知岗粘贴一份岗位描述，AI 解析出考察方向后，这里就能与你的星图对照。"
            action={<ButtonLink to="/jobs">去知岗解析岗位</ButtonLink>}
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <select
                aria-label="选择知岗解析"
                value={selectedId}
                onChange={(event) => setSelectedId(event.target.value)}
                className="min-w-0 max-w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
              >
                <option value="">选择一份知岗解析…</option>
                {readyAnalyses.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title} · v{item.version_no}
                  </option>
                ))}
              </select>
              <Button onClick={generate} disabled={generating || !selectedId}>
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                )}
                {generating ? '正在生成对照…' : '生成对照'}
              </Button>
            </div>
            {resultError ? (
              <p role="alert" className="mt-4 text-sm text-red-600">
                {resultError}
              </p>
            ) : null}
            {result ? <GapResult result={result} /> : null}
          </>
        )}
      </div>
    </section>
  )
}

function formatGapValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function GapResult({ result }: { result: GapAnalysisResponse }) {
  return (
    <div className="mt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-bold tracking-tight text-ink-strong">{result.position}</h3>
        <p className="text-xs text-ink-soft">
          已完成 {result.completed_interviews} 场面试
          {result.average_score !== null ? ` · 均分 ${result.average_score.toFixed(1)}` : ''}
          {result.model_name ? ` · 由 ${result.model_name} 解析` : ''}
        </p>
      </div>

      {!result.has_data ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50/70 px-3.5 py-2.5 text-sm leading-relaxed text-amber-800">
          尚无真实练习数据，现值记为 0；完成面试后，这里会替换为你的真实评分。
        </p>
      ) : null}

      <div className="mt-6 grid gap-10 lg:grid-cols-2">
        <SkillRadar
          dimensions={result.dimensions.map((dim) => ({
            name: dim.name,
            current: dim.current,
            target: dim.target,
          }))}
        />
        <ul className="divide-y divide-line/80">
          {result.dimensions.map((dim) => (
            <li key={dim.name} className="py-3.5 first:pt-0">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-[15px] font-semibold text-ink-strong">{dim.name}</span>
                <span className="text-sm tabular-nums text-ink">
                  {formatGapValue(dim.current)}
                  <span className="mx-1.5 text-ink-soft">→</span>
                  {formatGapValue(dim.target)}
                </span>
              </div>
              {dim.gap_note ? (
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">{dim.gap_note}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      {result.overall_note ? (
        <blockquote className="mt-8 border-l-2 border-brand-600/50 pl-4 text-sm leading-relaxed text-ink">
          {result.overall_note}
          <span className="mt-1.5 block text-xs text-ink-soft/80">
            —— {result.has_data ? '基于你的真实面试评分与岗位要求' : '岗位目标由 AI 依岗位描述解析，现值暂记为 0'}
          </span>
        </blockquote>
      ) : null}
    </div>
  )
}

function ScoreTrend({
  history,
}: {
  history: { date: string; position: string; score: number }[]
}) {
  const width = 480
  const height = 180
  const padding = { top: 16, right: 16, bottom: 28, left: 32 }
  const scores = history.map((h) => h.score)
  const min = Math.min(50, ...scores)
  const max = Math.max(100, ...scores)
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom
  const points = history.map((h, i) => {
    const x = padding.left + (history.length === 1 ? innerW / 2 : (i / (history.length - 1)) * innerW)
    const y = padding.top + innerH - ((h.score - min) / (max - min)) * innerH
    return { x, y, ...h }
  })
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label="面试总分走势图"
    >
      {[0, 0.5, 1].map((ratio) => {
        const y = padding.top + innerH - ratio * innerH
        const value = min + ratio * (max - min)
        return (
          <g key={ratio}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#e2e8f0" strokeWidth="1" />
            <text x={padding.left - 6} y={y + 4} textAnchor="end" fontSize="10" fill="#94a3b8">
              {Math.round(value)}
            </text>
          </g>
        )
      })}
      <path d={path} fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p) => (
        <g key={p.date}>
          <circle cx={p.x} cy={p.y} r="4" fill="#ffffff" stroke="#2563eb" strokeWidth="2" />
          <title>{`${p.position}：${p.score} 分`}</title>
          <text x={p.x} y={height - 8} textAnchor="middle" fontSize="10" fill="#94a3b8">
            {new Date(p.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}
          </text>
        </g>
      ))}
    </svg>
  )
}
