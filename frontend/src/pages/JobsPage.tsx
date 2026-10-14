import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Library,
  Lightbulb,
  Link2,
  Loader2,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { Badge } from '../components/ui/Badge'
import { Button, ButtonLink } from '../components/ui/Button'
import { PageHeading, SectionHead, StatStrip } from '../components/editorial/Editorial'
import { EmptyState } from '../components/ui/EmptyState'
import { cn } from '../lib/cn'
import type {
  JobAnalysisDetail,
  JobAnalysisResult,
  JobAnalysisSummary,
  JobPosition,
  JobResumeMatchResponse,
  ResumeSummary,
  TrackedItem,
} from '../types'

const JD_MIN_LENGTH = 30
const JD_MAX_LENGTH = 20000
const UNSPECIFIED_TEXT = '未明确说明'

const DIFFICULTY_OPTIONS = [
  { value: 'basic', label: '基础' },
  { value: 'intermediate', label: '进阶' },
  { value: 'advanced', label: '高阶' },
] as const

type DifficultyChoice = (typeof DIFFICULTY_OPTIONS)[number]['value']

/** 解析结果中允许用户修改条目文本的四个分组（其余字段只读、原样传回）。 */
type EditableItemGroup = 'responsibilities' | 'required_skills' | 'preferred_skills' | 'tools'

const QUESTION_COUNT_OPTIONS = Array.from({ length: 8 }, (_, index) => index + 3)

const inputClasses =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25 disabled:cursor-not-allowed disabled:bg-slate-50'

const selectClasses =
  'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25 disabled:cursor-not-allowed disabled:bg-slate-50'

function isUnspecified(text: string): boolean {
  return text.trim() === UNSPECIFIED_TEXT
}

function formatShortDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

function InferredBadge() {
  return (
    <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
      模型推断
    </span>
  )
}

/** 单条带证据的解析结论：正文 + 模型推断徽标 + 原文依据（细线行，无卡片）。 */
function TrackedItemRow({ item }: { item: TrackedItem }) {
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-ink">{item.text}</p>
        {item.is_inferred ? <InferredBadge /> : null}
      </div>
      {item.evidence ? (
        <p className="mt-1.5 border-l-2 border-brand-200 pl-2.5 text-xs leading-relaxed text-ink-soft">
          原文：{item.evidence}
        </p>
      ) : (
        <p className="mt-1.5 text-xs text-slate-400">未找到原文依据</p>
      )}
    </li>
  )
}

function TrackedGroup({ title, items }: { title: string; items: TrackedItem[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="text-sm font-semibold text-ink-strong">{title}</h3>
      <ul className="mt-1 divide-y divide-line/70">
        {items.map((item, index) => (
          <TrackedItemRow key={`${index}-${item.text}`} item={item} />
        ))}
      </ul>
    </div>
  )
}

/** 经验 / 学历这类单条结论：弱化展示「未明确说明」，附证据与推断徽标。 */
function TrackedLine({ label, item }: { label: string; item: TrackedItem }) {
  const muted = isUnspecified(item.text)
  return (
    <div className="text-sm">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
        <span className="text-ink-soft">{label}：</span>
        <span className={muted ? 'text-slate-400' : 'font-medium text-ink'}>{item.text}</span>
        {item.is_inferred ? <InferredBadge /> : null}
      </div>
      {item.evidence ? (
        <p className="mt-1 border-l-2 border-brand-200 pl-2.5 text-xs leading-relaxed text-ink-soft">
          原文：{item.evidence}
        </p>
      ) : (
        <p className="mt-1 text-xs text-slate-400">未找到原文依据</p>
      )}
    </div>
  )
}

function StringListSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="mb-2.5 text-sm font-semibold text-ink-strong">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((item, index) => (
          <li key={`${index}-${item}`} className="flex gap-2 text-sm leading-relaxed text-ink">
            <span
              className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600/70"
              aria-hidden="true"
            />
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 解析结果正文：基本信息 + 分组条目 + 关键词标签。 */
function AnalysisResultBody({ result }: { result: JobAnalysisResult }) {
  return (
    <div className="space-y-7">
      <div className="space-y-2.5 border-b border-line/70 pb-6">
        <div className="flex flex-wrap items-baseline gap-x-1 text-sm">
          <span className="text-ink-soft">所属行业：</span>
          <span className={isUnspecified(result.industry) ? 'text-slate-400' : 'font-medium text-ink'}>
            {result.industry}
          </span>
        </div>
        <TrackedLine label="经验要求" item={result.experience_requirement} />
        <TrackedLine label="学历 / 资质" item={result.education_requirement} />
      </div>

      <TrackedGroup title="核心工作职责" items={result.responsibilities} />
      <TrackedGroup title="必需技能" items={result.required_skills} />
      <TrackedGroup title="加分技能" items={result.preferred_skills} />
      <TrackedGroup title="主要工具与技术" items={result.tools} />
      <StringListSection title="关键能力维度" items={result.capability_dimensions} />
      <StringListSection title="可能的面试方向" items={result.interview_directions} />

      {result.keywords.length > 0 ? (
        <div>
          <h3 className="mb-2.5 text-sm font-semibold text-ink-strong">岗位关键词</h3>
          <div className="flex flex-wrap gap-2">
            {result.keywords.map((keyword, index) => (
              <span
                key={`${index}-${keyword}`}
                className="rounded-full bg-mist px-3 py-1 text-xs font-medium text-ink"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

/** 编辑态分组条目：每条一个文本框；evidence 与 is_inferred 只读展示并原样保留传回。 */
function EditableTrackedGroup({
  title,
  items,
  onItemChange,
}: {
  title: string
  items: TrackedItem[]
  onItemChange: (index: number, text: string) => void
}) {
  if (items.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-semibold text-ink-strong">{title}</h3>
        <p className="mt-1 text-xs text-slate-400">该分组暂无条目</p>
      </div>
    )
  }
  return (
    <div>
      <h3 className="text-sm font-semibold text-ink-strong">{title}</h3>
      <ul className="mt-1 divide-y divide-line/70">
        {items.map((item, index) => (
          <li key={index} className="py-3 first:pt-0 last:pb-0">
            <input
              type="text"
              value={item.text}
              onChange={(event) => onItemChange(index, event.target.value)}
              aria-label={`${title} · 第 ${index + 1} 条`}
              className={inputClasses}
            />
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              {item.is_inferred ? <InferredBadge /> : null}
              {item.evidence ? (
                <p className="border-l-2 border-brand-200 pl-2.5 text-xs leading-relaxed text-ink-soft">
                  原文：{item.evidence}
                </p>
              ) : (
                <p className="text-xs text-slate-400">未找到原文依据</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 编辑态解析结果正文：岗位名称与四个分组条目文本可改，其余字段只读展示、原样传回。 */
function EditableResultBody({
  draft,
  onPositionNameChange,
  onItemTextChange,
}: {
  draft: JobAnalysisResult
  onPositionNameChange: (value: string) => void
  onItemTextChange: (group: EditableItemGroup, index: number, text: string) => void
}) {
  return (
    <div className="space-y-7">
      <div className="space-y-2.5 border-b border-line/70 pb-6">
        <div>
          <label
            htmlFor="job-edit-position-name"
            className="mb-1.5 block text-sm font-medium text-ink-strong"
          >
            岗位名称
          </label>
          <input
            id="job-edit-position-name"
            type="text"
            value={draft.position_name}
            onChange={(event) => onPositionNameChange(event.target.value)}
            maxLength={120}
            className={inputClasses}
          />
        </div>
        <p className="text-xs leading-relaxed text-ink-soft">
          仅岗位名称与下列条目文本可修改；各条原文依据与推断标记会原样保留，保存后服务端按同一证据标准重新核验。
        </p>
        <TrackedLine label="经验要求" item={draft.experience_requirement} />
        <TrackedLine label="学历 / 资质" item={draft.education_requirement} />
      </div>

      <EditableTrackedGroup
        title="核心工作职责"
        items={draft.responsibilities}
        onItemChange={(index, text) => onItemTextChange('responsibilities', index, text)}
      />
      <EditableTrackedGroup
        title="必需技能"
        items={draft.required_skills}
        onItemChange={(index, text) => onItemTextChange('required_skills', index, text)}
      />
      <EditableTrackedGroup
        title="加分技能"
        items={draft.preferred_skills}
        onItemChange={(index, text) => onItemTextChange('preferred_skills', index, text)}
      />
      <EditableTrackedGroup
        title="主要工具与技术"
        items={draft.tools}
        onItemChange={(index, text) => onItemTextChange('tools', index, text)}
      />
    </div>
  )
}

/** 联动「问澜」：依据解析结果生成面试题，成功后跳转面试会话。 */
function InterviewGenerateSection({ analysisId, position }: { analysisId: number; position: string }) {
  const navigate = useNavigate()
  const [difficulty, setDifficulty] = useState<DifficultyChoice>('intermediate')
  const [questionCount, setQuestionCount] = useState(5)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCreate = async () => {
    const trimmed = position.trim()
    if (!trimmed) {
      setError('请先在上方填写岗位名称，面试题将围绕它生成')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const task = await api.createInterviewFromJob(analysisId, {
        position: trimmed,
        difficulty,
        questionCount,
      })
      navigate(`/interview/${task.id}`)
    } catch (err) {
      setError(getErrorMessage(err, '面试题生成失败，请稍后再试'))
      setCreating(false)
    }
  }

  return (
    <div className="rounded-xl border border-line bg-white p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
        <Sparkles className="h-4 w-4 text-brand-600" aria-hidden="true" />
        依据此岗位生成面试题
      </h3>
      <p className="mt-1 text-xs leading-relaxed text-ink-soft">
        联动「问澜」：围绕岗位职责与技能生成模拟面试题，生成后进入面试会话。
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="job-difficulty" className="mb-1.5 block text-sm font-medium text-ink-strong">
            难度
          </label>
          <select
            id="job-difficulty"
            value={difficulty}
            onChange={(event) => setDifficulty(event.target.value as DifficultyChoice)}
            disabled={creating}
            className={selectClasses}
          >
            {DIFFICULTY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="job-question-count" className="mb-1.5 block text-sm font-medium text-ink-strong">
            题量
          </label>
          <select
            id="job-question-count"
            value={String(questionCount)}
            onChange={(event) => setQuestionCount(Number(event.target.value))}
            disabled={creating}
            className={selectClasses}
          >
            {QUESTION_COUNT_OPTIONS.map((count) => (
              <option key={count} value={String(count)}>
                {count} 道
              </option>
            ))}
          </select>
        </div>
      </div>
      {error ? (
        <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <div className="mt-4">
        <Button onClick={() => void handleCreate()} disabled={creating}>
          {creating ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          )}
          {creating ? '正在为你准备面试题…' : '生成面试题'}
        </Button>
      </div>
    </div>
  )
}

/** 联动「合契」：选择简历与岗位解析结果结构化匹配。 */
function ResumeMatchSection({ analysisId }: { analysisId: number }) {
  const [resumes, setResumes] = useState<ResumeSummary[]>([])
  const [resumesLoading, setResumesLoading] = useState(true)
  const [resumesError, setResumesError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [resumeId, setResumeId] = useState('')
  const [matching, setMatching] = useState(false)
  const [matchError, setMatchError] = useState<string | null>(null)
  const [matchResult, setMatchResult] = useState<JobResumeMatchResponse | null>(null)

  // 简历列表加载：挂载时初始 loading=true，重试时由事件处理器先行重置状态
  useEffect(() => {
    let active = true
    api
      .listResumes()
      .then((items) => {
        if (active) setResumes(items)
      })
      .catch((error: unknown) => {
        if (active) setResumesError(getErrorMessage(error, '简历列表加载失败'))
      })
      .finally(() => {
        if (active) setResumesLoading(false)
      })
    return () => {
      active = false
    }
  }, [reloadKey])

  const handleRetryResumes = () => {
    setResumesLoading(true)
    setResumesError(null)
    setReloadKey((key) => key + 1)
  }

  const handleMatch = async () => {
    const id = Number(resumeId)
    if (!resumeId || Number.isNaN(id)) {
      setMatchError('请先选择一份简历')
      return
    }
    setMatching(true)
    setMatchError(null)
    try {
      const result = await api.matchJobWithResume(analysisId, id)
      setMatchResult(result)
    } catch (err) {
      setMatchError(getErrorMessage(err, '匹配失败，请稍后再试'))
    } finally {
      setMatching(false)
    }
  }

  const score = matchResult?.match_score ?? null
  const scoreColor =
    score === null
      ? ''
      : score >= 75
        ? 'text-emerald-600'
        : score >= 50
          ? 'text-amber-600'
          : 'text-red-500'

  return (
    <div className="rounded-xl border border-line bg-white p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
        <Link2 className="h-4 w-4 text-brand-600" aria-hidden="true" />
        与简历匹配
      </h3>
      <p className="mt-1 text-xs leading-relaxed text-ink-soft">
        联动「合契」：将岗位要求与你现有的简历逐条对照，命中与缺口均有原文依据。
      </p>

      {resumesLoading ? (
        <p className="mt-4 flex items-center gap-2 text-sm text-ink-soft">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          正在加载简历列表…
        </p>
      ) : resumesError ? (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p role="alert" className="text-sm text-red-700">{resumesError}</p>
          <button
            type="button"
            onClick={handleRetryResumes}
            className="mt-1.5 flex items-center gap-1 text-xs font-medium text-red-700 hover:text-red-800"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            重新加载
          </button>
        </div>
      ) : resumes.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-line bg-white p-4 text-center">
          <p className="text-sm leading-relaxed text-ink-soft">
            还没有可用简历。先到「履历成章」创建一份简历，再回来与岗位要求逐条对照。
          </p>
          <ButtonLink to="/resume" variant="secondary" size="sm" className="mt-3">
            去创建简历
          </ButtonLink>
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="job-resume-select" className="mb-1.5 block text-sm font-medium text-ink-strong">
              选择简历
            </label>
            <select
              id="job-resume-select"
              value={resumeId}
              onChange={(event) => setResumeId(event.target.value)}
              disabled={matching}
              className={selectClasses}
            >
              <option value="">请选择简历</option>
              {resumes.map((resume) => (
                <option key={resume.id} value={String(resume.id)}>
                  {resume.title}（v{resume.current_version_no}）
                </option>
              ))}
            </select>
          </div>
          <Button onClick={() => void handleMatch()} disabled={matching || !resumeId}>
            {matching ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Link2 className="h-4 w-4" aria-hidden="true" />
            )}
            {matching ? '匹配进行中…' : '开始匹配'}
          </Button>
        </div>
      )}

      {matchError ? (
        <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {matchError}
        </p>
      ) : null}

      {matchResult ? (
        <div className="mt-5 space-y-6 border-t border-line pt-5">
          <div>
            <div className="flex items-end gap-3">
              <span className={`text-4xl font-bold ${scoreColor}`}>{matchResult.match_score}</span>
              <span className="pb-1 text-sm text-ink-soft">匹配度 / 100</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ink-soft">{matchResult.score_note}</p>
          </div>

          {matchResult.llm_error ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              AI 建议生成失败，已展示统计匹配结果。
            </p>
          ) : null}

          <div>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
              已匹配技能（{matchResult.matched_skills.length}）
            </h4>
            {matchResult.matched_skills.length === 0 ? (
              <p className="mt-2 text-sm text-ink-soft">未发现简历与岗位要求直接对应的技能。</p>
            ) : (
              <ul className="mt-2.5 space-y-2">
                {matchResult.matched_skills.map((item) => (
                  <li key={item.skill} className="rounded-lg bg-mist/60 px-3.5 py-3">
                    <p className="text-sm font-medium text-ink-strong">{item.skill}</p>
                    {item.evidence ? (
                      <p className="mt-1 text-xs leading-relaxed text-ink-soft">简历证据：{item.evidence}</p>
                    ) : null}
                    {item.job_evidence ? (
                      <p className="mt-1 text-xs leading-relaxed text-ink-soft">岗位证据：{item.job_evidence}</p>
                    ) : null}
                    {item.supporting_experiences && item.supporting_experiences.length > 0 ? (
                      <ul className="mt-1.5 space-y-1">
                        {item.supporting_experiences.map((experience, index) => (
                          <li key={`${index}-${experience}`} className="text-xs leading-relaxed text-ink-soft">
                            支撑经历：{experience}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
              <XCircle className="h-4 w-4 text-amber-600" aria-hidden="true" />
              岗位要求但简历未体现（{matchResult.missing_skills.length}）
            </h4>
            {matchResult.missing_skills.length === 0 ? (
              <p className="mt-2 text-sm text-ink-soft">岗位要求在简历中均有对应体现。</p>
            ) : (
              <ul className="mt-2.5 divide-y divide-line/70">
                {matchResult.missing_skills.map((item) => (
                  <li key={item.skill} className="py-3 first:pt-0 last:pb-0">
                    <p className="text-sm font-medium text-ink">{item.skill}</p>
                    {item.job_evidence ? (
                      <p className="mt-1 text-xs leading-relaxed text-ink-soft">岗位原文：{item.job_evidence}</p>
                    ) : null}
                    <p className="mt-1 text-xs leading-relaxed text-ink-soft">补充建议：{item.suggestion}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {matchResult.uncertain_items.length > 0 ? (
            <div>
              <h4 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
                <HelpCircle className="h-4 w-4 text-ink-soft" aria-hidden="true" />
                不能确定的项（{matchResult.uncertain_items.length}）
              </h4>
              <ul className="mt-2.5 divide-y divide-line/70">
                {matchResult.uncertain_items.map((item) => (
                  <li key={item.skill} className="py-3 first:pt-0 last:pb-0">
                    <p className="text-sm font-medium text-ink">{item.skill}</p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-soft">原因：{item.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {matchResult.suggestions.length > 0 ? (
            <div>
              <h4 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
                <Lightbulb className="h-4 w-4 text-brand-600" aria-hidden="true" />
                AI 建议
              </h4>
              <ol className="mt-2.5 divide-y divide-line/70">
                {matchResult.suggestions.map((suggestion, index) => (
                  <li key={`${index}-${suggestion}`} className="flex gap-2 py-2.5 text-sm leading-relaxed text-ink first:pt-0 last:pb-0">
                    <span className="font-semibold text-brand-600">{index + 1}.</span>
                    {suggestion}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

/** 从知潮岗位资料库选择真实岗位送入解析：列表与状态徽标均来自库内真实数据，绝不编造。 */
function PositionPickerSection({ onLoaded }: { onLoaded: (detail: JobAnalysisDetail) => void }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [positions, setPositions] = useState<JobPosition[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analyzingId, setAnalyzingId] = useState<number | null>(null)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  // 岗位解析：统一任务状态机（真实计时）
  const analyzeTask = useAsyncTask({ debugLabel: 'job-analyze' })

  const load = async (keyword: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.listJobPositions({ q: keyword, limit: 50 })
      setPositions(response.items)
    } catch (err) {
      setPositions([])
      setError(getErrorMessage(err, '岗位资料库加载失败，请稍后再试'))
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = () => {
    const next = !open
    setOpen(next)
    if (next) void load(query)
  }

  const handleSearch = () => {
    void load(query)
  }

  const handleAnalyze = async (position: JobPosition) => {
    if (analyzingId !== null) return
    setAnalyzingId(position.id)
    setAnalyzeError(null)
    await analyzeTask.run(async () => {
      const response = await api.analyzeJobFromPosition(position.id)
      const loaded = await api.getJobAnalysis(response.job_analysis_id)
      onLoaded(loaded)
    }, { timeoutMs: 180000 })
    setAnalyzingId(null)
    if (analyzeTask.error) {
      setAnalyzeError(analyzeTask.error)
    }
  }

  return (
    <section>
      <div className="rounded-xl border border-line bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
              <Library className="h-4 w-4 text-brand-600" aria-hidden="true" />
              从岗位资料库选择
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-ink-soft">
              联动「知潮」：库内岗位均来自可核验来源，选择后直接送入解析，招聘状态与时效如实标注。
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={handleToggle} aria-expanded={open}>
            {open ? (
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            )}
            {open ? '收起' : '展开选择'}
          </Button>
        </div>

        {open ? (
          <div className="mt-4 border-t border-line/70 pt-4">
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') handleSearch()
                }}
                placeholder="按岗位名称、公司、地点或技能搜索，回车确认"
                aria-label="搜索岗位资料库"
                className={inputClasses}
              />
              <Button variant="secondary" onClick={handleSearch} disabled={loading}>
                <Search className="h-4 w-4" aria-hidden="true" />
                搜索
              </Button>
            </div>

            {error ? (
              <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </p>
            ) : null}

            {analyzeTask.running ? (
              <AurelTaskStatus
                className="mt-3"
                title="岗位解析"
                scene="zhigang.analyze"
                status={analyzeTask.status}
                elapsedMs={analyzeTask.elapsedMs}
              />
            ) : null}

            {loading ? (
              <p className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                正在读取岗位资料库…
              </p>
            ) : error ? null : positions.length === 0 ? (
              <EmptyState
                icon={Search}
                title="没有匹配的岗位"
                description="资料库中暂无符合条件的岗位记录。可尝试更换关键词，或直接粘贴 JD 进行解析。"
                className="py-8"
              />
            ) : (
              <ul className="mt-1 divide-y divide-line/70">
                {positions.map((position) => {
                  const analyzing = analyzingId === position.id
                  const metaLine = [position.company, position.location, position.industry_name]
                    .filter(Boolean)
                    .join(' · ')
                  return (
                    <li key={position.id}>
                      <button
                        type="button"
                        onClick={() => void handleAnalyze(position)}
                        disabled={analyzingId !== null}
                        className="group flex w-full items-start gap-3 rounded-lg px-2 py-3 text-left transition-colors hover:bg-mist/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 disabled:cursor-wait disabled:opacity-70"
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-ink-strong transition-colors group-hover:text-brand-700">
                            {position.title}
                          </span>
                          {metaLine ? (
                            <span className="mt-0.5 block truncate text-xs text-ink-soft">{metaLine}</span>
                          ) : null}
                          <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                            <Badge tone="neutral">招聘状态未确认</Badge>
                            {position.stale_hint ? <Badge tone="preview">可能已过期</Badge> : null}
                          </span>
                        </span>
                        {analyzing ? (
                          <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-brand-600" aria-hidden="true" />
                        ) : (
                          <Briefcase className="mt-1 h-4 w-4 shrink-0 text-slate-400 transition-colors group-hover:text-brand-600" aria-hidden="true" />
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}

            {analyzeError ? (
              <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {analyzeError}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  )
}

export default function JobsPage() {
  const [histories, setHistories] = useState<JobAnalysisSummary[]>([])
  const [historiesLoading, setHistoriesLoading] = useState(true)
  const [historiesError, setHistoriesError] = useState<string | null>(null)
  const [historiesReloadKey, setHistoriesReloadKey] = useState(0)

  const [jdText, setJdText] = useState('')
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [inputError, setInputError] = useState<string | null>(null)

  const [detail, setDetail] = useState<JobAnalysisDetail | null>(null)
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [positionName, setPositionName] = useState('')
  const [positionNameSourceId, setPositionNameSourceId] = useState<number | null>(null)

  // 解析结果编辑态：draft 为完整 JobAnalysisResult 副本，未开放编辑的字段原样保留传回
  const [editingResult, setEditingResult] = useState(false)
  const [resultDraft, setResultDraft] = useState<JobAnalysisResult | null>(null)
  const [savingResult, setSavingResult] = useState(false)
  const [resultSaveError, setResultSaveError] = useState<string | null>(null)
  const [resultSaved, setResultSaved] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    document.title = '知岗 · 岗位解析 | 观澜 AUREL'
    return () => {
      document.title = '观澜 AUREL — AI 驱动的能力探索与成长平台'
    }
  }, [])

  // 历史记录加载：挂载时初始 loading=true，重试时由事件处理器先行重置状态
  useEffect(() => {
    let active = true
    api
      .listJobAnalyses()
      .then((items) => {
        if (active) setHistories(items)
      })
      .catch((error: unknown) => {
        if (active) setHistoriesError(getErrorMessage(error, '历史记录加载失败'))
      })
      .finally(() => {
        if (active) setHistoriesLoading(false)
      })
    return () => {
      active = false
    }
  }, [historiesReloadKey])

  const handleRetryHistories = () => {
    setHistoriesLoading(true)
    setHistoriesError(null)
    setHistoriesReloadKey((key) => key + 1)
  }

  // 切换展示的分析时，岗位名称默认取模型结果（render 阶段调整状态，遵循 React 官方推荐模式）
  if (detail && detail.id !== positionNameSourceId) {
    setPositionNameSourceId(detail.id)
    setPositionName(detail.result?.position_name ?? '')
  } else if (!detail && positionNameSourceId !== null) {
    setPositionNameSourceId(null)
    setPositionName('')
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    setInputError(null)
    try {
      const uploaded = await api.uploadJobFile(file)
      setJdText(uploaded.text)
      setUploadedFilename(uploaded.filename)
    } catch (err) {
      setInputError(getErrorMessage(err, '文件解析失败，请稍后再试'))
    } finally {
      setUploading(false)
    }
  }

  // 切换展示的解析记录时重置编辑态（在各打开记录的入口同步执行；保存成功后 id 不变不误清提示）
  const resetEditState = () => {
    setEditingResult(false)
    setResultDraft(null)
    setResultSaveError(null)
    setResultSaved(false)
  }

  const handleParse = async () => {
    const text = jdText.trim()
    if (text.length < JD_MIN_LENGTH) {
      setInputError(`岗位描述内容过短，至少需要 ${JD_MIN_LENGTH} 个字符（当前 ${text.length} 个），请补充完整后再解析`)
      return
    }
    if (text.length > JD_MAX_LENGTH) {
      setInputError(`岗位描述过长，不能超过 ${JD_MAX_LENGTH} 个字符（当前 ${text.length} 个），请精简后再解析`)
      return
    }
    setParsing(true)
    setInputError(null)
    try {
      const created = await api.analyzeJob(text)
      resetEditState()
      setDetail(created)
      setHistories((prev) => [created, ...prev])
    } catch (err) {
      setInputError(getErrorMessage(err, '解析失败，请稍后再试'))
    } finally {
      setParsing(false)
    }
  }

  const openDetail = async (id: number) => {
    setDetailLoadingId(id)
    setDetailError(null)
    try {
      const loaded = await api.getJobAnalysis(id)
      resetEditState()
      setDetail(loaded)
      setJdText(loaded.jd_text)
      setUploadedFilename(null)
    } catch (err) {
      setDetailError(getErrorMessage(err, '加载分析详情失败'))
    } finally {
      setDetailLoadingId(null)
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除这条岗位分析记录吗？删除后无法恢复。')) return
    try {
      await api.deleteJobAnalysis(id)
      setHistories((prev) => prev.filter((item) => item.id !== id))
      if (detail?.id === id) setDetail(null)
    } catch (err) {
      setHistoriesError(getErrorMessage(err, '删除失败'))
    }
  }

  // 从岗位资料库载入解析结果：复用现有 detail 展示链路，历史列表去重后置顶
  const handlePositionAnalysisLoaded = (loaded: JobAnalysisDetail) => {
    resetEditState()
    setDetail(loaded)
    setJdText(loaded.jd_text)
    setUploadedFilename(null)
    setInputError(null)
    setHistories((prev) => (prev.some((item) => item.id === loaded.id) ? prev : [loaded, ...prev]))
  }

  const handleToggleEdit = () => {
    if (editingResult) {
      setEditingResult(false)
      setResultDraft(null)
      setResultSaveError(null)
      return
    }
    if (!detail?.result) return
    setResultDraft({
      ...detail.result,
      responsibilities: detail.result.responsibilities.map((item) => ({ ...item })),
      required_skills: detail.result.required_skills.map((item) => ({ ...item })),
      preferred_skills: detail.result.preferred_skills.map((item) => ({ ...item })),
      tools: detail.result.tools.map((item) => ({ ...item })),
    })
    setResultSaveError(null)
    setResultSaved(false)
    setEditingResult(true)
  }

  const handleDraftPositionNameChange = (value: string) => {
    setResultDraft((prev) => (prev ? { ...prev, position_name: value } : prev))
  }

  const handleDraftItemTextChange = (group: EditableItemGroup, index: number, text: string) => {
    setResultDraft((prev) => {
      if (!prev) return prev
      const items = prev[group].map((item, i) => (i === index ? { ...item, text } : item))
      if (group === 'responsibilities') return { ...prev, responsibilities: items }
      if (group === 'required_skills') return { ...prev, required_skills: items }
      if (group === 'preferred_skills') return { ...prev, preferred_skills: items }
      return { ...prev, tools: items }
    })
  }

  const handleSaveResult = async () => {
    if (!detail || !resultDraft) return
    setSavingResult(true)
    setResultSaveError(null)
    try {
      const updated = await api.updateJobAnalysis(detail.id, { result: resultDraft })
      setDetail(updated)
      setEditingResult(false)
      setResultDraft(null)
      setResultSaved(true)
      setPositionName(updated.result?.position_name ?? positionName)
      setHistories((prev) =>
        prev.map((item) =>
          item.id === updated.id
            ? { ...item, title: updated.title, version_no: updated.version_no, status: updated.status }
            : item,
        ),
      )
    } catch (err) {
      setResultSaveError(getErrorMessage(err, '保存失败，请稍后再试'))
    } finally {
      setSavingResult(false)
    }
  }

  return (
    <div>
      <PageHeading
        kicker="知行"
        title="知岗"
        subtitle="读懂岗位所需，找准能力对应。解析结果均可回溯 JD 原文依据。"
      />

      <div className="mt-10 grid items-start gap-10 lg:grid-cols-12">
        {/* 左：解析历史 —— 细线行列表，无卡片 */}
        <aside className="lg:col-span-4">
          <SectionHead
            title="解析历史"
            note={historiesLoading ? '正在读取…' : `${histories.length} 条记录`}
          />
          {historiesError ? (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
              <p role="alert" className="text-xs leading-relaxed text-red-700">{historiesError}</p>
              <button
                type="button"
                onClick={handleRetryHistories}
                className="mt-1.5 flex items-center gap-1 text-xs font-medium text-red-700 hover:text-red-800"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                重新加载
              </button>
            </div>
          ) : null}
          {historiesLoading ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-ink-soft">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              正在读取…
            </div>
          ) : histories.length === 0 ? (
            <p className="mt-4 text-sm leading-relaxed text-ink-soft">
              还没有解析记录。粘贴一段岗位描述并解析，记录会出现在这里。
            </p>
          ) : (
            <ul className="mt-2">
              {histories.map((item) => (
                <li
                  key={item.id}
                  className="group -mx-3 flex items-start gap-2 border-b border-line/70 px-3 py-3.5 transition-colors last:border-b-0 hover:bg-white/70"
                >
                  <button
                    type="button"
                    onClick={() => void openDetail(item.id)}
                    disabled={detailLoadingId !== null}
                    className="min-w-0 flex-1 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 disabled:cursor-wait disabled:opacity-70"
                  >
                    <p
                      className={cn(
                        'truncate text-[15px] font-semibold transition-colors group-hover:text-brand-700',
                        detail?.id === item.id ? 'text-brand-700' : 'text-ink-strong',
                      )}
                    >
                      {item.title}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      v{item.version_no} · {formatShortDate(item.created_at)}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-soft">
                      {item.jd_preview}
                    </p>
                  </button>
                  <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
                    <Badge tone={item.status === 'ready' ? 'brand' : 'preview'}>
                      {item.status === 'ready' ? '就绪' : '失败'}
                    </Badge>
                    <button
                      type="button"
                      onClick={() => void handleDelete(item.id)}
                      className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                      aria-label={`删除 ${item.title}`}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {detailError ? (
            <p role="alert" className="mt-3 text-xs text-red-600">{detailError}</p>
          ) : null}
        </aside>

        {/* 右：资料库选择 + 解析输入与结果 */}
        <div className="min-w-0 space-y-10 lg:col-span-8">
          <PositionPickerSection onLoaded={handlePositionAnalysisLoaded} />
          <section>
            <SectionHead
              title="解析岗位描述"
              note="粘贴完整 JD（30–20000 字符），或上传 .txt / .docx / .pdf 文件，AI 将提炼岗位要点。"
            />
            <div className="mt-4 rounded-xl border border-line bg-white p-5 sm:p-6">
              <textarea
                id="jd-input"
                value={jdText}
                onChange={(event) => {
                  setJdText(event.target.value)
                  if (inputError) setInputError(null)
                }}
                rows={10}
                maxLength={JD_MAX_LENGTH}
                placeholder="粘贴招聘 JD：岗位职责、任职要求、技术栈、加分项…"
                className={cn(inputClasses, 'resize-y leading-relaxed')}
              />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.docx,.pdf"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0]
                      if (file) void handleUpload(file)
                      event.target.value = ''
                    }}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading || parsing}
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        提取文本中…
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4" aria-hidden="true" />
                        上传岗位描述文件
                      </>
                    )}
                  </Button>
                  {uploadedFilename ? <Badge tone="brand">{uploadedFilename}</Badge> : null}
                </div>
                <span className="text-xs text-ink-soft">{jdText.length}/{JD_MAX_LENGTH}</span>
              </div>
              {parsing ? (
                <p className="mt-3 flex items-center gap-2 text-sm text-brand-700">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  正在解读岗位要求，请稍候…
                </p>
              ) : null}
              {inputError ? (
                <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {inputError}
                </p>
              ) : null}
              <div className="mt-4 flex justify-end">
                <Button onClick={() => void handleParse()} disabled={parsing || uploading}>
                  {parsing ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Briefcase className="h-4 w-4" aria-hidden="true" />
                  )}
                  {parsing ? '正在解读岗位要求，请稍候…' : '解析岗位'}
                </Button>
              </div>
            </div>
          </section>

          {detail ? (
            <motion.div
              key={detail.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
            >
              {detail.result ? (
                <section>
                  <SectionHead
                    title="岗位解析结果"
                    note={
                      <>
                        {`${detail.title} · v${detail.version_no}${detail.model_name ? ` · 解析模型 ${detail.model_name}` : ''}`}
                        {detail.user_edited ? (
                          <Badge tone="brand" className="ml-2 align-middle">
                            已由用户修订
                          </Badge>
                        ) : null}
                      </>
                    }
                    action={
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={handleToggleEdit}
                          disabled={savingResult}
                        >
                          {editingResult ? (
                            <X className="h-4 w-4" aria-hidden="true" />
                          ) : (
                            <Pencil className="h-4 w-4" aria-hidden="true" />
                          )}
                          {editingResult ? '取消编辑' : '编辑解析'}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDetail(null)}>
                          <X className="h-4 w-4" aria-hidden="true" />
                          关闭
                        </Button>
                      </div>
                    }
                  />
                  <div className="mt-5 space-y-8">
                    {resultSaved ? (
                      <p className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                        已保存修改（证据标准不降低，无原文依据的条目仍标记为 AI 推断）
                      </p>
                    ) : null}
                    {resultSaveError ? (
                      <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        {resultSaveError}
                      </p>
                    ) : null}
                    {!editingResult ? (
                      <div>
                        <label
                          htmlFor="job-position-name"
                          className="mb-1.5 flex flex-wrap items-center gap-2 text-sm font-medium text-ink-strong"
                        >
                          岗位名称
                          <span className="text-xs font-normal text-ink-soft">
                            默认取自解析结果，可修改后用于生成面试题
                          </span>
                        </label>
                        <input
                          id="job-position-name"
                          type="text"
                          value={positionName}
                          onChange={(event) => setPositionName(event.target.value)}
                          maxLength={120}
                          placeholder="例如：前端工程师"
                          className={inputClasses}
                        />
                      </div>
                    ) : null}

                    <StatStrip
                      items={[
                        { label: '核心职责', value: detail.result.responsibilities.length },
                        { label: '必需技能', value: detail.result.required_skills.length },
                        { label: '加分技能', value: detail.result.preferred_skills.length },
                        { label: '工具技术', value: detail.result.tools.length },
                      ]}
                    />

                    {editingResult && resultDraft ? (
                      <EditableResultBody
                        draft={resultDraft}
                        onPositionNameChange={handleDraftPositionNameChange}
                        onItemTextChange={handleDraftItemTextChange}
                      />
                    ) : (
                      <AnalysisResultBody result={detail.result} />
                    )}

                    {editingResult && resultDraft ? (
                      <div className="flex flex-wrap items-center gap-3">
                        <Button onClick={() => void handleSaveResult()} disabled={savingResult}>
                          {savingResult ? (
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                          ) : (
                            <Save className="h-4 w-4" aria-hidden="true" />
                          )}
                          {savingResult ? '正在保存…' : '保存修改'}
                        </Button>
                        <p className="text-xs leading-relaxed text-ink-soft">
                          保存后将按同一证据标准重新核验，无原文依据的条目仍会标记为模型推断。
                        </p>
                      </div>
                    ) : null}

                    <InterviewGenerateSection analysisId={detail.id} position={positionName} />
                    <ResumeMatchSection analysisId={detail.id} />
                  </div>
                </section>
              ) : (
                <section>
                  <SectionHead
                    title="岗位解析未完成"
                    note={`${detail.title} · v${detail.version_no}`}
                    action={
                      <Button variant="ghost" size="sm" onClick={() => setDetail(null)}>
                        <X className="h-4 w-4" aria-hidden="true" />
                        关闭
                      </Button>
                    }
                  />
                  <div className="mt-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-medium text-red-800">本次解析未能完成</p>
                      <p className="mt-1 text-sm leading-relaxed text-red-700">
                        {detail.error_message ?? '解析过程出现异常，请重试。'}
                      </p>
                    </div>
                  </div>
                </section>
              )}
            </motion.div>
          ) : (
            <p className="text-sm leading-relaxed text-ink-soft">
              解析结果将在此呈现。粘贴或上传岗位描述并解析，AI 将提炼职责、技能、能力维度与面试方向。
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
