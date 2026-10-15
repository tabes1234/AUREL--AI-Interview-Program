import {
  AlertTriangle,
  ArrowRight,
  BookOpenCheck,
  ChevronRight,
  ExternalLink,
  Loader2,
  PenLine,
  ShieldCheck,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { ResumeGallery, ResumeTemplateGuide } from '../types'

/** 行业分组：按 industry 字段前缀归组，未匹配的兜底到最后 */
const GROUPS: { key: string; label: string; match: (industry: string) => boolean }[] = [
  { key: 'general', label: '通用 · 全行业', match: (i) => i.startsWith('通用') },
  { key: 'finance', label: '金融 · 银行证券', match: (i) => i.startsWith('金融') },
  { key: 'fmcg', label: '快消 · 零售', match: (i) => i.startsWith('快消') },
  { key: 'manufacturing', label: '制造 · 新能源', match: (i) => i.startsWith('制造') },
  { key: 'medical', label: '医药 · 医疗', match: (i) => i.startsWith('医药') },
  { key: 'education', label: '教育', match: (i) => i.startsWith('教育') },
  { key: 'media', label: '传媒 · 运营', match: (i) => i.startsWith('传媒') },
  { key: 'legal', label: '法律 · 咨询', match: (i) => i.startsWith('法律') },
]

function groupOf(industry: string): string {
  const hit = GROUPS.find((g) => g.match(industry))
  return hit ? hit.key : 'other'
}

/** 模板条目：编辑式单列排布，结构链用胶囊 + 箭头，要点列表 + 官方来源 */
function TemplateEntry({ template }: { template: ResumeTemplateGuide }) {
  return (
    <article className="border-t border-line py-6 first:border-t-0 first:pt-0">
      <div className="flex flex-col gap-4 md:flex-row md:gap-8">
        {/* 左列：名称与结构链 */}
        <div className="md:w-[42%] md:shrink-0">
          <h3 className="text-lg font-semibold leading-snug text-ink-strong">{template.name}</h3>
          <p className="mt-1.5 text-xs text-ink-soft">
            <span className="text-brand-700">{template.industry}</span>
            <span className="mx-1.5 text-line">·</span>
            适用于{template.audience}
          </p>
          <div className="mt-3.5 flex flex-wrap items-center gap-y-2">
            {template.structure.map((step, idx) => (
              <span key={step} className="flex items-center gap-2">
                {idx > 0 && (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden="true" />
                )}
                <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs text-brand-800 ring-1 ring-brand-100">
                  {step}
                </span>
              </span>
            ))}
          </div>
        </div>

        {/* 右列：写作要点 + 来源 */}
        <div className="min-w-0 flex-1">
          <ul className="space-y-2">
            {template.tips.map((tip) => (
              <li key={tip} className="flex items-start gap-2 text-sm leading-relaxed text-ink-soft">
                <span
                  aria-hidden="true"
                  className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-brand-400"
                />
                {tip}
              </li>
            ))}
          </ul>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-soft/90">
            <a
              href={template.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-brand-700 underline decoration-brand-200 underline-offset-4 transition-colors hover:text-brand-800 hover:decoration-brand-400"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              {template.source_title}
            </a>
            <span>查阅于 {template.accessed_at}</span>
            <Link
              to="/resume"
              className="ml-auto inline-flex items-center gap-1 font-medium text-brand-700 transition-colors hover:text-brand-800"
            >
              <PenLine className="h-3.5 w-3.5" aria-hidden="true" />
              去履历成章写一份
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </div>
    </article>
  )
}

export default function ResumeGalleryPage() {
  const [gallery, setGallery] = useState<ResumeGallery | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  // 加载态由「结果归属轮次」推导：返回结果所属轮次与当前轮次不一致即视为加载中，
  // 避免 effect 内同步 setState 触发级联渲染（与知潮列表页同一模式）
  const [loadedRound, setLoadedRound] = useState(-1)
  const loading = loadedRound !== reload
  const [activeGroup, setActiveGroup] = useState<string>('all')

  useEffect(() => {
    document.title = '拾贝 · 简历模板指南 — 观澜 AUREL'
    return () => {
      document.title = '观澜 AUREL — AI 驱动的能力探索与成长平台'
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .getResumeGallery()
      .then((data) => {
        if (cancelled) return
        setGallery(data)
        setError(null)
        setLoadedRound(reload)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : '模板指南加载失败，请稍后重试')
        setLoadedRound(reload)
      })
    return () => {
      cancelled = true
    }
  }, [reload])

  const groups = useMemo(() => {
    if (!gallery) return []
    const all = GROUPS.map((g) => ({
      key: g.key,
      label: g.label,
      items: gallery.templates.filter((t) => groupOf(t.industry) === g.key),
    }))
    const other = gallery.templates.filter((t) => groupOf(t.industry) === 'other')
    if (other.length > 0) {
      all.push({ key: 'other', label: '其他行业', items: other })
    }
    return all.filter((g) => g.items.length > 0)
  }, [gallery])

  const visibleGroups = useMemo(
    () => (activeGroup === 'all' ? groups : groups.filter((g) => g.key === activeGroup)),
    [groups, activeGroup],
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-strong">拾贝 · 简历模板指南</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
            海边拾贝，各取所需。这里收录来自高校就业指导中心与国家就业服务平台的官方简历写作规范，
            按行业分门别类，每一条都可回溯至来源原文。
          </p>
        </div>
      </div>

      {/* 数据真实性说明 */}
      <div className="rounded-xl border border-line bg-brand-50/40 px-5 py-4">
        <ul className="space-y-1.5 text-xs leading-relaxed text-ink-soft">
          <li className="flex items-start gap-2">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
            全部 {gallery?.templates.length ?? 16} 条模板规范均核对自官方来源页面（高校就业网
            .edu.cn 与国家大学生就业服务平台等），只收录结构与写法规范，不含任何真实个人简历内容。
          </li>
          <li className="flex items-start gap-2">
            <BookOpenCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
            每条规范附来源链接与查阅日期（最近查阅 {gallery?.verified_on ?? '—'}），点击来源即可核对原文；
            写作要点为来源原文的忠实提炼，非 AI 编造。
          </li>
        </ul>
      </div>

      {/* 行业筛选 */}
      {gallery && groups.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="按行业筛选模板">
          <button
            type="button"
            onClick={() => setActiveGroup('all')}
            aria-pressed={activeGroup === 'all'}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
              activeGroup === 'all'
                ? 'bg-brand-600 text-white'
                : 'bg-white text-ink-soft ring-1 ring-line hover:text-brand-700 hover:ring-brand-200'
            }`}
          >
            全部（{gallery.templates.length}）
          </button>
          {groups.map((g) => (
            <button
              key={g.key}
              type="button"
              onClick={() => setActiveGroup(g.key)}
              aria-pressed={activeGroup === g.key}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                activeGroup === g.key
                  ? 'bg-brand-600 text-white'
                  : 'bg-white text-ink-soft ring-1 ring-line hover:text-brand-700 hover:ring-brand-200'
              }`}
            >
              {g.label}（{g.items.length}）
            </button>
          ))}
        </div>
      )}

      {/* 加载态 */}
      {loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-ink-soft">
          <Loader2 className="h-4 w-4 animate-spin text-brand-500" aria-hidden="true" />
          正在整理滩涂上的贝壳，请稍候…
        </div>
      )}

      {/* 错误态 */}
      {!loading && error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-5 py-4">
          <div className="flex items-start gap-2 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <p>{error}</p>
              <button
                type="button"
                onClick={() => setReload((n) => n + 1)}
                className="mt-2 font-medium text-amber-900 underline underline-offset-4"
              >
                重试
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 分组渲染 */}
      {!loading && !error && gallery && visibleGroups.length === 0 && (
        <p className="py-16 text-center text-sm text-ink-soft">这一类暂无收录，换个分类看看。</p>
      )}
      {!loading &&
        !error &&
        visibleGroups.map((g) => (
          <section key={g.key} aria-labelledby={`rg-${g.key}`} className="mt-2">
            <div className="mb-1 flex items-baseline gap-3">
              <h2
                id={`rg-${g.key}`}
                className="text-[13px] font-semibold tracking-[0.18em] text-brand-800"
              >
                {g.label}
              </h2>
              <span className="h-px flex-1 bg-gradient-to-r from-line to-transparent" aria-hidden="true" />
              <span className="text-xs text-ink-soft/70">{g.items.length} 条规范</span>
            </div>
            <div className="px-0.5">
              {g.items.map((t) => (
                <TemplateEntry key={t.id} template={t} />
              ))}
            </div>
          </section>
        ))}
    </div>
  )
}
