import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  Check,
  ChevronDown,
  ClipboardList,
  Compass,
  Download,
  Eraser,
  History,
  Layers,
  Network,
  Plug,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  TrendingUp,
  X,
} from 'lucide-react'
import { api, ApiError } from '../../api/client'
import { AurelTaskStatus, useAsyncTask } from '../aurel-progress'
import { cn } from '../../lib/cn'
import type {
  CareerAnalysisSituation,
  CareerDirectionsResult,
  CareerGapAnalysis,
  CareerGraph,
  CareerPathComparison,
  CareerPlan,
  CareerProfileDetail,
  CareerProfileFact,
  CareerSkillNode,
  CareerWorkflowRun,
  GrowthFeedback,
  MemoryUsage,
  PlanRevisionSummary,
  PlanReviewResult,
  RetrievalOutcome,
  RetrievalStats,
} from '../../types'

type PanelTab = 'profile' | 'plan' | 'graph' | 'paths' | 'knowledge' | 'workflow'

const TABS: { key: PanelTab; label: string; icon: typeof Layers }[] = [
  { key: 'profile', label: '档案', icon: Layers },
  { key: 'plan', label: '计划', icon: ClipboardList },
  { key: 'graph', label: '图谱', icon: Network },
  { key: 'paths', label: '路径', icon: Compass },
  { key: 'knowledge', label: '知识', icon: BookOpen },
  { key: 'workflow', label: '联动', icon: Plug },
]

const FACT_CATEGORIES: { value: string; label: string }[] = [
  { value: 'stage', label: '当前阶段' },
  { value: 'major', label: '专业背景' },
  { value: 'skill', label: '技能' },
  { value: 'experience', label: '经历' },
  { value: 'industry', label: '感兴趣行业' },
  { value: 'target_role', label: '目标职业' },
  { value: 'difficulty', label: '求职困难' },
  { value: 'constraint', label: '现实约束' },
  { value: 'achievement', label: '成果作品' },
  { value: 'goal', label: '想提升' },
  { value: 'other', label: '其他' },
]

function categoryLabel(key: string): string {
  return FACT_CATEGORIES.find((item) => item.value === key)?.label ?? '其他'
}

/** 来源三态徽标：事实与推断严格分开呈现 */
function SourceBadge({ fact }: { fact: CareerProfileFact }) {
  if (fact.source_type === 'user_stated') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-shallow/70 px-2 py-0.5 text-[11px] font-medium text-brand-700">
        <Check className="h-3 w-3" aria-hidden="true" />
        我提供的
      </span>
    )
  }
  if (fact.source_type === 'ai_generalized') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium',
          fact.confirmed ? 'bg-shallow/70 text-brand-700' : 'border border-dashed border-line bg-white text-ink-soft',
        )}
      >
        AI 归纳{fact.confirmed ? ' · 已确认' : ' · 待你确认'}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-line bg-white px-2 py-0.5 text-[11px] font-medium text-ink-soft">
      AI 推断{fact.confidence ? ` · ${fact.confidence}` : ''}
    </span>
  )
}

function ErrorNote({ message }: { message: string }) {
  return (
    <p className="mt-2 rounded-lg bg-mist/80 px-3 py-2 text-xs leading-relaxed text-ink-soft">
      {message}
    </p>
  )
}

export default function CareerAdvisorPanel({
  conversationId,
  dataVersion = 0,
}: {
  conversationId: number | null
  /** 会话每完成一轮问答就 +1，触发档案重新拉取 */
  dataVersion?: number
}) {
  const [tab, setTab] = useState<PanelTab>('profile')
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-line/70 pb-3">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn(
              'inline-flex min-w-0 flex-1 items-center justify-center gap-1 rounded-full px-1 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
              tab === key ? 'bg-shallow/80 text-brand-700' : 'text-ink-soft hover:bg-mist hover:text-ink',
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
      <div className="mt-4 flex-1 overflow-y-auto pr-1">
        {tab === 'profile' ? (
          <ProfileTab conversationId={conversationId} refreshKey={refreshKey + dataVersion} onRefresh={() => setRefreshKey((n) => n + 1)} />
        ) : tab === 'plan' ? (
          <PlanTab conversationId={conversationId} refreshKey={refreshKey + dataVersion} />
        ) : tab === 'graph' ? (
          <GraphTab refreshKey={refreshKey + dataVersion} />
        ) : tab === 'paths' ? (
          <PathsTab refreshKey={refreshKey} />
        ) : tab === 'knowledge' ? (
          <KnowledgeTab conversationId={conversationId} />
        ) : (
          <WorkflowTab refreshKey={refreshKey} />
        )}
      </div>
    </div>
  )
}

// ---------- 职业档案 ----------

function ProfileTab({
  conversationId,
  refreshKey,
  onRefresh,
}: {
  conversationId: number | null
  refreshKey: number
  onRefresh: () => void
}) {
  const [profile, setProfile] = useState<CareerProfileDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [organizing, setOrganizing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [factDraft, setFactDraft] = useState('')
  const [factCategory, setFactCategory] = useState('other')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState('')
  const [exported, setExported] = useState(false)
  // 结构化分析结果（真实接口返回，不伪造）
  const [situation, setSituation] = useState<CareerAnalysisSituation | null>(null)
  const [directions, setDirections] = useState<CareerDirectionsResult | null>(null)
  // 结构化分析：统一任务状态机（真实计时、防重复触发）
  const [analysisKind, setAnalysisKind] = useState<'situation' | 'directions'>('situation')
  const analysisTask = useAsyncTask({ debugLabel: 'career-analysis' })
  const analyzing = analysisTask.running ? analysisKind : null
  const analysisError = analysisTask.error
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    api
      .getCareerProfile()
      .then((data) => {
        if (aliveRef.current) {
          setProfile(data)
          setLoadError(null)
        }
      })
      .catch((err) => {
        if (aliveRef.current) setLoadError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
    return () => {
      aliveRef.current = false
    }
  }, [refreshKey])

  const runOrganize = () => {
    setOrganizing(true)
    setActionError(null)
    api
      .organizeCareerProfile(conversationId)
      .then((data) => {
        setProfile(data)
        setOrganizing(false)
      })
      .catch((err) => {
        setOrganizing(false)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const addFact = () => {
    const content = factDraft.trim()
    if (!content) return
    setActionError(null)
    api
      .addCareerFact(content, factCategory)
      .then((fact) => {
        setProfile((prev) =>
          prev
            ? {
                ...prev,
                facts: [fact, ...prev.facts],
                confirmed_count: prev.confirmed_count + 1,
              }
            : prev,
        )
        setFactDraft('')
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const confirmFact = (fact: CareerProfileFact) => {
    api
      .updateCareerFact(fact.id, { confirmed: true })
      .then((updated) => {
        setProfile((prev) =>
          prev
            ? {
                ...prev,
                facts: prev.facts.map((item) => (item.id === updated.id ? updated : item)),
                confirmed_count: prev.confirmed_count + (updated.confirmed ? 1 : 0),
                pending_count: Math.max(0, prev.pending_count - (updated.confirmed ? 1 : 0)),
              }
            : prev,
        )
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const saveEdit = (fact: CareerProfileFact) => {
    const content = editDraft.trim()
    if (!content) return
    api
      .updateCareerFact(fact.id, { content })
      .then((updated) => {
        setProfile((prev) =>
          prev
            ? { ...prev, facts: prev.facts.map((item) => (item.id === updated.id ? updated : item)) }
            : prev,
        )
        setEditingId(null)
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const removeFact = (fact: CareerProfileFact) => {
    api
      .deleteCareerFact(fact.id)
      .then(() => {
        setProfile((prev) =>
          prev
            ? {
                ...prev,
                facts: prev.facts.filter((item) => item.id !== fact.id),
                confirmed_count: Math.max(0, prev.confirmed_count - (fact.confirmed ? 1 : 0)),
                pending_count: Math.max(0, prev.pending_count - (fact.confirmed ? 0 : 1)),
              }
            : prev,
        )
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const clearFacts = () => {
    if (!window.confirm('确定清空长期职业档案吗？所有事实记录都会删除，之后小鸥不再引用它们。')) return
    api
      .clearCareerFacts()
      .then(() => onRefresh())
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const exportData = () => {
    api
      .exportCareerData()
      .then(({ blob, filename }) => {
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = filename
        anchor.click()
        URL.revokeObjectURL(url)
        setExported(true)
        window.setTimeout(() => setExported(false), 2500)
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const analyze = (kind: 'situation' | 'directions') => {
    setAnalysisKind(kind)
    void analysisTask.run(async () => {
      const data =
        kind === 'situation' ? await api.analyzeCareerSituation() : await api.exploreCareerDirections()
      if (kind === 'situation') {
        setSituation(data as CareerAnalysisSituation)
      } else {
        setDirections(data as CareerDirectionsResult)
      }
    })
  }

  return (
    <div className="space-y-6 pb-4">
      {loadError ? <ErrorNote message={loadError} /> : null}
      {actionError ? <ErrorNote message={actionError} /> : null}

      {profile && (profile.summary || profile.facts.length > 0) ? (
        <section>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink-strong">
              长期档案
              <span className="ml-2 text-xs font-normal text-ink-soft">
                已确认 {profile.confirmed_count} · 待确认 {profile.pending_count}
              </span>
            </h3>
            <button
              type="button"
              onClick={runOrganize}
              disabled={organizing}
              className="inline-flex items-center gap-1 rounded-full bg-mist px-2.5 py-1 text-xs font-semibold text-brand-700 transition-colors hover:bg-shallow disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
            >
              <RefreshCw className={cn('h-3 w-3', organizing && 'animate-spin')} aria-hidden="true" />
              {organizing ? '整理中…' : 'AI 整理'}
            </button>
          </div>
          {profile.summary ? (
            <p className="mt-2 whitespace-pre-wrap rounded-xl bg-mist/60 px-3 py-2.5 text-[13px] leading-relaxed text-ink">
              {profile.summary}
            </p>
          ) : null}
          <ul className="mt-3 space-y-2.5">
            {profile.facts.map((fact) => (
              <li key={fact.id} className="group rounded-xl border border-line/80 bg-white/85 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-medium text-ink-soft">{categoryLabel(fact.category)}</span>
                  <SourceBadge fact={fact} />
                </div>
                {editingId === fact.id ? (
                  <div className="mt-1.5">
                    <textarea
                      value={editDraft}
                      onChange={(event) => setEditDraft(event.target.value)}
                      rows={2}
                      className="w-full resize-none rounded-lg border border-ripple bg-white px-2.5 py-1.5 text-[13px] leading-relaxed text-ink focus:outline-none focus:ring-2 focus:ring-ripple/40"
                    />
                    <div className="mt-1.5 flex gap-2">
                      <button
                        type="button"
                        onClick={() => saveEdit(fact)}
                        className="rounded-full bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                      >
                        保存
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="rounded-full px-2 py-1 text-xs text-ink-soft hover:text-ink focus-visible:outline-none"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-1 text-[13px] leading-relaxed text-ink">{fact.content}</p>
                )}
                {fact.source_type === 'user_stated' && fact.quote ? (
                  <p className="mt-1 border-l-2 border-line pl-2 text-[11px] italic leading-relaxed text-ink-soft">
                    原话：「{fact.quote}」
                  </p>
                ) : null}
                <div className="mt-1.5 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                  {!fact.confirmed && fact.source_type !== 'user_stated' ? (
                    <button
                      type="button"
                      onClick={() => confirmFact(fact)}
                      className="text-[11px] font-medium text-brand-600 hover:text-brand-700 focus-visible:outline-none"
                    >
                      确认无误
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(fact.id)
                      setEditDraft(fact.content)
                    }}
                    className="text-[11px] text-ink-soft hover:text-ink focus-visible:outline-none"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFact(fact)}
                    className="text-[11px] text-ink-soft hover:text-brand-700 focus-visible:outline-none"
                  >
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={clearFacts}
              className="inline-flex items-center gap-1 text-xs text-ink-soft transition-colors hover:text-brand-700 focus-visible:outline-none"
            >
              <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
              清空记忆
            </button>
            <button
              type="button"
              onClick={exportData}
              className="inline-flex items-center gap-1 text-xs text-ink-soft transition-colors hover:text-brand-700 focus-visible:outline-none"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              导出我的数据
            </button>
            {exported ? <span className="text-xs text-brand-700">已开始下载</span> : null}
          </div>
        </section>
      ) : (
        !loadError && (
          <p className="rounded-xl bg-mist/50 px-3 py-3 text-[13px] leading-relaxed text-ink-soft">
            长期档案还是空的。多和小鸥聊聊，它会把关键信息整理到这里；AI 的归纳会先请你确认，不会擅自当成事实。
          </p>
        )
      )}

      {/* 主动补充一条事实 */}
      <section>
        <h3 className="text-sm font-semibold text-ink-strong">补充一条</h3>
        <div className="mt-2 flex gap-2">
          <select
            value={factCategory}
            onChange={(event) => setFactCategory(event.target.value)}
            className="shrink-0 rounded-lg border border-line bg-white px-2 py-1.5 text-xs text-ink focus:outline-none focus:ring-2 focus:ring-ripple/40"
          >
            {FACT_CATEGORIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <input
            value={factDraft}
            onChange={(event) => setFactDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addFact()
              }
            }}
            placeholder="例如：我在准备秋招的产品岗"
            className="min-w-0 flex-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
          />
          <button
            type="button"
            onClick={addFact}
            disabled={!factDraft.trim()}
            className="shrink-0 rounded-lg bg-brand-600 p-1.5 text-white transition-colors hover:bg-brand-700 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
            aria-label="添加这条档案"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </section>

      {/* 结构化分析：真实调用分析引擎 */}
      <section className="border-t border-line/70 pt-5">
        <h3 className="text-sm font-semibold text-ink-strong">结构化分析</h3>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={() => analyze('situation')}
            disabled={analyzing != null}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {analyzing === 'situation' ? '分析中…' : '当前情况总结'}
          </button>
          <button
            type="button"
            onClick={() => analyze('directions')}
            disabled={analyzing != null}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {analyzing === 'directions' ? '分析中…' : '职业方向探索'}
          </button>
        </div>
        {analysisTask.running ? (
          <AurelTaskStatus
            className="mt-3"
            title={analysisKind === 'situation' ? '当前情况总结' : '职业方向探索'}
            scene={analysisKind === 'situation' ? 'ai.start' : 'career.direction'}
            status={analysisTask.status}
            elapsedMs={analysisTask.elapsedMs}
          />
        ) : null}
        {analysisError ? <ErrorNote message={analysisError} /> : null}

        {situation ? (
          <div className="mt-3 space-y-2 rounded-xl border border-line/80 bg-white/85 p-3 text-[13px] leading-relaxed">
            <p className="text-ink">{situation.summary}</p>
            {situation.known.length > 0 ? (
              <div>
                <p className="text-xs font-semibold text-brand-700">已确认的信息</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-ink-soft">
                  {situation.known.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {situation.uncertain.length > 0 ? (
              <div>
                <p className="text-xs font-semibold text-ink-soft">尚不确定</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-ink-soft">
                  {situation.uncertain.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {situation.suggested_focus.length > 0 ? (
              <div>
                <p className="text-xs font-semibold text-ink-soft">建议聚焦</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-ink-soft">
                  {situation.suggested_focus.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        {directions ? (
          <div className="mt-3 space-y-3">
            {directions.directions.map((direction) => (
              <div key={direction.name} className="rounded-xl border border-line/80 bg-white/85 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink-strong">{direction.name}</p>
                  <span className="rounded-full bg-mist px-2 py-0.5 text-[11px] font-medium text-brand-700">
                    {direction.fit}
                  </span>
                </div>
                {direction.relation ? (
                  <p className="mt-1 text-[13px] leading-relaxed text-ink">{direction.relation}</p>
                ) : null}
                <DirectionList label="常见岗位要求" items={direction.requirements} />
                <DirectionList label="你已有的证据" items={direction.evidence} />
                <DirectionList label="未明确的情况" items={direction.unknowns} />
                <DirectionList label="需验证的条件" items={direction.conditions} />
                <DirectionList label="下一步探索" items={direction.next_steps} />
              </div>
            ))}
            {directions.directions.length === 0 ? (
              <p className="text-[13px] text-ink-soft">这次没有提出方向——多聊一些经历后再试。</p>
            ) : null}
            <p className="text-[11px] leading-relaxed text-ink-soft">{directions.note}</p>
          </div>
        ) : null}
      </section>
    </div>
  )
}

function DirectionList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="mt-2">
      <p className="text-xs font-semibold text-ink-soft">{label}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[13px] leading-relaxed text-ink-soft">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

// ---------- 行动计划 ----------

const PHASE_LABELS: Record<string, string> = {
  '7d': '未来 7 天',
  '30d': '未来 30 天',
  '90d': '未来 90 天',
}

function PlanTab({ conversationId, refreshKey }: { conversationId: number | null; refreshKey: number }) {
  const [plans, setPlans] = useState<CareerPlan[] | null>(null)
  const [activePlanId, setActivePlanId] = useState<number | null>(null)
  // 计划生成：统一任务状态机（真实计时、防重复触发）
  const planTask = useAsyncTask({ debugLabel: 'career-plan-generate' })
  const generating = planTask.running
  const [actionError, setActionError] = useState<string | null>(null)
  const [newGoal, setNewGoal] = useState('')
  const [newPhase, setNewPhase] = useState('30d')
  const [reviewDraft, setReviewDraft] = useState<{ actionId: number; text: string } | null>(null)
  const aliveRef = useRef(true)

  const loadPlans = () => {
    return api
      .listCareerPlans()
      .then((summaries) =>
        Promise.all(summaries.map((summary) => api.getCareerPlan(summary.id))),
      )
      .then((items) => {
        if (aliveRef.current) setPlans(items)
      })
  }

  useEffect(() => {
    aliveRef.current = true
    loadPlans().catch((err) => {
      if (aliveRef.current) setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
    })
    return () => {
      aliveRef.current = false
    }
  }, [refreshKey])

  const activePlan = plans?.find((plan) => plan.id === activePlanId) ?? null

  const generate = () => {
    setActionError(null)
    void planTask.run(async () => {
      const plan = await api.generateCareerPlan({ conversation_id: conversationId })
      setPlans((prev) => (prev ? [plan, ...prev] : [plan]))
      setActivePlanId(plan.id)
    })
  }

  const patchPlan = (planId: number, payload: { title?: string; status?: string }) => {
    return api.updateCareerPlan(planId, payload).then((plan) => replacePlan(plan))
  }

  const replacePlan = (plan: CareerPlan) => {
    setPlans((prev) => (prev ? prev.map((item) => (item.id === plan.id ? plan : item)) : [plan]))
  }

  const removePlan = (planId: number) => {
    api
      .deleteCareerPlan(planId)
      .then(() => {
        setPlans((prev) => (prev ? prev.filter((item) => item.id !== planId) : prev))
        setActivePlanId((current) => (current === planId ? null : current))
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const patchAction = (
    actionId: number,
    payload: { status?: string; review?: string | null; due_at?: string | null },
  ) => {
    if (!activePlan) return
    api
      .updateCareerPlanAction(activePlan.id, actionId, payload)
      .then(replacePlan)
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const addAction = () => {
    const goal = newGoal.trim()
    if (!goal || !activePlan) return
    api
      .addCareerPlanAction(activePlan.id, { phase: newPhase, goal })
      .then(replacePlan)
      .then(() => setNewGoal(''))
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const removeAction = (actionId: number) => {
    if (!activePlan) return
    api
      .deleteCareerPlanAction(activePlan.id, actionId)
      .then(replacePlan)
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  return (
    <div className="space-y-5 pb-4">
      {actionError ? <ErrorNote message={actionError} /> : null}

      {plans === null ? (
        <p className="text-[13px] text-ink-soft">计划加载中……</p>
      ) : (
        <>
          {activePlan ? (
            <button
              type="button"
              onClick={() => setActivePlanId(null)}
              className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-ink focus-visible:outline-none"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
              返回计划列表
            </button>
          ) : null}

          {!activePlan ? (
            <>
              <button
                type="button"
                onClick={generate}
                disabled={generating}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-card transition-all hover:bg-brand-700 hover:shadow-raised disabled:opacity-55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
              >
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                {generating ? '正在结合你的档案制定计划……' : '让小鸥制定 7/30/90 天计划'}
              </button>
              {planTask.running ? (
                <AurelTaskStatus
                  title="计划生成"
                  scene="career.plan"
                  status={planTask.status}
                  error={planTask.error}
                  elapsedMs={planTask.elapsedMs}
                />
              ) : null}
              {plans.length === 0 ? (
                <p className="text-[13px] leading-relaxed text-ink-soft">
                  还没有行动计划。多聊几句后让小鸥制定，它会给出阶段化任务——计划不会承诺任何求职结果，只帮你把路拆成能走的步子。
                </p>
              ) : null}
              <ul className="space-y-2.5">
                {plans.map((plan) => (
                  <li key={plan.id} className="group rounded-xl border border-line/80 bg-white/85 px-3.5 py-3">
                    <button
                      type="button"
                      onClick={() => setActivePlanId(plan.id)}
                      className="w-full text-left focus-visible:outline-none"
                    >
                      <p className="text-sm font-semibold text-ink-strong group-hover:text-brand-700">
                        {plan.title}
                      </p>
                      {plan.focus_role ? (
                        <p className="mt-0.5 text-xs text-ink-soft">目标方向：{plan.focus_role}</p>
                      ) : null}
                      <p className="mt-1 text-xs text-ink-soft">
                        待完成 {plan.actions.filter((action) => action.status === 'pending').length} ·
                        已完成 {plan.actions.filter((action) => action.status === 'done').length} ·
                        第 {plan.version_no} 版
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
              <GrowthSection refreshKey={refreshKey} />
            </>
          ) : (
            <PlanDetail
              plan={activePlan}
              onBack={() => setActivePlanId(null)}
              onPatchPlan={patchPlan}
              onRemovePlan={removePlan}
              onPatchAction={patchAction}
              onAddAction={addAction}
              onRemoveAction={removeAction}
              onPlanReplaced={replacePlan}
              newGoal={newGoal}
              setNewGoal={setNewGoal}
              newPhase={newPhase}
              setNewPhase={setNewPhase}
              reviewDraft={reviewDraft}
              setReviewDraft={setReviewDraft}
            />
          )}
        </>
      )}
    </div>
  )
}

function PlanDetail({
  plan,
  onBack,
  onPatchPlan,
  onRemovePlan,
  onPatchAction,
  onAddAction,
  onRemoveAction,
  onPlanReplaced,
  newGoal,
  setNewGoal,
  newPhase,
  setNewPhase,
  reviewDraft,
  setReviewDraft,
}: {
  plan: CareerPlan
  onBack: () => void
  onPatchPlan: (planId: number, payload: { title?: string; status?: string }) => void
  onRemovePlan: (planId: number) => void
  onPatchAction: (
    actionId: number,
    payload: { status?: string; review?: string | null; due_at?: string | null },
  ) => void
  onAddAction: () => void
  onRemoveAction: (actionId: number) => void
  onPlanReplaced: (plan: CareerPlan) => void
  newGoal: string
  setNewGoal: (value: string) => void
  newPhase: string
  setNewPhase: (value: string) => void
  reviewDraft: { actionId: number; text: string } | null
  setReviewDraft: (value: { actionId: number; text: string } | null) => void
}) {
  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold leading-snug text-ink-strong">{plan.title}</h3>
        <span className="shrink-0 rounded-full bg-mist px-2 py-0.5 text-[11px] font-medium text-brand-700">
          第 {plan.version_no} 版
        </span>
      </div>
      {plan.situation ? (
        <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-relaxed text-ink-soft">{plan.situation}</p>
      ) : null}
      {plan.focus_role ? (
        <p className="mt-1.5 text-xs text-ink-soft">目标方向：{plan.focus_role}</p>
      ) : null}

      {(['7d', '30d', '90d'] as const).map((phase) => {
        const actions = plan.actions.filter((action) => action.phase === phase)
        if (actions.length === 0) return null
        return (
          <section key={phase} className="mt-4">
            <h4 className="text-xs font-bold uppercase tracking-wide text-ink-soft">
              {PHASE_LABELS[phase]}
            </h4>
            <ul className="mt-2 space-y-2.5">
              {actions.map((action) => (
                <li
                  key={action.id}
                  className={cn(
                    'rounded-xl border px-3 py-2.5',
                    action.status === 'done'
                      ? 'border-shallow/70 bg-shallow/25'
                      : action.status === 'skipped'
                        ? 'border-line/70 bg-white/60 opacity-70'
                        : 'border-line/80 bg-white/85',
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <button
                      type="button"
                      onClick={() =>
                        onPatchAction(action.id, { status: action.status === 'done' ? 'pending' : 'done' })
                      }
                      aria-label={action.status === 'done' ? '标记为未完成' : '标记为已完成'}
                      className={cn(
                        'mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
                        action.status === 'done'
                          ? 'border-brand-600 bg-brand-600 text-white'
                          : 'border-line bg-white hover:border-brand-600',
                      )}
                    >
                      {action.status === 'done' ? <Check className="h-3 w-3" aria-hidden="true" /> : null}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p
                        className={cn(
                          'text-[13px] font-medium leading-relaxed text-ink',
                          action.status === 'done' && 'line-through opacity-70',
                        )}
                      >
                        {action.goal}
                      </p>
                      {action.steps ? (
                        <p className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-ink-soft">{action.steps}</p>
                      ) : null}
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-soft">
                        {action.due_at ? <span>期限 {formatDue(action.due_at)}</span> : null}
                        {action.related_goal ? <span>关联：{action.related_goal}</span> : null}
                        {action.status === 'skipped' ? <span className="text-ink-soft">已跳过</span> : null}
                      </div>
                      {action.review ? (
                        <p className="mt-1.5 rounded-lg bg-mist/60 px-2.5 py-1.5 text-xs leading-relaxed text-ink-soft">
                          复盘：{action.review}
                        </p>
                      ) : null}

                      {reviewDraft?.actionId === action.id ? (
                        <div className="mt-2">
                          <textarea
                            value={reviewDraft.text}
                            onChange={(event) =>
                              setReviewDraft({ actionId: action.id, text: event.target.value })
                            }
                            rows={2}
                            placeholder="这一步做得怎么样？写下你的复盘。"
                            className="w-full resize-none rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs leading-relaxed text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
                          />
                          <div className="mt-1.5 flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                onPatchAction(action.id, { review: reviewDraft.text.trim() || null })
                                setReviewDraft(null)
                              }}
                              className="rounded-full bg-brand-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-700 focus-visible:outline-none"
                            >
                              保存复盘
                            </button>
                            <button
                              type="button"
                              onClick={() => setReviewDraft(null)}
                              className="rounded-full px-2 py-1 text-xs text-ink-soft hover:text-ink focus-visible:outline-none"
                            >
                              取消
                            </button>
                          </div>
                        </div>
                      ) : null}

                      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <button
                          type="button"
                          onClick={() => setReviewDraft({ actionId: action.id, text: action.review ?? '' })}
                          className="text-[11px] text-ink-soft hover:text-brand-700 focus-visible:outline-none"
                        >
                          复盘
                        </button>
                        {action.status !== 'skipped' ? (
                          <button
                            type="button"
                            onClick={() => onPatchAction(action.id, { status: 'skipped' })}
                            className="text-[11px] text-ink-soft hover:text-brand-700 focus-visible:outline-none"
                          >
                            跳过
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => onPatchAction(action.id, { status: 'pending' })}
                            className="text-[11px] text-ink-soft hover:text-brand-700 focus-visible:outline-none"
                          >
                            恢复
                          </button>
                        )}
                        <label className="inline-flex cursor-pointer items-center gap-1 text-[11px] text-ink-soft hover:text-brand-700 focus-within:outline-none">
                          改期
                          <input
                            type="date"
                            value={action.due_at ? action.due_at.slice(0, 10) : ''}
                            onChange={(event) =>
                              onPatchAction(action.id, {
                                due_at: event.target.value ? `${event.target.value}T00:00:00Z` : null,
                              })
                            }
                            className="rounded border border-line bg-white px-1 py-0.5 text-[11px] text-ink focus:outline-none"
                          />
                        </label>
                        <button
                          type="button"
                          onClick={() => onRemoveAction(action.id)}
                          className="text-[11px] text-ink-soft hover:text-brand-700 focus-visible:outline-none"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )
      })}

      {/* 手动补一个任务 */}
      <div className="mt-4 flex gap-2">
        <select
          value={newPhase}
          onChange={(event) => setNewPhase(event.target.value)}
          className="shrink-0 rounded-lg border border-line bg-white px-2 py-1.5 text-xs text-ink focus:outline-none"
        >
          <option value="7d">7 天</option>
          <option value="30d">30 天</option>
          <option value="90d">90 天</option>
        </select>
        <input
          value={newGoal}
          onChange={(event) => setNewGoal(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              onAddAction()
            }
          }}
          placeholder="自己补一个任务…"
          className="min-w-0 flex-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
        />
        <button
          type="button"
          onClick={onAddAction}
          disabled={!newGoal.trim()}
          className="shrink-0 rounded-lg bg-brand-600 p-1.5 text-white transition-colors hover:bg-brand-700 disabled:opacity-40 focus-visible:outline-none"
          aria-label="添加任务"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <PlanVersionsAndReview key={plan.id} planId={plan.id} versionNo={plan.version_no} onPlanReplaced={onPlanReplaced} />

      <div className="mt-5 flex items-center gap-4 border-t border-line/70 pt-4">
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-ink-soft hover:text-ink focus-visible:outline-none"
        >
          返回列表
        </button>
        <button
          type="button"
          onClick={() => onPatchPlan(plan.id, { status: plan.status === 'active' ? 'archived' : 'active' })}
          className="text-xs text-ink-soft hover:text-brand-700 focus-visible:outline-none"
        >
          {plan.status === 'active' ? '归档这份计划' : '恢复为进行中'}
        </button>
        <button
          type="button"
          onClick={() => onRemovePlan(plan.id)}
          className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-brand-700 focus-visible:outline-none"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          删除计划
        </button>
      </div>
    </div>
  )
}

function formatDue(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// ---------- 模块联动 ----------

function WorkflowTab({ refreshKey }: { refreshKey: number }) {
  const [runs, setRuns] = useState<CareerWorkflowRun[]>([])
  const [running, setRunning] = useState<'gap_analysis' | 'interview_prep' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [prepPosition, setPrepPosition] = useState('')
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    api
      .listCareerWorkflows()
      .then((items) => {
        if (aliveRef.current) {
          setRuns(items)
          setExpandedId((current) => current ?? items[0]?.id ?? null)
        }
      })
      .catch(() => undefined)
    return () => {
      aliveRef.current = false
    }
  }, [refreshKey])

  const runWorkflow = (kind: 'gap_analysis' | 'interview_prep') => {
    setRunning(kind)
    setActionError(null)
    const params = kind === 'interview_prep' && prepPosition.trim() ? { position: prepPosition.trim() } : {}
    api
      .runCareerWorkflow(kind, params)
      .then((run) => {
        setRuns((prev) => [run, ...prev])
        setExpandedId(run.id)
        setRunning(null)
        if (kind === 'interview_prep') setPrepPosition('')
      })
      .catch((err) => {
        setRunning(null)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  return (
    <div className="space-y-5 pb-4">
      {actionError ? <ErrorNote message={actionError} /> : null}

      <section>
        <h3 className="text-sm font-semibold text-ink-strong">真实调用各模块</h3>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
          每一步都在后端真实执行并留痕：读档案、查知岗、翻简历、搜知藏、汇总观己评分——不会只在对话里说说而已。
        </p>
        <div className="mt-3 space-y-3">
          <div className="rounded-xl border border-line/80 bg-white/85 p-3">
            <p className="text-[13px] font-semibold text-ink">能力差距分析</p>
            <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
              结合知岗 JD、履历成章简历与问澜评分，找出已证明与缺证据的能力。
            </p>
            <button
              type="button"
              onClick={() => runWorkflow('gap_analysis')}
              disabled={running != null}
              className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
            >
              {running === 'gap_analysis' ? '正在分析……' : '开始分析'}
            </button>
          </div>
          <div className="rounded-xl border border-line/80 bg-white/85 p-3">
            <p className="text-[13px] font-semibold text-ink">安排面试训练</p>
            <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
              根据目标岗位在问澜真实创建一场练习（默认 5 题）。
            </p>
            <div className="mt-2 flex gap-2">
              <input
                value={prepPosition}
                onChange={(event) => setPrepPosition(event.target.value)}
                placeholder="岗位名（留空则用最近的知岗解析）"
                className="min-w-0 flex-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
              />
              <button
                type="button"
                onClick={() => runWorkflow('interview_prep')}
                disabled={running != null}
                className="shrink-0 rounded-full bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
              >
                {running === 'interview_prep' ? '创建中……' : '开始安排'}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-line/70 pt-5">
        <h3 className="text-sm font-semibold text-ink-strong">运行记录</h3>
        {runs.length === 0 ? (
          <p className="mt-2 text-[13px] text-ink-soft">还没有运行记录。</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {runs.map((run) => (
              <li key={run.id} className="rounded-xl border border-line/80 bg-white/85">
                <button
                  type="button"
                  onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left focus-visible:outline-none"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-semibold text-ink-strong">
                      {run.kind === 'gap_analysis' ? '能力差距分析' : '面试训练安排'} ·{' '}
                      {formatDue(run.created_at)}
                    </span>
                    <span
                      className={cn(
                        'mt-0.5 block text-[11px]',
                        run.status === 'succeeded'
                          ? 'text-brand-700'
                          : run.status === 'failed'
                            ? 'text-ink-soft'
                            : 'text-ink-soft',
                      )}
                    >
                      {run.status === 'succeeded'
                        ? '已完成'
                        : run.status === 'failed'
                          ? '失败（已如实记录）'
                          : '进行中'}
                      {run.steps.length > 0 ? ` · ${run.steps.length} 步` : ''}
                    </span>
                  </span>
                  <ChevronDown
                    className={cn('h-4 w-4 shrink-0 text-ink-soft transition-transform', expandedId === run.id && 'rotate-180')}
                    aria-hidden="true"
                  />
                </button>
                {expandedId === run.id ? (
                  <div className="border-t border-line/60 px-3 py-2.5">
                    <ol className="space-y-1.5">
                      {run.steps.map((step, index) => (
                        <li key={`${step.key}-${index}`} className="flex items-start gap-2 text-xs leading-relaxed">
                          <span
                            className={cn(
                              'mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold',
                              step.status === 'succeeded'
                                ? 'bg-shallow text-brand-700'
                                : step.status === 'skipped'
                                  ? 'bg-mist text-ink-soft'
                                  : step.status === 'failed'
                                    ? 'bg-line text-ink'
                                    : 'bg-mist text-brand-700',
                            )}
                          >
                            {step.status === 'succeeded' ? '✓' : step.status === 'skipped' ? '—' : step.status === 'failed' ? '×' : '·'}
                          </span>
                          <span className="min-w-0">
                            <span className="text-ink">{step.title}</span>
                            {step.detail ? <span className="block text-ink-soft">{step.detail}</span> : null}
                          </span>
                        </li>
                      ))}
                    </ol>
                    {run.error_message ? (
                      <p className="mt-2 rounded-lg bg-mist/80 px-2.5 py-1.5 text-xs leading-relaxed text-ink-soft">
                        失败原因：{run.error_message}
                      </p>
                    ) : null}
                    {run.kind === 'gap_analysis' && run.status === 'succeeded' ? (
                      <GapResult result={run.result as unknown as CareerGapAnalysis | null} />
                    ) : null}
                    {run.kind === 'interview_prep' && run.status === 'succeeded' && run.result ? (
                      <div className="mt-2 rounded-lg bg-mist/60 px-2.5 py-2 text-xs leading-relaxed text-ink">
                        <p>{String(run.result.message ?? '')}</p>
                        {typeof run.result.task_id === 'number' ? (
                          <Link
                            to={`/interview/${run.result.task_id}`}
                            className="mt-1 inline-block font-medium text-brand-700 underline-offset-4 hover:underline"
                          >
                            前往这场练习 →
                          </Link>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function GapResult({ result }: { result: CareerGapAnalysis | null }) {
  if (!result) return null
  return (
    <div className="mt-2 space-y-2 text-[13px] leading-relaxed">
      <p className="font-semibold text-ink-strong">目标：{result.target_role || '未明确说明'}</p>
      <DirectionList label="你已有的" items={result.have} />
      <DirectionList label="岗位要求的" items={result.required} />
      <DirectionList label="已有证据证明的" items={result.proven} />
      <DirectionList label="还缺证据的（缺证据 ≠ 不会）" items={result.missing} />
      <DirectionList label="可以补足的" items={result.buildable} />
      <DirectionList label="建议的实践任务" items={result.practice_tasks} />
      {result.notes ? <p className="text-xs text-ink-soft">{result.notes}</p> : null}
    </div>
  )
}

// ---------- 成长反馈（只来自真实记录） ----------

function GrowthSection({ refreshKey }: { refreshKey: number }) {
  const [growth, setGrowth] = useState<GrowthFeedback | null>(null)
  const [error, setError] = useState<string | null>(null)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    api
      .getGrowthFeedback()
      .then((data) => {
        if (aliveRef.current) setGrowth(data)
      })
      .catch((err) => {
        if (aliveRef.current) setError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
    return () => {
      aliveRef.current = false
    }
  }, [refreshKey])

  if (error) return null
  if (!growth) return null
  if (!growth.available) {
    return (
      <section className="rounded-xl border border-dashed border-line bg-white/60 px-3.5 py-3">
        <h4 className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-soft">
          <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
          成长轨迹
        </h4>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{growth.message}</p>
      </section>
    )
  }
  return (
    <section className="rounded-xl border border-line/80 bg-white/85 px-3.5 py-3">
      <h4 className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-strong">
        <TrendingUp className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" />
        成长轨迹（真实记录）
      </h4>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink">
        <span>活跃天数 {growth.heatmap.total_active_days ?? 0}</span>
        <span>连续打卡 {growth.heatmap.current_streak ?? 0} 天</span>
        <span>度衡挑战 {growth.challenge_count} 次</span>
        <span>问澜报告 {growth.interview_scores.length} 份</span>
      </div>
      {growth.interview_scores.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {growth.interview_scores.slice(-3).map((item, index) => (
            <li key={`${item.date}-${index}`} className="flex items-center justify-between text-xs text-ink-soft">
              <span className="truncate">
                {item.date} · {item.position}
              </span>
              <span className="font-semibold text-brand-700">{item.score} 分</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-2 text-[11px] leading-relaxed text-ink-soft">{growth.disclaimer}</p>
    </section>
  )
}

// ---------- 规划版本与复盘（历史不覆盖） ----------

function PlanVersionsAndReview({
  planId,
  versionNo,
  onPlanReplaced,
}: {
  planId: number
  versionNo: number
  onPlanReplaced: (plan: CareerPlan) => void
}) {
  const [revisions, setRevisions] = useState<PlanRevisionSummary[] | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [review, setReview] = useState<PlanReviewResult | null>(null)
  const [selectedAdjustments, setSelectedAdjustments] = useState<number[]>([])
  const [busy, setBusy] = useState<'review' | 'apply' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const loadRevisions = () => {
    return api
      .listPlanRevisions(planId)
      .then((items) => setRevisions(items))
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  useEffect(() => {
    loadRevisions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId])

  const runReview = () => {
    setBusy('review')
    setActionError(null)
    api
      .reviewCareerPlan(planId)
      .then((outcome) => {
        setReview(outcome.review)
        setSelectedAdjustments(outcome.review.adjustments.map((_, index) => index))
        setBusy(null)
        loadRevisions()
      })
      .catch((err) => {
        setBusy(null)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const applyAdjustments = () => {
    if (!review) return
    const adjustments = review.adjustments.filter((_, index) => selectedAdjustments.includes(index))
    if (adjustments.length === 0) return
    setBusy('apply')
    setActionError(null)
    api
      .applyPlanReviewAdjustments(planId, adjustments)
      .then(({ plan }) => {
        onPlanReplaced(plan)
        setBusy(null)
        setReview(null)
        loadRevisions()
      })
      .catch((err) => {
        setBusy(null)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  return (
    <section className="mt-5 border-t border-line/70 pt-4">
      <div className="flex items-center justify-between">
        <h4 className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-strong">
          <History className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" />
          版本与复盘
        </h4>
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="text-[11px] text-ink-soft hover:text-ink focus-visible:outline-none"
        >
          {expanded ? '收起' : '展开'}
        </button>
      </div>
      {actionError ? <ErrorNote message={actionError} /> : null}

      {expanded ? (
        <>
          <p className="mt-2 text-xs leading-relaxed text-ink-soft">
            每次生成或复盘都会保留为独立版本（当前第 {versionNo} 版），历史不会被覆盖。
          </p>
          <ul className="mt-2 space-y-1.5">
            {(revisions ?? []).map((revision) => (
              <li
                key={revision.version_no}
                className="flex items-center justify-between gap-2 rounded-lg bg-mist/50 px-2.5 py-1.5 text-xs"
              >
                <span className="min-w-0 truncate text-ink">
                  第 {revision.version_no} 版 · {revision.change_note}
                  {revision.has_review ? '（含复盘）' : ''}
                </span>
                <span className="shrink-0 text-[11px] text-ink-soft">{formatDue(revision.created_at)}</span>
              </li>
            ))}
            {revisions !== null && revisions.length === 0 ? (
              <li className="text-xs text-ink-soft">还没有版本记录。</li>
            ) : null}
          </ul>

          <button
            type="button"
            onClick={runReview}
            disabled={busy != null}
            className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {busy === 'review' ? '正在结合真实完成情况复盘……' : '让小鸥复盘这份计划'}
          </button>

          {review ? (
            <div className="mt-3 space-y-2 rounded-xl border border-line/80 bg-white/85 p-3 text-[13px] leading-relaxed">
              <p className="text-ink">{review.review_summary}</p>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-soft">
                <span>已完成 {review.real_stats.done ?? 0}</span>
                <span>已跳过 {review.real_stats.skipped ?? 0}</span>
                <span>进行中 {review.real_stats.pending ?? 0}</span>
                <span>已逾期 {review.real_stats.overdue ?? 0}</span>
              </div>
              <DirectionList label="已达成" items={review.achievements} />
              <DirectionList label="受阻" items={review.blocked} />
              <DirectionList label="下一步关注" items={review.next_focus} />
              {review.adjustments.length > 0 ? (
                <div>
                  <p className="text-xs font-semibold text-ink-soft">调整建议（勾选后采纳）</p>
                  <ul className="mt-1 space-y-1.5">
                    {review.adjustments.map((adjustment, index) => (
                      <li key={index} className="rounded-lg bg-mist/50 px-2.5 py-2">
                        <label className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            checked={selectedAdjustments.includes(index)}
                            onChange={(event) =>
                              setSelectedAdjustments((prev) =>
                                event.target.checked
                                  ? [...prev, index]
                                  : prev.filter((item) => item !== index),
                              )
                            }
                            className="mt-0.5 accent-[#4D83D6]"
                          />
                          <span className="min-w-0 text-xs leading-relaxed text-ink">
                            <strong>{adjustment.goal}</strong>
                            {adjustment.steps ? <span className="block text-ink-soft">{adjustment.steps}</span> : null}
                            <span className="mt-0.5 block text-[11px] text-ink-soft">
                              {adjustment.phase} 阶段
                              {adjustment.due_in_days ? ` · ${adjustment.due_in_days} 天内` : ''}
                              {adjustment.reason ? ` · ${adjustment.reason}` : ''}
                            </span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={applyAdjustments}
                    disabled={busy != null || selectedAdjustments.length === 0}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                    {busy === 'apply' ? '写入中……' : `采纳选中的 ${selectedAdjustments.length} 条（生成新版本）`}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}

// ---------- 能力图谱 ----------

const NODE_STATUS_META: Record<string, { label: string; className: string }> = {
  verified: { label: '已证实', className: 'bg-shallow/80 text-brand-700' },
  user_stated: { label: '用户自述', className: 'bg-mist text-brand-700' },
  ai_inferred: { label: 'AI 推断', className: 'border border-dashed border-line bg-white text-ink-soft' },
  pending: { label: '尚待验证', className: 'bg-mist/60 text-ink-soft' },
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  skill: '技能',
  required_skill: '岗位要求',
  experience: '经历',
  direction: '方向',
  target_position: '目标岗位',
  evidence: '证据',
  improvement_task: '提升任务',
}

const SOURCE_KIND_LABELS: Record<string, string> = {
  interview_report: '问澜报告',
  resume: '履历成章',
  job_analysis: '知岗解析',
  profile_fact: '档案事实',
  ai_suggest: 'AI 提议',
  user_manual: '手动添加',
  job_position: '知潮岗位',
  guide: '就业指导',
  knowledge_doc: '知藏文档',
  user_profile: '档案',
}

function sourceKindLabel(key: string): string {
  return SOURCE_KIND_LABELS[key] ?? key
}

/** 手动建边可选的关系类型（与后端 EDGE_RELATIONS 对齐）。 */
const EDGE_RELATION_LABELS: [string, string][] = [
  ['related_to', '相关（两个能力彼此关联）'],
  ['proves', '印证（经历/项目证明技能）'],
  ['requires', '要求（岗位/职业要求技能）'],
  ['targets', '指向（技能指向目标职业）'],
  ['practice_for', '练习服务于（任务服务技能）'],
  ['improves', '提升（练习提升能力）'],
]

function GraphTab({ refreshKey }: { refreshKey: number }) {
  const [graph, setGraph] = useState<CareerGraph | null>(null)
  const [busy, setBusy] = useState<'sync' | 'suggest' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [edgeDraft, setEdgeDraft] = useState<{ fromId: string; toId: string; relation: string }>({
    fromId: '',
    toId: '',
    relation: 'related_to',
  })

  const loadGraph = () => {
    return api.getCareerGraph().then((data) => setGraph(data))
  }

  useEffect(() => {
    loadGraph().catch((err) => {
      setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
    })
  }, [refreshKey])

  const runSync = () => {
    setBusy('sync')
    setActionError(null)
    api
      .syncCareerGraph()
      .then((data) => {
        setGraph(data)
        setBusy(null)
      })
      .catch((err) => {
        setBusy(null)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const runSuggest = () => {
    setBusy('suggest')
    setActionError(null)
    api
      .suggestCareerGraphNodes()
      .then((data) => {
        setGraph(data)
        setBusy(null)
      })
      .catch((err) => {
        setBusy(null)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const confirmNode = (node: CareerSkillNode) => {
    api
      .updateCareerGraphNode(node.id, { status: 'user_stated' })
      .then(() => loadGraph())
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const removeNode = (node: CareerSkillNode) => {
    if (!window.confirm(`删除节点「${node.name}」？相关连接也会一并移除。`)) return
    api
      .deleteCareerGraphNode(node.id)
      .then(() => loadGraph())
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const submitEdge = () => {
    const fromId = Number(edgeDraft.fromId)
    const toId = Number(edgeDraft.toId)
    if (!fromId || !toId || fromId === toId) {
      setActionError('请选择两个不同的节点，再建立关系')
      return
    }
    setActionError(null)
    api
      .addCareerGraphEdge({ from_node_id: fromId, to_node_id: toId, relation: edgeDraft.relation })
      .then((data) => {
        setGraph(data)
        setEdgeDraft((draft) => ({ ...draft, fromId: '', toId: '' }))
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const counts = graph?.status_counts ?? {}
  const nodes = graph?.nodes ?? []
  const statusOrder = ['verified', 'user_stated', 'ai_inferred', 'pending']

  return (
    <div className="space-y-4 pb-4">
      {actionError ? <ErrorNote message={actionError} /> : null}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={runSync}
          disabled={busy != null}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', busy === 'sync' && 'animate-spin')} aria-hidden="true" />
          同步我的真实数据
        </button>
        <button
          type="button"
          onClick={runSuggest}
          disabled={busy != null}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
        >
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          {busy === 'suggest' ? '提议中……' : 'AI 提议节点'}
        </button>
      </div>

      {graph !== null ? (
        <p className="text-[11px] leading-relaxed text-ink-soft">
          已证实 {counts.verified ?? 0} · 用户自述 {counts.user_stated ?? 0} · AI 推断{' '}
          {counts.ai_inferred ?? 0} · 尚待验证 {counts.pending ?? 0}。「已证实」只能来自真实练习结果，不能手工标记；AI
          提议必须给出材料依据，确认后才会成为自述。
        </p>
      ) : null}

      {graph === null ? (
        <p className="text-[13px] text-ink-soft">图谱加载中……</p>
      ) : nodes.length === 0 ? (
        <p className="rounded-xl bg-mist/50 px-3 py-3 text-[13px] leading-relaxed text-ink-soft">
          图谱还是空的。完成一场问澜面试、保存一份简历或解析一个岗位 JD 后，相关能力记录会自动出现在这里；也可以先点「同步我的真实数据」。
        </p>
      ) : (
        statusOrder.map((status) => {
          const group = nodes.filter((node) => node.status === status)
          if (group.length === 0) return null
          return (
            <section key={status}>
              <h4 className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-soft">
                {NODE_STATUS_META[status]?.label ?? status}
                <span className="font-normal">（{group.length}）</span>
              </h4>
              <ul className="mt-2 space-y-2">
                {group.map((node) => (
                  <li key={node.id} className="rounded-xl border border-line/80 bg-white/85 px-3 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-[13px] font-medium text-ink">{node.name}</span>
                      <span
                        className={cn(
                          'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium',
                          NODE_STATUS_META[node.status]?.className ?? '',
                        )}
                      >
                        {NODE_STATUS_META[node.status]?.label ?? node.status}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-ink-soft">
                      {ENTITY_TYPE_LABELS[node.entity_type] ?? node.entity_type} · 来源：
                      {sourceKindLabel(node.source_kind)}
                      {node.status === 'ai_inferred' && node.confidence ? ` · 置信度 ${node.confidence}` : ''}
                    </p>
                    {node.quote ? (
                      <p className="mt-1 border-l-2 border-line pl-2 text-[11px] italic leading-relaxed text-ink-soft">
                        依据：「{node.quote}」
                      </p>
                    ) : null}
                    {node.note ? <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">{node.note}</p> : null}
                    <div className="mt-1.5 flex items-center gap-3">
                      {node.status === 'ai_inferred' ? (
                        <button
                          type="button"
                          onClick={() => confirmNode(node)}
                          className="text-[11px] font-medium text-brand-600 hover:text-brand-700 focus-visible:outline-none"
                        >
                          确认这是我的能力
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => removeNode(node)}
                        className="text-[11px] text-ink-soft hover:text-brand-700 focus-visible:outline-none"
                      >
                        删除
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )
        })
      )}

      {graph !== null && nodes.length >= 2 ? (
        <section className="border-t border-line/70 pt-3">
          <h4 className="text-xs font-semibold text-ink-soft">手动建立关系</h4>
          <div className="mt-2 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <select
                value={edgeDraft.fromId}
                onChange={(event) => setEdgeDraft((d) => ({ ...d, fromId: event.target.value }))}
                aria-label="关系起点节点"
                className="rounded-lg border border-line bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
              >
                <option value="">起点节点……</option>
                {nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.name}
                  </option>
                ))}
              </select>
              <select
                value={edgeDraft.toId}
                onChange={(event) => setEdgeDraft((d) => ({ ...d, toId: event.target.value }))}
                aria-label="关系终点节点"
                className="rounded-lg border border-line bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
              >
                <option value="">终点节点……</option>
                {nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <select
                value={edgeDraft.relation}
                onChange={(event) => setEdgeDraft((d) => ({ ...d, relation: event.target.value }))}
                aria-label="关系类型"
                className="min-w-0 flex-1 rounded-lg border border-line bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
              >
                {EDGE_RELATION_LABELS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={submitEdge}
                className="shrink-0 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
              >
                建立关系
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-ink-soft">
              手动建立的关系会标注为「用户添加」，便于追溯；节点四态不因此改变。
            </p>
          </div>
        </section>
      ) : null}

      {graph !== null && graph.edges.length > 0 ? (
        <section className="border-t border-line/70 pt-3">
          <h4 className="text-xs font-semibold text-ink-soft">能力关系（带来源）</h4>
          <ul className="mt-2 space-y-1">
            {graph.edges.slice(0, 12).map((edge) => (
              <li key={edge.id} className="text-[11px] leading-relaxed text-ink-soft">
                {edge.from_name} → {edge.to_name}
                <span className="ml-1 text-brand-700">{edge.relation}</span>
                <span className="ml-1">（{sourceKindLabel(edge.source_kind)}）</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

// ---------- 多职业路径比较 ----------

function PathsTab({ refreshKey }: { refreshKey: number }) {
  const [records, setRecords] = useState<CareerPathComparison[] | null>(null)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [dirDraft, setDirDraft] = useState('')
  const [noteDraft, setNoteDraft] = useState('')
  const [comparing, setComparing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const aliveRef = useRef(true)

  const loadRecords = () => {
    return api.listCareerPathComparisons().then((items) => {
      if (aliveRef.current) setRecords(items)
    })
  }

  useEffect(() => {
    aliveRef.current = true
    loadRecords().catch(() => undefined)
    return () => {
      aliveRef.current = false
    }
  }, [refreshKey])

  const runCompare = () => {
    const directions = dirDraft
      .split(/[，,、\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (directions.length < 2) {
      setActionError('请至少填写两个职业方向（用逗号分隔）')
      return
    }
    setComparing(true)
    setActionError(null)
    api
      .compareCareerPaths({ directions: directions.slice(0, 4), note: noteDraft.trim() || undefined })
      .then((record) => {
        setRecords((prev) => (prev ? [record, ...prev] : [record]))
        setActiveId(record.id)
        setDirDraft('')
        setNoteDraft('')
        setComparing(false)
      })
      .catch((err) => {
        setComparing(false)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const removeRecord = (id: number) => {
    if (!window.confirm('删除这条比较记录？')) return
    api
      .deleteCareerPathComparison(id)
      .then(() => {
        setRecords((prev) => (prev ? prev.filter((item) => item.id !== id) : prev))
        setActiveId((current) => (current === id ? null : current))
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const active = records?.find((item) => item.id === activeId) ?? null

  return (
    <div className="space-y-4 pb-4">
      {actionError ? <ErrorNote message={actionError} /> : null}

      {!active ? (
        <>
          <section>
            <h3 className="text-sm font-semibold text-ink-strong">比较职业方向</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
              输入 2–4 个你犹豫的方向（用逗号分隔），小鸥会结合你的档案、知潮真实岗位与知藏资料做对比——不预测录用概率，只帮你把差异看清楚。
            </p>
            <textarea
              value={dirDraft}
              onChange={(event) => setDirDraft(event.target.value)}
              rows={2}
              placeholder="例如：数据分析，后端开发，产品经理"
              className="mt-2 w-full resize-none rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
            />
            <input
              value={noteDraft}
              onChange={(event) => setNoteDraft(event.target.value)}
              placeholder="补充你的偏好或限制（可选）：例如希望工作强度可控"
              className="mt-2 w-full rounded-lg border border-line bg-white px-2.5 py-2 text-[13px] text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
            />
            <button
              type="button"
              onClick={runCompare}
              disabled={comparing || !dirDraft.trim()}
              className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-full bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-card transition-all hover:bg-brand-700 hover:shadow-raised disabled:opacity-55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
            >
              <Compass className="h-4 w-4" aria-hidden="true" />
              {comparing ? '正在结合岗位资料比较……' : '开始比较'}
            </button>
          </section>

          {records === null ? (
            <p className="text-[13px] text-ink-soft">记录加载中……</p>
          ) : records.length === 0 ? (
            <p className="rounded-xl bg-mist/50 px-3 py-3 text-[13px] leading-relaxed text-ink-soft">
              还没有保存过方向比较。比较结果可以反复回看，帮你记录当时的选择背景。
            </p>
          ) : (
            <ul className="space-y-2.5">
              {records.map((record) => (
                <li key={record.id} className="group rounded-xl border border-line/80 bg-white/85 px-3.5 py-3">
                  <button
                    type="button"
                    onClick={() => setActiveId(record.id)}
                    className="w-full text-left focus-visible:outline-none"
                  >
                    <p className="text-sm font-semibold text-ink-strong group-hover:text-brand-700">{record.title}</p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      {record.directions.map((direction) => direction.name).join(' vs ')} · {formatDue(record.created_at)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <div>
          <button
            type="button"
            onClick={() => setActiveId(null)}
            className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-ink focus-visible:outline-none"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            返回列表
          </button>
          <h3 className="mt-2 text-sm font-semibold text-ink-strong">{active.title}</h3>
          {active.note ? <p className="mt-1 text-xs text-ink-soft">你的说明：{active.note}</p> : null}

          <div className="mt-3 space-y-3">
            {active.directions.map((direction) => (
              <div key={direction.name} className="rounded-xl border border-line/80 bg-white/85 p-3">
                <p className="text-sm font-semibold text-ink-strong">{direction.name}</p>
                {direction.relevance ? (
                  <p className="mt-1 text-[13px] leading-relaxed text-ink">{direction.relevance}</p>
                ) : null}
                {direction.skill_requirements.length > 0 ? (
                  <div className="mt-2">
                    <p className="text-xs font-semibold text-ink-soft">岗位技能要求（附来源）</p>
                    <ul className="mt-1 space-y-1">
                      {direction.skill_requirements.map((item, index) => (
                        <li key={index} className="text-[13px] leading-relaxed text-ink-soft">
                          {item.requirement}
                          {item.source ? <span className="ml-1 text-[11px] text-brand-700">—— {item.source}</span> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <DirectionList label="还缺的证据与实践" items={direction.evidence_gaps} />
                <DirectionList label="你说明的兴趣与限制" items={direction.interests_constraints} />
                {direction.learning_cost ? (
                  <p className="mt-2 text-xs leading-relaxed text-ink-soft">
                    学习/切换成本：<span className="text-ink">{direction.learning_cost}</span>
                  </p>
                ) : null}
                <DirectionList label="验证方向的下一步行动" items={direction.verification_actions} />
              </div>
            ))}

            {active.comparison?.recommendation ? (
              <div className="rounded-xl bg-mist/60 px-3 py-2.5 text-[13px] leading-relaxed text-ink">
                <p className="text-xs font-semibold text-brand-700">综合比较</p>
                {active.comparison.common?.length ? (
                  <p className="mt-1">共同点：{active.comparison.common.join('；')}</p>
                ) : null}
                {active.comparison.diverge?.length ? (
                  <p className="mt-0.5">差异：{active.comparison.diverge.join('；')}</p>
                ) : null}
                <p className="mt-0.5">建议：{active.comparison.recommendation}</p>
              </div>
            ) : null}

            {active.data_basis?.job_sources?.length ? (
              <div className="text-[11px] leading-relaxed text-ink-soft">
                <p className="font-semibold">本次比较依据的真实岗位来源</p>
                <ul className="mt-1 space-y-0.5">
                  {active.data_basis.job_sources.map((source, index) => (
                    <li key={index}>
                      {source.title}
                      {source.company ? `（${source.company}）` : ''}
                      {source.source_url ? (
                        <>
                          {' '}
                          <a
                            href={source.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-brand-700 underline-offset-4 hover:underline"
                          >
                            来源链接
                          </a>
                        </>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {active.data_basis?.disclaimer ? (
              <p className="text-[11px] leading-relaxed text-ink-soft">{active.data_basis.disclaimer}</p>
            ) : null}

            <button
              type="button"
              onClick={() => removeRecord(active.id)}
              className="inline-flex items-center gap-1 text-xs text-ink-soft hover:text-brand-700 focus-visible:outline-none"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              删除这份比较
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------- 知识检索 + 记忆透明化 ----------

function KnowledgeTab({ conversationId }: { conversationId: number | null }) {
  const [query, setQuery] = useState('')
  const [outcome, setOutcome] = useState<RetrievalOutcome | null>(null)
  const [searching, setSearching] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [stats, setStats] = useState<RetrievalStats | null>(null)
  const [showMemory, setShowMemory] = useState(false)
  const [memory, setMemory] = useState<MemoryUsage | null>(null)
  const [memoryLoading, setMemoryLoading] = useState(false)
  const [memoryQuery, setMemoryQuery] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const runSearch = () => {
    const text = query.trim()
    if (!text) return
    setSearching(true)
    setActionError(null)
    api
      .searchCareerKnowledge({ query: text })
      .then((data) => {
        setOutcome(data)
        setSearching(false)
      })
      .catch((err) => {
        setSearching(false)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const runSync = () => {
    setSyncing(true)
    setActionError(null)
    api
      .syncCareerRetrievalIndex()
      .then((data) => {
        setStats(data.stats)
        setSyncing(false)
      })
      .catch((err) => {
        setSyncing(false)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const loadMemory = () => {
    setMemoryLoading(true)
    setActionError(null)
    api
      .getCareerMemoryUsage({ conversation_id: conversationId, query: memoryQuery.trim() || undefined })
      .then((data) => {
        setMemory(data)
        setMemoryLoading(false)
      })
      .catch((err) => {
        setMemoryLoading(false)
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  const clearMemory = () => {
    if (
      !window.confirm(
        '确定清除全部对话记忆吗？所有知途会话与档案事实都会删除，之后小鸥不再引用它们。此操作不可撤销。',
      )
    )
      return
    api
      .clearCareerMemory()
      .then(({ deleted_conversations, deleted_facts }) => {
        setMemory(null)
        window.alert(`已清除 ${deleted_conversations} 个会话与 ${deleted_facts} 条档案事实。`)
      })
      .catch((err) => {
        setActionError(err instanceof ApiError ? err.message : '网络请求失败：无法连接后端服务')
      })
  }

  return (
    <div className="space-y-5 pb-4">
      {actionError ? <ErrorNote message={actionError} /> : null}

      <section>
        <h3 className="text-sm font-semibold text-ink-strong">岗位知识检索</h3>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
          在知潮真实岗位摘要、就业指导资料、知岗解析与知藏文档中做混合检索——每条结果都附来源与依据片段，检索不到会如实说明。
        </p>
        <div className="mt-2 flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                runSearch()
              }
            }}
            placeholder="例如：数据分析师需要什么技能"
            className="min-w-0 flex-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
          />
          <button
            type="button"
            onClick={runSearch}
            disabled={searching || !query.trim()}
            className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
          >
            {searching ? '检索中……' : '检索'}
          </button>
        </div>

        {outcome ? (
          outcome.found && outcome.results ? (
            <ul className="mt-3 space-y-2.5">
              {outcome.results.map((hit) => (
                <li key={hit.chunk_id} className="rounded-xl border border-line/80 bg-white/85 px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-[13px] font-semibold text-ink-strong">{hit.title}</span>
                    <span className="shrink-0 rounded-full bg-mist px-2 py-0.5 text-[11px] text-brand-700">
                      {sourceKindLabel(hit.source_kind)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink-soft">{hit.content}</p>
                  {hit.stale && hit.stale_note ? (
                    <p className="mt-1 text-[11px] text-amber-600">{hit.stale_note}</p>
                  ) : null}
                  <div className="mt-1 flex items-center justify-between text-[11px] text-ink-soft">
                    <span>
                      {hit.experience_level ? `经验：${hit.experience_level} · ` : ''}
                      相关度 {hit.final_score.toFixed(3)}
                    </span>
                    {hit.source_url ? (
                      <a
                        href={hit.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-brand-700 underline-offset-4 hover:underline"
                      >
                        查看来源 →
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 rounded-xl bg-mist/50 px-3 py-2.5 text-[13px] leading-relaxed text-ink-soft">
              {outcome.message ?? '没有找到相关资料。'}
            </p>
          )
        ) : null}

        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={runSync}
            disabled={syncing}
            className="inline-flex items-center gap-1 text-xs text-ink-soft transition-colors hover:text-brand-700 focus-visible:outline-none"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', syncing && 'animate-spin')} aria-hidden="true" />
            同步检索索引
          </button>
          {stats ? (
            <span className="text-[11px] text-ink-soft">
              共 {stats.total} 段（全局 {stats.global} · 我的 {stats.user}）
            </span>
          ) : null}
        </div>
      </section>

      <section className="border-t border-line/70 pt-4">
        <h3 className="text-sm font-semibold text-ink-strong">记忆用了什么</h3>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
          查看一次回答会带入哪些记忆：只有你确认过的事实和与当前问题相关的历史会进入上下文，未确认的归纳不会。
        </p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={() => {
              const next = !showMemory
              setShowMemory(next)
              if (next && memory === null) loadMemory()
            }}
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-ripple hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
          >
            {showMemory ? '收起预览' : '预览记忆分层'}
          </button>
        </div>
        {showMemory ? (
          <div className="mt-3 space-y-2">
            <input
              value={memoryQuery}
              onChange={(event) => setMemoryQuery(event.target.value)}
              placeholder="模拟提问（可选）：例如 我适合转数据分析吗"
              className="w-full rounded-lg border border-line bg-white px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
            />
            {memoryLoading ? <p className="text-xs text-ink-soft">加载中……</p> : null}
            {memory ? (
              <div className="space-y-2 text-[13px] leading-relaxed">
                <div>
                  <p className="text-xs font-semibold text-brand-700">已确认档案（{memory.layers.confirmed_facts.length}）</p>
                  {memory.layers.confirmed_facts.length === 0 ? (
                    <p className="mt-0.5 text-xs text-ink-soft">暂无已确认事实。</p>
                  ) : (
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-ink-soft">
                      {memory.layers.confirmed_facts.map((fact) => (
                        <li key={fact.id}>{fact.content}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink-soft">
                    相关历史召回（{memory.layers.related_history.length}）
                  </p>
                  {memory.layers.related_history.length === 0 ? (
                    <p className="mt-0.5 text-xs text-ink-soft">没有与该问题直接相关的历史消息。</p>
                  ) : (
                    <ul className="mt-1 space-y-0.5 text-xs text-ink-soft">
                      {memory.layers.related_history.map((item, index) => (
                        <li key={index} className="truncate">
                          「{item.conversation_title}」{item.content}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {memory.layers.session_summary ? (
                  <div>
                    <p className="text-xs font-semibold text-ink-soft">当前会话摘要</p>
                    <p className="mt-0.5 whitespace-pre-wrap text-xs text-ink-soft">{memory.layers.session_summary}</p>
                  </div>
                ) : null}
                <p className="text-[11px] text-ink-soft">近期完整消息窗口：{memory.layers.recent_window} 条</p>
                <p className="text-[11px] leading-relaxed text-ink-soft">{memory.note}</p>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="border-t border-line/70 pt-4">
        <button
          type="button"
          onClick={clearMemory}
          className="inline-flex items-center gap-1 text-xs text-ink-soft transition-colors hover:text-brand-700 focus-visible:outline-none"
        >
          <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
          清除全部记忆，重新开始
        </button>
        <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">
          会删除全部知途会话与档案事实；档案页的「清空记忆」只清事实，不清会话。
        </p>
      </section>
    </div>
  )
}
