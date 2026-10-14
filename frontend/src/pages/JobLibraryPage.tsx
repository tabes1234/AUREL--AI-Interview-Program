import {
  AlertTriangle,
  Building2,
  Clock,
  Compass,
  ExternalLink,
  History,
  Link2,
  Loader2,
  MapPin,
  MessageSquareText,
  Plus,
  Puzzle,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  Waves,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { AiStatusBadge } from '../components/AiStatusBadge'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { TextAreaField, TextField } from '../components/ui/Field'
import type {
  CatalogIndustry,
  JobPosition,
  JobPositionDetail,
  ResumeSummary,
} from '../types'

const SOURCE_TYPE_LABEL: Record<JobPosition['source_type'], string> = {
  official_seed: '官方页面核对',
  user_import: '用户导入',
  manual: '手动录入',
}

const LINK_STATUS_LABEL: Record<JobPosition['link_status'], string> = {
  ok: '链接可用',
  stale: '待核验',
  dead: '来源失效',
  no_link: '无来源链接',
  unverified: '未核验',
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('zh-CN')
}

interface Filters {
  q: string
  industry_id: string
  company: string
  location: string
  stage: string
}

const EMPTY_FILTERS: Filters = { q: '', industry_id: '', company: '', location: '', stage: '' }

const EMPTY_FORM = {
  company: '',
  title: '',
  location: '',
  level: '',
  sourceUrl: '',
  responsibilities: '',
  requiredSkills: '',
  preferredSkills: '',
  experience: '',
  jdFullText: '',
}

/** 检索条件键：标识「列表结果属于哪一次筛选」，用于推导加载态。 */
function makeListKey(filters: Filters, favoritesOnly: boolean, reload: number): string {
  return [
    filters.q,
    filters.industry_id,
    filters.company,
    filters.location,
    filters.stage,
    favoritesOnly ? 'fav' : 'all',
    String(reload),
  ].join('|')
}

export default function JobLibraryPage() {
  const navigate = useNavigate()
  const [industries, setIndustries] = useState<CatalogIndustry[]>([])
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [reload, setReload] = useState(0)

  // 加载态由「结果归属键」推导：返回结果的筛选条件与当前不一致即视为加载中，
  // 避免 effect 内同步 setState 触发级联渲染
  const listKey = makeListKey(applied, favoritesOnly, reload)
  const [listState, setListState] = useState<{
    key: string
    items: JobPosition[]
    total: number
    error: string | null
  }>({ key: '', items: [], total: 0, error: null })
  const loading = listState.key !== listKey
  const listError = loading ? null : listState.error

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<JobPositionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [importOpen, setImportOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  const [resumes, setResumes] = useState<ResumeSummary[]>([])
  const [resumeId, setResumeId] = useState('')
  const [matchResult, setMatchResult] = useState<
    Awaited<ReturnType<typeof api.matchPositionWithResume>> | null
  >(null)

  useEffect(() => {
    document.title = '知潮 · 岗位资料库 | 观澜 AUREL'
    return () => {
      document.title = '观澜 AUREL — AI 驱动的能力探索与成长平台'
    }
  }, [])

  useEffect(() => {
    api
      .listIndustries()
      .then(setIndustries)
      .catch(() => setIndustries([]))
  }, [])

  useEffect(() => {
    let cancelled = false
    const key = makeListKey(applied, favoritesOnly, reload)
    const loader = favoritesOnly
      ? api.listFavoritePositions()
      : api.listJobPositions({
          q: applied.q,
          industry_id: applied.industry_id || undefined,
          company: applied.company,
          location: applied.location,
          stage: applied.stage || undefined,
          limit: 50,
        })
    loader
      .then((response) => {
        if (!cancelled) {
          setListState({ key, items: response.items, total: response.total, error: null })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setListState({
            key,
            items: [],
            total: 0,
            error: err instanceof ApiError ? err.message : '岗位目录加载失败，请稍后再试',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [applied, favoritesOnly, reload])

  const openDetail = useCallback(
    (id: number) => {
      setSelectedId(id)
      setMatchResult(null)
      setActionError(null)
      setNotice(null)
      setDetailLoading(true)
      api
        .getJobPosition(id)
        .then(setDetail)
        .catch((err) => {
          setDetail(null)
          setActionError(err instanceof ApiError ? err.message : '岗位详情加载失败')
        })
        .finally(() => setDetailLoading(false))
    },
    [],
  )

  const refreshDetail = useCallback(async (id: number) => {
    const fresh = await api.getJobPosition(id)
    setDetail(fresh)
    return fresh
  }, [])

  const toggleFavorite = async (position: JobPosition) => {
    setBusy(`fav:${position.id}`)
    try {
      await api.toggleJobFavorite(position.id, position.is_favorited)
      const favorited = !position.is_favorited
      setListState((prev) => {
        if (prev.key !== listKey) return prev
        const items = favoritesOnly
          ? prev.items.filter((item) => item.id !== position.id)
          : prev.items.map((item) =>
              item.id === position.id ? { ...item, is_favorited: favorited } : item,
            )
        return { ...prev, items }
      })
      if (detail?.id === position.id) await refreshDetail(position.id)
      if (favoritesOnly) setReload((n) => n + 1)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '收藏操作失败，请稍后再试')
    } finally {
      setBusy(null)
    }
  }

  const verifySource = async (position: JobPosition) => {
    setBusy(`verify:${position.id}`)
    setActionError(null)
    setNotice(null)
    try {
      const fresh = await api.verifyJobPosition(position.id)
      setNotice(`来源链接核验完成：${LINK_STATUS_LABEL[fresh.link_status]}。核验只判断链接是否可打开，招聘状态仍以企业官方页面为准。`)
      await refreshDetail(position.id)
      setReload((n) => n + 1)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '来源核验失败，请稍后再试')
    } finally {
      setBusy(null)
    }
  }

  const analyzePosition = async (position: JobPosition) => {
    setBusy(`analyze:${position.id}`)
    setActionError(null)
    setNotice(null)
    try {
      const result = await api.analyzeJobFromPosition(position.id)
      setNotice(
        result.reused
          ? `已复用「${result.position_name}」的知岗解析（记录 #${result.job_analysis_id}），可前往知岗查看或修改。`
          : `知岗解析完成（记录 #${result.job_analysis_id}）：职责、技能与经验均可追溯至岗位原文证据。`,
      )
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '知岗解析失败，请稍后再试')
    } finally {
      setBusy(null)
    }
  }

  const createInterviewTask = async (position: JobPosition) => {
    setBusy(`interview:${position.id}`)
    setActionError(null)
    try {
      const task = await api.createInterviewFromPosition(position.id)
      void navigate(`/interview/${task.id}`)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '题集生成失败，请稍后再试')
      setBusy(null)
    }
  }

  const createCareerPlan = async (position: JobPosition) => {
    setBusy(`plan:${position.id}`)
    setActionError(null)
    setNotice(null)
    try {
      const result = await api.createCareerPlanFromPosition(position.id)
      setNotice(
        `${result.reused_analysis ? '已复用' : '已完成'}岗位解析（记录 #${result.job_analysis_id}），并在知途创建行动计划「${result.plan_title}」，可前往知途查看与调整。`,
      )
      setTimeout(() => void navigate('/career-guide'), 1200)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '知途规划生成失败，请稍后再试')
    } finally {
      setBusy(null)
    }
  }

  const loadResumes = useCallback(async () => {
    try {
      const list = await api.listResumes()
      setResumes(list)
      if (list.length > 0) setResumeId((current) => current || String(list[0].id))
    } catch {
      setResumes([])
    }
  }, [])

  const matchWithResume = async (position: JobPosition) => {
    if (!resumeId) {
      setActionError('请先在履历成章创建一份简历，再进行合契匹配')
      return
    }
    setBusy(`match:${position.id}`)
    setActionError(null)
    setNotice(null)
    try {
      const result = await api.matchPositionWithResume(position.id, Number(resumeId))
      setMatchResult(result)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '合契匹配失败，请稍后再试')
    } finally {
      setBusy(null)
    }
  }

  const submitImport = async () => {
    if (!form.company.trim() || !form.title.trim()) {
      setImportError('来源企业与岗位名称为必填项')
      return
    }
    if (!form.sourceUrl.trim() && !form.responsibilities.trim() && !form.requiredSkills.trim() && !form.jdFullText.trim()) {
      setImportError('请提供可验证的来源链接，或至少填写职责/技能摘要；不允许导入空岗位')
      return
    }
    setImporting(true)
    setImportError(null)
    try {
      const response = await api.importJobPosition({
        company: form.company.trim(),
        title: form.title.trim(),
        location: form.location.trim(),
        level: form.level.trim(),
        industry_id: applied.industry_id || undefined,
        source_url: form.sourceUrl.trim() || undefined,
        responsibilities_summary: form.responsibilities.trim(),
        required_skills_summary: form.requiredSkills.trim(),
        preferred_skills_summary: form.preferredSkills.trim(),
        experience_summary: form.experience.trim(),
        jd_full_text: form.jdFullText.trim() || undefined,
      })
      setForm(EMPTY_FORM)
      setImportOpen(false)
      setNotice(
        response.is_duplicate
          ? `资料库中已存在相同内容的「${response.position.title}」，本次未重复导入。`
          : `「${response.position.title}」已加入资料库。发布时间与招聘状态以来源页面为准，尚未核验前显示「未确认」。`,
      )
      setReload((n) => n + 1)
      if (response.is_duplicate) openDetail(response.position.id)
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : '导入失败，请稍后再试')
    } finally {
      setImporting(false)
    }
  }

  const applyFilters = (next: Filters) => {
    setFilters(next)
    setApplied(next)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-strong">知潮 · 岗位资料库</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
            潮起有信，求职有据。这里只收录来源可核验的真实岗位：发布时间与招聘状态如实标注，
            每条岗位都可回溯至企业官方页面。
          </p>
        </div>
        <AiStatusBadge className="shrink-0" />
      </div>

      {/* 数据真实性说明 */}
      <div className="rounded-xl border border-line bg-brand-50/40 px-5 py-4">
        <ul className="space-y-1.5 text-xs leading-relaxed text-ink-soft">
          <li className="flex items-start gap-2">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
            内置岗位由官方招聘页面人工核对录入，展示事实性摘要与原文链接，不整段复制 JD 原文。
          </li>
          <li className="flex items-start gap-2">
            <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
            来源页面未提供发布时间时显示「来源未提供发布时间」；无法确认是否在招时显示「招聘状态未确认」，绝不默认标记为正在招聘。
          </li>
          <li className="flex items-start gap-2">
            <History className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
            长期未核验的岗位会提示「可能已过期」；发现链接失效可点击「核验来源」即时复核。
          </li>
        </ul>
      </div>

      {/* 检索与筛选 */}
      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <div className="flex-1">
              <label htmlFor="job-q" className="mb-1.5 block text-sm font-medium text-ink-strong">
                关键词
              </label>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
                <input
                  id="job-q"
                  type="text"
                  value={filters.q}
                  placeholder="岗位名称、企业、地点、技能…"
                  maxLength={80}
                  onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') applyFilters(filters)
                  }}
                  className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:w-auto">
              <div>
                <label htmlFor="job-industry" className="mb-1.5 block text-sm font-medium text-ink-strong">
                  行业
                </label>
                <select
                  id="job-industry"
                  value={filters.industry_id}
                  onChange={(event) => applyFilters({ ...filters, industry_id: event.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                >
                  <option value="">全部行业</option>
                  {industries.map((industry) => (
                    <option key={industry.id} value={industry.id}>
                      {industry.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="job-company" className="mb-1.5 block text-sm font-medium text-ink-strong">
                  企业
                </label>
                <input
                  id="job-company"
                  type="text"
                  value={filters.company}
                  placeholder="按企业过滤"
                  maxLength={60}
                  onChange={(event) => setFilters((prev) => ({ ...prev, company: event.target.value }))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') applyFilters(filters)
                  }}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                />
              </div>
              <div>
                <label htmlFor="job-location" className="mb-1.5 block text-sm font-medium text-ink-strong">
                  地点
                </label>
                <input
                  id="job-location"
                  type="text"
                  value={filters.location}
                  placeholder="如：北京"
                  maxLength={60}
                  onChange={(event) => setFilters((prev) => ({ ...prev, location: event.target.value }))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') applyFilters(filters)
                  }}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                />
              </div>
              <div>
                <label htmlFor="job-stage" className="mb-1.5 block text-sm font-medium text-ink-strong">
                  经验阶段
                </label>
                <select
                  id="job-stage"
                  value={filters.stage}
                  onChange={(event) => applyFilters({ ...filters, stage: event.target.value })}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                >
                  <option value="">全部</option>
                  <option value="campus">校招 / 实习</option>
                  <option value="experienced">社招</option>
                </select>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={() => applyFilters(filters)}>
              <Search className="h-4 w-4" aria-hidden="true" />
              检索
            </Button>
            <Button
              size="sm"
              variant={favoritesOnly ? 'primary' : 'secondary'}
              onClick={() => setFavoritesOnly((prev) => !prev)}
            >
              <Star className="h-4 w-4" aria-hidden="true" />
              我的收藏
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setImportOpen((prev) => !prev)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              导入岗位
            </Button>
            {applied !== EMPTY_FILTERS && Object.values(applied).some(Boolean) ? (
              <button
                type="button"
                onClick={() => {
                  setFilters(EMPTY_FILTERS)
                  setApplied(EMPTY_FILTERS)
                  setFavoritesOnly(false)
                }}
                className="text-xs font-medium text-brand-600 underline-offset-2 hover:underline"
              >
                清空筛选
              </button>
            ) : null}
            <span className="ml-auto text-xs text-ink-soft">
              {loading ? '检索中…' : `共 ${listState.total} 条岗位资料`}
            </span>
          </div>
        </CardBody>
      </Card>

      {/* 导入表单 */}
      {importOpen ? (
        <Card>
          <CardHeader
            title="导入真实岗位"
            description="须提供可验证的来源链接（仅接受公网 http/https 地址），或选择手动录入；资料库按内容识别重复岗位，不会重复收录。"
            action={
              <button
                type="button"
                onClick={() => setImportOpen(false)}
                aria-label="收起导入表单"
                className="rounded-lg p-1.5 text-ink-soft transition-colors hover:bg-mist hover:text-ink"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            }
          />
          <CardBody className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="来源企业"
                required
                value={form.company}
                onChange={(value) => setForm((prev) => ({ ...prev, company: value }))}
                placeholder="如：美团"
                maxLength={80}
              />
              <TextField
                label="岗位名称"
                required
                value={form.title}
                onChange={(value) => setForm((prev) => ({ ...prev, title: value }))}
                placeholder="如：AI 后端开发工程师"
                maxLength={120}
              />
              <TextField
                label="工作地点"
                value={form.location}
                onChange={(value) => setForm((prev) => ({ ...prev, location: value }))}
                placeholder="如：北京"
                maxLength={200}
              />
              <TextField
                label="岗位级别 / 招聘类型"
                value={form.level}
                onChange={(value) => setForm((prev) => ({ ...prev, level: value }))}
                placeholder="如：校园招聘 / 社招"
                maxLength={40}
              />
            </div>
            <TextField
              label="来源链接"
              hint="岗位原始页面地址；留空则按手动录入保存（无链接岗位无法在线核验）"
              value={form.sourceUrl}
              onChange={(value) => setForm((prev) => ({ ...prev, sourceUrl: value }))}
              placeholder="https://…"
              maxLength={500}
            />
            <TextAreaField
              label="工作职责摘要"
              value={form.responsibilities}
              onChange={(value) => setForm((prev) => ({ ...prev, responsibilities: value }))}
              placeholder="以事实性摘要转述来源页面的职责要求，不要整段复制原文"
              maxLength={2000}
              rows={3}
            />
            <TextAreaField
              label="必需技能摘要"
              value={form.requiredSkills}
              onChange={(value) => setForm((prev) => ({ ...prev, requiredSkills: value }))}
              placeholder="岗位明确要求的技能，逐条列出"
              maxLength={2000}
              rows={3}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextAreaField
                label="加分技能摘要"
                value={form.preferredSkills}
                onChange={(value) => setForm((prev) => ({ ...prev, preferredSkills: value }))}
                placeholder="优先条件（选填）"
                maxLength={2000}
                rows={2}
              />
              <TextAreaField
                label="经验要求摘要"
                value={form.experience}
                onChange={(value) => setForm((prev) => ({ ...prev, experience: value }))}
                placeholder="如：本科及以上，3 年以上相关经验（选填）"
                maxLength={300}
                rows={2}
              />
            </div>
            <TextAreaField
              label="JD 原文（选填）"
              hint="仅用于知岗解析，不在目录中公开展示"
              value={form.jdFullText}
              onChange={(value) => setForm((prev) => ({ ...prev, jdFullText: value }))}
              placeholder="粘贴完整职位描述原文…"
              maxLength={20000}
              rows={4}
            />
            {importError ? (
              <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {importError}
              </p>
            ) : null}
            <div className="flex justify-end">
              <Button onClick={() => void submitImport()} disabled={importing}>
                {importing ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                {importing ? '导入中…' : '确认导入'}
              </Button>
            </div>
          </CardBody>
        </Card>
      ) : null}

      {notice ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50/70 px-4 py-3 text-sm leading-relaxed text-emerald-800">
          {notice}
        </p>
      ) : null}
      {actionError && !detailLoading ? (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </p>
      ) : null}

      {/* 岗位列表 */}
      {loading ? (
        <Card>
          <div className="flex items-center justify-center gap-3 py-16 text-sm text-ink-soft">
            <Loader2 className="h-5 w-5 animate-spin text-brand-600" aria-hidden="true" />
            正在检索岗位目录…
          </div>
        </Card>
      ) : listError ? (
        <Card>
          <EmptyState icon={AlertTriangle} title="加载失败" description={listError} />
        </Card>
      ) : listState.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={Waves}
            title={favoritesOnly ? '收藏夹还是空的' : '暂无符合条件的岗位'}
            description={
              favoritesOnly
                ? '在岗位列表点击收藏，正在关注的岗位会汇聚在这里。'
                : '资料库只收录来源可核验的真实岗位，没有数据时如实显示空状态。可以调整筛选条件，或通过「导入岗位」补充来源。'
            }
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line/70">
            {listState.items.map((position) => (
              <li key={position.id}>
                <button
                  type="button"
                  onClick={() => openDetail(position.id)}
                  className={`w-full px-5 py-4 text-left transition-colors hover:bg-brand-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-600/40 ${
                    selectedId === position.id ? 'bg-brand-50/60' : ''
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
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
                    {position.industry_name ? (
                      <Badge tone="brand">{position.industry_name}</Badge>
                    ) : null}
                    {position.level ? <Badge tone="neutral">{position.level}</Badge> : null}
                    <Badge tone="preview">招聘状态未确认</Badge>
                    {position.stale_hint ? <Badge tone="preview">可能已过期</Badge> : null}
                  </div>
                  {position.responsibilities_summary ? (
                    <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-ink-soft">
                      {position.responsibilities_summary}
                    </p>
                  ) : null}
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-soft/80">
                    <span>{SOURCE_TYPE_LABEL[position.source_type]}</span>
                    <span>发布：来源未提供</span>
                    {position.source_updated_at ? (
                      <span>来源更新：{formatDate(position.source_updated_at)}</span>
                    ) : null}
                    <span>核验：{position.last_verified_at ? formatDate(position.last_verified_at) : '未核验'}</span>
                    <span>{LINK_STATUS_LABEL[position.link_status]}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* 岗位详情与联动 */}
      {detailLoading ? (
        <Card>
          <div className="flex items-center justify-center gap-3 py-12 text-sm text-ink-soft">
            <Loader2 className="h-5 w-5 animate-spin text-brand-600" aria-hidden="true" />
            正在加载岗位详情…
          </div>
        </Card>
      ) : detail ? (
        <Card>
          <CardHeader
            title={`${detail.title} · ${detail.company}`}
            description="以下摘要来自来源页面的事实性转述；完整职位描述请查看企业原始岗位。"
            action={
              <button
                type="button"
                onClick={() => {
                  setSelectedId(null)
                  setDetail(null)
                  setMatchResult(null)
                  setNotice(null)
                  setActionError(null)
                }}
                aria-label="收起岗位详情"
                className="rounded-lg p-1.5 text-ink-soft transition-colors hover:bg-mist hover:text-ink"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            }
          />
          <CardBody className="space-y-6">
            <div className="grid gap-4 text-sm sm:grid-cols-2">
              <div className="space-y-2">
                <InfoRow label="所属行业" value={detail.industry_name} />
                <InfoRow label="职业分类" value={detail.occupation_name} />
                <InfoRow label="工作地点" value={detail.location} />
                <InfoRow label="岗位级别" value={detail.level} />
              </div>
              <div className="space-y-2">
                <InfoRow label="发布时间" value={detail.published_at ? formatDate(detail.published_at) : detail.published_note} />
                <InfoRow
                  label="来源更新"
                  value={detail.source_updated_at ? formatDate(detail.source_updated_at) : '来源未提供更新时间'}
                />
                <InfoRow
                  label="招聘状态"
                  value={detail.hiring_status === 'open' ? '招聘中（来源标注）' : detail.hiring_status === 'closed' ? '已关闭（来源标注）' : '招聘状态未确认'}
                />
                <InfoRow
                  label="最后核验"
                  value={`${detail.last_verified_at ? formatDateTime(detail.last_verified_at) : '未核验'} · ${LINK_STATUS_LABEL[detail.link_status]}`}
                />
              </div>
            </div>

            <div className="space-y-3">
              <SummaryBlock title="工作职责摘要" text={detail.responsibilities_summary} />
              <SummaryBlock title="必需技能摘要" text={detail.required_skills_summary} />
              <SummaryBlock title="加分技能摘要" text={detail.preferred_skills_summary} />
              <SummaryBlock title="经验要求摘要" text={detail.experience_summary} />
            </div>

            {/* 来源与核验 */}
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-mist/50 px-4 py-3">
              {detail.source_url ? (
                <a
                  href={detail.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 underline-offset-2 hover:underline"
                >
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  查看企业原始岗位
                </a>
              ) : (
                <span className="text-sm text-ink-soft">手动录入岗位，无来源链接</span>
              )}
              <span className="text-xs text-ink-soft">来源类型：{SOURCE_TYPE_LABEL[detail.source_type]}</span>
              {detail.verified_note ? (
                <span className="text-xs text-ink-soft">{detail.verified_note}</span>
              ) : null}
              {detail.source_url ? (
                <Button
                  size="sm"
                  variant="secondary"
                  className="ml-auto"
                  disabled={busy === `verify:${detail.id}`}
                  onClick={() => void verifySource(detail)}
                >
                  {busy === `verify:${detail.id}` ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                  )}
                  核验来源
                </Button>
              ) : null}
            </div>

            {/* 变更历史 */}
            {detail.changes.length > 0 ? (
              <div>
                <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-strong">
                  <History className="h-4 w-4 text-brand-600" aria-hidden="true" />
                  变更记录
                </h3>
                <ol className="space-y-1.5 border-l border-line pl-4">
                  {detail.changes.map((change) => (
                    <li key={change.id} className="text-xs leading-relaxed text-ink-soft">
                      <span className="font-medium text-ink">{formatDateTime(change.created_at)}</span>
                      <span className="mx-1.5 rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                        {change.change_type}
                      </span>
                      {change.note}
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}

            {/* 模块联动 */}
            <div>
              <h3 className="mb-3 text-sm font-semibold text-ink-strong">送入既有流程</h3>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy?.startsWith('analyze:') ?? false}
                  onClick={() => void analyzePosition(detail)}
                >
                  {busy === `analyze:${detail.id}` ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Sparkles className="h-4 w-4" aria-hidden="true" />
                  )}
                  送知岗解析
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy?.startsWith('interview:') ?? false}
                  onClick={() => void createInterviewTask(detail)}
                >
                  {busy === `interview:${detail.id}` ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <MessageSquareText className="h-4 w-4" aria-hidden="true" />
                  )}
                  生成问澜题集
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy?.startsWith('match:') ?? false}
                  onClick={() => {
                    if (resumes.length === 0) void loadResumes()
                    else void matchWithResume(detail)
                  }}
                >
                  {busy === `match:${detail.id}` ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Puzzle className="h-4 w-4" aria-hidden="true" />
                  )}
                  加入合契匹配
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy?.startsWith('plan:') ?? false}
                  onClick={() => void createCareerPlan(detail)}
                >
                  {busy === `plan:${detail.id}` ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Compass className="h-4 w-4" aria-hidden="true" />
                  )}
                  加入知途规划
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy === `fav:${detail.id}`}
                  onClick={() => void toggleFavorite(detail)}
                >
                  <Star
                    className={`h-4 w-4 ${detail.is_favorited ? 'fill-amber-400 text-amber-500' : ''}`}
                    aria-hidden="true"
                  />
                  {detail.is_favorited ? '已收藏' : '收藏岗位'}
                </Button>
              </div>
              {resumes.length > 0 ? (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-line bg-brand-50/40 px-3 py-2">
                  <label htmlFor="match-resume" className="text-xs font-medium text-ink-strong">
                    选择简历
                  </label>
                  <select
                    id="match-resume"
                    value={resumeId}
                    onChange={(event) => setResumeId(event.target.value)}
                    className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                  >
                    {resumes.map((resume) => (
                      <option key={resume.id} value={resume.id}>
                        {resume.title}
                      </option>
                    ))}
                  </select>
                  <Button size="sm" onClick={() => void matchWithResume(detail)} disabled={busy?.startsWith('match:') ?? false}>
                    <Link2 className="h-4 w-4" aria-hidden="true" />
                    开始匹配
                  </Button>
                </div>
              ) : null}
            </div>

            {/* 合契匹配结果 */}
            {matchResult ? (
              <div className="space-y-4 rounded-xl border border-line bg-surface p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-ink-strong">
                    合契匹配 · {matchResult.resume_title}
                  </h3>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-brand-700">{matchResult.match_score}</p>
                    <p className="text-[11px] text-ink-soft">内部文本匹配指标</p>
                  </div>
                </div>
                <p className="rounded-lg bg-brand-50/60 px-3 py-2 text-xs leading-relaxed text-ink-soft">
                  {matchResult.score_note}
                </p>
                {matchResult.matched_skills.length > 0 ? (
                  <ul className="space-y-2">
                    {matchResult.matched_skills.map((skill) => (
                      <li key={skill.skill} className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3 text-xs leading-relaxed">
                        <p className="font-medium text-emerald-800">{skill.skill}</p>
                        {skill.evidence ? <p className="mt-1 text-ink-soft">简历依据：{skill.evidence}</p> : null}
                        {skill.job_evidence ? <p className="mt-0.5 text-ink-soft">岗位依据：{skill.job_evidence}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-ink-soft">简历中暂未发现与岗位要求对应的技能。</p>
                )}
                {matchResult.missing_skills.length > 0 ? (
                  <div>
                    <p className="mb-1.5 text-xs font-semibold text-ink-strong">岗位要求但简历未体现</p>
                    <div className="flex flex-wrap gap-2">
                      {matchResult.missing_skills.map((item) => (
                        <span
                          key={item.skill}
                          title={item.suggestion}
                          className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-medium text-red-700 ring-1 ring-inset ring-red-600/20"
                        >
                          {item.skill}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : null}
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="w-20 shrink-0 text-xs text-ink-soft">{label}</span>
      <span className="text-sm text-ink">{value || '未明确说明'}</span>
    </div>
  )
}

function SummaryBlock({ title, text }: { title: string; text: string }) {
  if (!text) return null
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold tracking-wide text-ink-soft">{title}</h4>
      <p className="whitespace-pre-wrap rounded-lg bg-mist/50 px-3.5 py-2.5 text-sm leading-relaxed text-ink">
        {text}
      </p>
    </div>
  )
}
