import {
  Building2,
  Check,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  FileUp,
  Info,
  Link2,
  Loader2,
  MapPin,
  Search,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import type {
  JobPosition,
  JobResumeMatchResponse,
  ResumeMatchResponse,
  ResumeSummary,
} from '../types'

const ACCEPTED_SUFFIXES = ['.pdf', '.docx', '.txt', '.md']

export function MatchingPage() {
  const [jobDescription, setJobDescription] = useState('')
  const [parsed, setParsed] = useState<{
    filename: string
    text: string
    position: string | null
    parseError: string | null
  } | null>(null)
  const [parsing, setParsing] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  // 拖拽匹配链路：统一任务状态机（真实计时、防重复提交）
  const matchTask = useAsyncTask({ debugLabel: 'matching-submit' })
  const submitting = matchTask.running
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ResumeMatchResponse | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<File | null>(null)

  useEffect(() => {
    document.title = '合契 · 简历匹配 | 观澜 AUREL'
    return () => {
      document.title = '观澜 AUREL — AI 驱动的能力探索与成长平台'
    }
  }, [])

  const handleFile = async (file: File) => {
    const lower = file.name.toLowerCase()
    if (!ACCEPTED_SUFFIXES.some((suffix) => lower.endsWith(suffix))) {
      setError('暂不支持该文件格式：请上传 PDF、Word（.docx）、TXT 或 Markdown 简历')
      return
    }
    fileRef.current = file
    setParsing(true)
    setError(null)
    setResult(null)
    try {
      const response = await api.parseResumeFile(file, jobDescription)
      setParsed({
        filename: response.filename,
        text: response.text,
        position: response.position,
        parseError: response.parse_error,
      })
    } catch (err) {
      setParsed(null)
      setError(err instanceof ApiError ? err.message : '简历解析失败，请稍后再试')
    } finally {
      setParsing(false)
    }
  }

  const handleSubmit = async () => {
    if (!parsed) return
    setError(null)
    await matchTask.run(async () => {
      // 拖拽时还没有 JD 的话，提交前带 JD 重新解析一次，自动补齐目标岗位
      let current = parsed
      if (!current.position && jobDescription.trim() && fileRef.current) {
        const response = await api.parseResumeFile(fileRef.current, jobDescription)
        current = {
          filename: response.filename,
          text: response.text,
          position: response.position,
          parseError: response.parse_error,
        }
        setParsed(current)
      }
      if (!current.position) {
        setError('未能自动识别目标岗位：请先粘贴岗位描述（JD），再重新拖入简历文件')
        return
      }
      const matchResult = await api.matchResume({
        position: current.position,
        jobDescription,
        resumeText: current.text,
      })
      setResult(matchResult)
    }, { timeoutMs: 180000 })
    if (matchTask.error) {
      setError(matchTask.error)
    }
  }

  const canSubmit = Boolean(parsed && !parsing && !submitting)
  const score = result?.match_score ?? null
  const scoreColor =
    score === null
      ? ''
      : score >= 75
        ? 'text-emerald-600'
        : score >= 50
          ? 'text-amber-600'
          : 'text-red-500'

  // ---------- 入口二：用资料库岗位匹配（与拖拽流程相互独立） ----------

  const [libraryQuery, setLibraryQuery] = useState('')
  const [positions, setPositions] = useState<JobPosition[]>([])
  const [positionsLoaded, setPositionsLoaded] = useState(false)
  const [positionsLoading, setPositionsLoading] = useState(true)
  const [positionsError, setPositionsError] = useState<string | null>(null)
  const [selectedPosition, setSelectedPosition] = useState<JobPosition | null>(null)
  const [resumes, setResumes] = useState<ResumeSummary[] | null>(null)
  const [resumesError, setResumesError] = useState<string | null>(null)
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null)
  const [positionMatching, setPositionMatching] = useState(false)
  // 资料库岗位匹配链路：统一任务状态机（真实计时）
  const positionMatchTask = useAsyncTask({ debugLabel: 'matching-position' })
  const [positionError, setPositionError] = useState<string | null>(null)
  const [positionResult, setPositionResult] = useState<JobResumeMatchResponse | null>(null)

  const searchPositions = useCallback(async (query: string) => {
    setPositionsLoading(true)
    setPositionsError(null)
    try {
      const response = await api.listJobPositions({ q: query, limit: 50 })
      setPositions(response.items)
      setPositionsLoaded(true)
      setSelectedPosition((current) =>
        current && response.items.some((item) => item.id === current.id) ? current : null,
      )
    } catch (err) {
      setPositionsError(err instanceof ApiError ? err.message : '岗位列表获取失败，请稍后再试')
    } finally {
      setPositionsLoading(false)
    }
  }, [])

  // 首次进入时加载岗位候选列表（loading 初始即为 true，setState 均在异步回调中；搜索按钮触发走 searchPositions）
  useEffect(() => {
    let cancelled = false
    api
      .listJobPositions({ q: '', limit: 50 })
      .then((response) => {
        if (cancelled) return
        setPositions(response.items)
        setPositionsLoaded(true)
      })
      .catch((err) => {
        if (!cancelled) {
          setPositionsError(err instanceof ApiError ? err.message : '岗位列表获取失败，请稍后再试')
        }
      })
      .finally(() => {
        if (!cancelled) setPositionsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .listResumes()
      .then((list) => {
        if (!cancelled) setResumes(list)
      })
      .catch((err) => {
        if (!cancelled) {
          setResumesError(err instanceof ApiError ? err.message : '简历列表获取失败，请稍后再试')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handlePositionMatch = async () => {
    if (!selectedPosition || selectedResumeId === null) return
    setPositionMatching(true)
    setPositionError(null)
    await positionMatchTask.run(async () => {
      const response = await api.matchPositionWithResume(selectedPosition.id, selectedResumeId)
      setPositionResult(response)
    }, { timeoutMs: 180000 })
    setPositionMatching(false)
    if (positionMatchTask.error) {
      setPositionError(positionMatchTask.error)
    }
  }

  const canPositionMatch = Boolean(selectedPosition && selectedResumeId !== null && !positionMatching)
  const positionScore = positionResult?.match_score ?? null
  const positionScoreColor =
    positionScore === null
      ? ''
      : positionScore >= 75
        ? 'text-emerald-600'
        : positionScore >= 50
          ? 'text-amber-600'
          : 'text-red-500'

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-strong">合契 · 简历匹配</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            拖入简历，自动解析目标岗位；简历与岗位相互映照：命中之处有原文为证，缺隙之处如实相告。
          </p>
        </div>
      </div>

      <Card>
        <CardHeader
          title="拖入简历，自动匹配"
          description="无需手动输入：拖拽或点击选择简历文件，AI 自动识别岗位并解析内容。"
        />
        <CardBody className="space-y-5">
          <div
            role="button"
            tabIndex={0}
            aria-label="拖拽或点击选择简历文件"
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                fileInputRef.current?.click()
              }
            }}
            onDragOver={(event) => {
              event.preventDefault()
              setDragActive(true)
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragActive(false)
              const file = event.dataTransfer.files?.[0]
              if (file) void handleFile(file)
            }}
            className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${
              dragActive
                ? 'border-brand-600 bg-brand-50/80'
                : 'border-line bg-surface/70 hover:border-brand-500 hover:bg-brand-50/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void handleFile(file)
                event.target.value = ''
              }}
            />
            {parsing ? (
              <>
                <Loader2 className="mx-auto h-8 w-8 animate-spin text-brand-600" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink-strong">正在解析简历…</p>
                <p className="mt-1 text-xs text-ink-soft">正在提取文本并识别目标岗位，请稍候</p>
              </>
            ) : (
              <>
                <FileUp className="mx-auto h-8 w-8 text-brand-500" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink-strong">把简历文件拖到这里，自动解析</p>
                <p className="mt-1 text-xs text-ink-soft">
                  支持 PDF、Word（.docx）、TXT、Markdown · 全程无需手动输入
                </p>
              </>
            )}
          </div>

          {parsed && !parsing ? (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-brand-50/50 px-4 py-3">
              <Badge tone="brand">{parsed.filename}</Badge>
              {parsed.position ? (
                <span className="text-sm text-ink">
                  已识别目标岗位：<span className="font-semibold text-ink-strong">{parsed.position}</span>
                </span>
              ) : parsed.parseError ? (
                <span className="text-sm text-red-600">{parsed.parseError}</span>
              ) : (
                <span className="text-sm text-amber-600">
                  简历已解析，但未识别出目标岗位 — 可粘贴下方岗位描述后再匹配
                </span>
              )}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="ml-auto text-xs font-medium text-brand-600 underline-offset-2 hover:underline"
              >
                重新选择文件
              </button>
            </div>
          ) : null}

          <div>
            <label htmlFor="match-jd" className="mb-1.5 block text-sm font-medium text-ink-strong">
              岗位描述<span className="ml-1.5 text-xs font-normal text-ink-soft">
                选填，粘贴后岗位识别与匹配更准
              </span>
            </label>
            <textarea
              id="match-jd"
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
              rows={4}
              maxLength={4000}
              placeholder="粘贴招聘 JD：职责要求、技术栈、加分项…（不填也可，AI 会从简历自动识别岗位）"
              className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm leading-relaxed text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
            />
          </div>

          {error ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end">
            <Button onClick={() => void handleSubmit()} disabled={!canSubmit}>
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Link2 className="h-4 w-4" aria-hidden="true" />
              )}
              {submitting ? '映照进行中…' : '开始匹配'}
            </Button>
          </div>

          {matchTask.running ? (
            <AurelTaskStatus
              className="mt-4"
              title="简历与岗位映照"
              scene="heqi.match"
              status={matchTask.status}
              elapsedMs={matchTask.elapsedMs}
            />
          ) : null}
        </CardBody>
      </Card>

      {result ? (
        <Card>
          <CardHeader
            title="匹配结果"
            description={
              result.llm_error
                ? 'AI 建议生成失败，以下为统计匹配结果（如实降级）'
                : result.model_name
                  ? `含 AI 建议（${result.model_name}）`
                  : '统计匹配结果'
            }
            action={
              <div className="text-right">
                <p className={`text-3xl font-bold ${scoreColor}`}>{result.match_score}</p>
                <p className="text-xs text-ink-soft">匹配度 / 100</p>
              </div>
            }
          />
          <CardBody className="space-y-6">
            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                命中技能（{result.matched_skills.length}）
              </h3>
              {result.matched_skills.length === 0 ? (
                <p className="text-sm text-ink-soft">未发现与岗位要求直接对应的技能。</p>
              ) : (
                <ul className="space-y-2.5">
                  {result.matched_skills.map((skill) => (
                    <li key={skill.skill} className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3">
                      <p className="text-sm font-medium text-emerald-800">{skill.skill}</p>
                      {skill.evidence ? (
                        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                          简历依据：{skill.evidence}
                        </p>
                      ) : null}
                      {skill.job_evidence ? (
                        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                          岗位依据：{skill.job_evidence}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {result.missing_skills.length > 0 ? (
              <div>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                  <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />
                  岗位要求但简历未体现（{result.missing_skills.length}）
                </h3>
                <div className="flex flex-wrap gap-2">
                  {result.missing_skills.map((skill) => (
                    <span
                      key={skill}
                      className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/20"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {result.suggestions.length > 0 ? (
              <div>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                  <Sparkles className="h-4 w-4 text-brand-600" aria-hidden="true" />
                  提升建议
                </h3>
                <ul className="space-y-2">
                  {result.suggestions.map((suggestion, index) => (
                    <li
                      key={suggestion}
                      className="flex gap-2 rounded-lg bg-surface p-3 text-sm leading-relaxed text-ink"
                    >
                      <span className="font-semibold text-brand-600">{index + 1}.</span>
                      {suggestion}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={FileSearch}
            title="结果将在此呈现"
            description="每一项命中都附有简历与岗位的原文依据，一目了然。"
          />
        </Card>
      )}

      <Card>
        <CardHeader
          title="用资料库岗位匹配"
          description="从知潮资料库选择来源可核验的真实岗位，搭配履历成章中的简历进行匹配：命中与缺隙皆有原文为证。"
        />
        <CardBody className="space-y-5">
          <div>
            <label htmlFor="library-position-q" className="mb-1.5 block text-sm font-medium text-ink-strong">
              搜索岗位
              <span className="ml-1.5 text-xs font-normal text-ink-soft">输入关键词后回车或点击搜索</span>
            </label>
            <div className="flex gap-2">
              <input
                id="library-position-q"
                value={libraryQuery}
                onChange={(event) => setLibraryQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void searchPositions(libraryQuery)
                  }
                }}
                placeholder="按职位名称、公司、城市或技能关键词搜索…"
                className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
              />
              <Button
                variant="secondary"
                onClick={() => void searchPositions(libraryQuery)}
                disabled={positionsLoading}
              >
                {positionsLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Search className="h-4 w-4" aria-hidden="true" />
                )}
                搜索
              </Button>
            </div>
          </div>

          {positionsError ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {positionsError}
            </p>
          ) : positionsLoading && positions.length === 0 ? (
            <p className="flex items-center gap-2 text-sm text-ink-soft">
              <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-hidden="true" />
              正在加载岗位…
            </p>
          ) : positionsLoaded && positions.length === 0 ? (
            <EmptyState
              icon={Search}
              title="没有找到符合条件的岗位"
              description="资料库中没有匹配该关键词的岗位，可以更换关键词重试。资料库只收录来源可核验的真实岗位，没有数据时如实显示空状态。"
            />
          ) : positions.length > 0 ? (
            <ul className="max-h-80 divide-y divide-line/70 overflow-y-auto rounded-lg border border-line bg-surface/50">
              {positions.map((position) => {
                const selected = selectedPosition?.id === position.id
                return (
                  <li key={position.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedPosition(position)}
                      aria-pressed={selected}
                      className={`w-full px-4 py-3 text-left transition-colors hover:bg-brand-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-600/40 ${
                        selected ? 'bg-brand-50/60' : ''
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        {selected ? (
                          <Check className="h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
                        ) : null}
                        <span className="text-sm font-semibold text-ink-strong">{position.title}</span>
                        <span className="flex items-center gap-1 text-xs text-ink-soft">
                          <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
                          {position.company}
                        </span>
                        {position.location ? (
                          <span className="flex items-center gap-1 text-xs text-ink-soft">
                            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                            {position.location}
                          </span>
                        ) : null}
                        {position.industry_name ? <Badge tone="brand">{position.industry_name}</Badge> : null}
                        <Badge tone="preview">招聘状态未确认</Badge>
                        {position.stale_hint ? <Badge tone="preview">可能已过期</Badge> : null}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          ) : null}

          <div>
            <label htmlFor="library-resume" className="mb-1.5 block text-sm font-medium text-ink-strong">
              选择简历
            </label>
            <select
              id="library-resume"
              value={selectedResumeId ?? ''}
              onChange={(event) =>
                setSelectedResumeId(event.target.value ? Number(event.target.value) : null)
              }
              disabled={resumes === null || resumes.length === 0}
              className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
            >
              <option value="">
                {resumes === null
                  ? resumesError
                    ? '简历列表加载失败'
                    : '正在加载简历…'
                  : resumes.length === 0
                    ? '暂无可用简历'
                    : '请选择一份简历…'}
              </option>
              {(resumes ?? []).map((resume) => (
                <option key={resume.id} value={resume.id}>
                  {resume.title}
                </option>
              ))}
            </select>
            {resumesError ? (
              <p role="alert" className="mt-1.5 text-sm text-red-600">
                {resumesError}
              </p>
            ) : resumes !== null && resumes.length === 0 ? (
              <p className="mt-1.5 text-sm text-amber-600">请先在履历成章创建简历</p>
            ) : null}
          </div>

          {selectedPosition ? (
            <p className="text-xs text-ink-soft">
              已选岗位：
              <span className="font-medium text-ink-strong">
                {selectedPosition.title}（{selectedPosition.company}）
              </span>
            </p>
          ) : null}

          {positionError ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {positionError}
            </p>
          ) : null}

          <div className="flex justify-end">
            <Button onClick={() => void handlePositionMatch()} disabled={!canPositionMatch}>
              {positionMatching ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Link2 className="h-4 w-4" aria-hidden="true" />
              )}
              {positionMatching ? '映照进行中…' : '开始匹配'}
            </Button>
          </div>

          {positionMatchTask.running ? (
            <AurelTaskStatus
              className="mt-4"
              title="资料库岗位映照"
              scene="heqi.match"
              status={positionMatchTask.status}
              elapsedMs={positionMatchTask.elapsedMs}
            />
          ) : null}
        </CardBody>
      </Card>

      {positionResult ? (
        <Card>
          <CardHeader
            title="资料库岗位匹配结果"
            description={
              positionResult.llm_error
                ? 'AI 建议生成失败，以下为统计匹配结果（如实降级）'
                : positionResult.model_name
                  ? `含 AI 建议（${positionResult.model_name}）`
                  : '统计匹配结果'
            }
            action={
              <div className="text-right">
                <p className={`text-3xl font-bold ${positionScoreColor}`}>
                  {positionResult.match_score}
                </p>
                <p className="text-xs text-ink-soft">匹配度 / 100</p>
              </div>
            }
          />
          <CardBody className="space-y-6">
            <p className="text-sm text-ink-soft">
              简历「{positionResult.resume_title}」
              {selectedPosition ? (
                <>
                  {' × '}
                  <span className="font-medium text-ink-strong">
                    {selectedPosition.title}（{selectedPosition.company}）
                  </span>
                </>
              ) : null}
            </p>

            <div>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                命中技能（{positionResult.matched_skills.length}）
              </h3>
              {positionResult.matched_skills.length === 0 ? (
                <p className="text-sm text-ink-soft">未发现与岗位要求直接对应的技能。</p>
              ) : (
                <ul className="space-y-2.5">
                  {positionResult.matched_skills.map((skill) => (
                    <li key={skill.skill} className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3">
                      <p className="text-sm font-medium text-emerald-800">{skill.skill}</p>
                      {skill.evidence ? (
                        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                          简历依据：{skill.evidence}
                        </p>
                      ) : null}
                      {skill.job_evidence ? (
                        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                          岗位依据：{skill.job_evidence}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {positionResult.missing_skills.length > 0 ? (
              <div>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                  <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />
                  岗位要求但简历未体现（{positionResult.missing_skills.length}）
                </h3>
                <ul className="space-y-2.5">
                  {positionResult.missing_skills.map((item) => (
                    <li key={item.skill} className="rounded-lg border border-red-100 bg-red-50/50 p-3">
                      <p className="text-sm font-medium text-red-800">{item.skill}</p>
                      {item.job_evidence ? (
                        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                          岗位依据：{item.job_evidence}
                        </p>
                      ) : null}
                      <p className="mt-1 text-xs leading-relaxed text-ink-soft">建议：{item.suggestion}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {positionResult.uncertain_items.length > 0 ? (
              <div>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                  <CircleAlert className="h-4 w-4 text-amber-600" aria-hidden="true" />
                  难以判定（{positionResult.uncertain_items.length}）
                </h3>
                <ul className="space-y-2">
                  {positionResult.uncertain_items.map((item) => (
                    <li key={item.skill} className="rounded-lg bg-amber-50/60 p-3">
                      <p className="text-sm font-medium text-amber-800">{item.skill}</p>
                      <p className="mt-1 text-xs leading-relaxed text-ink-soft">{item.reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {positionResult.suggestions.length > 0 ? (
              <div>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                  <Sparkles className="h-4 w-4 text-brand-600" aria-hidden="true" />
                  提升建议
                </h3>
                <ul className="space-y-2">
                  {positionResult.suggestions.map((suggestion, index) => (
                    <li
                      key={suggestion}
                      className="flex gap-2 rounded-lg bg-surface p-3 text-sm leading-relaxed text-ink"
                    >
                      <span className="font-semibold text-brand-600">{index + 1}.</span>
                      {suggestion}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="flex gap-2 rounded-lg bg-surface p-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
              <p className="text-xs leading-relaxed text-ink-soft">{positionResult.score_note}</p>
            </div>
          </CardBody>
        </Card>
      ) : null}
    </div>
  )
}
