import { ArrowRight, FileText, Loader2, Megaphone, Pin, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { PageBackground } from '../components/PageBackground'
import { SiteHeader } from '../components/layout/SiteHeader'
import { XiaouCompanion } from '../components/XiaouCompanion'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import type { AnnouncementItem } from '../types'

function typeTone(type: string): 'brand' | 'neutral' | 'preview' {
  if (type === '版本更新') return 'brand'
  if (type === '维护修复') return 'preview'
  return 'neutral'
}

/** 置顶「项目介绍」栏目：特殊标记的入口条目，位于全部普通公告之前，点击进入独立阅读页。 */
function PinnedArchiveEntry({ item }: { item: AnnouncementItem }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => navigate('/announcements/tech-archive')}
      className="group mb-6 block w-full rounded-2xl border border-amber-200/80 bg-gradient-to-r from-amber-50/70 via-white/75 to-shallow/40 p-5 text-left shadow-card transition duration-200 hover:-translate-y-0.5 hover:shadow-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500 sm:p-6"
      aria-label={`阅读置顶栏目：${item.title}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-full border border-amber-300/70 bg-amber-50/90 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
          <Pin className="h-3 w-3" aria-hidden="true" />
          置顶
        </span>
        <Badge tone="brand">{item.type}</Badge>
        {item.importance ? (
          <span className="rounded-full border border-amber-200/80 bg-white/70 px-2.5 py-0.5 text-xs font-medium text-amber-600">
            {item.importance}
          </span>
        ) : null}
        <time
          className="ml-auto text-xs text-ink-soft"
          dateTime={item.updated_at ?? item.date ?? undefined}
        >
          更新于 {item.updated_at ?? item.date ?? '日期待记'}
        </time>
      </div>

      <div className="mt-3 flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-brand-700 text-white shadow-card">
          <FileText className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 className="text-lg font-bold leading-snug text-ink-strong">{item.title}</h2>
          <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-ink-soft">{item.summary}</p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end gap-1.5 text-sm font-semibold text-amber-700">
        阅读完整档案
        <ArrowRight
          className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </button>
  )
}

/** 澜讯：平台公告页。数据来自真实接口 /api/v1/announcements，无公告时显示空状态。 */
export default function AnnouncementsPage() {
  const [state, setState] = useState<{
    phase: 'loading' | 'error' | 'ready'
    items: AnnouncementItem[]
    message: string | null
  }>({ phase: 'loading', items: [], message: null })

  async function reload() {
    setState({ phase: 'loading', items: [], message: null })
    try {
      const data = await api.listAnnouncements()
      setState({ phase: 'ready', items: data.items, message: null })
    } catch (error) {
      setState({
        phase: 'error',
        items: [],
        message: error instanceof ApiError ? error.message : '加载公告失败',
      })
    }
  }

  useEffect(() => {
    document.title = '澜讯 | 观澜 AUREL'
    let cancelled = false
    api
      .listAnnouncements()
      .then((data) => {
        if (!cancelled) setState({ phase: 'ready', items: data.items, message: null })
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            phase: 'error',
            items: [],
            message: error instanceof ApiError ? error.message : '加载公告失败',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const pinned = state.phase === 'ready' ? state.items.find((item) => item.pinned) : undefined
  const regularItems = state.phase === 'ready' ? state.items.filter((item) => !item.pinned) : []

  return (
    <div className="relative min-h-screen bg-surface">
      {/* 午后薰衣草场景背景（固定底层，pointer-events: none）+ 柔和光晕 */}
      <PageBackground scene="notices" />
      <SiteHeader variant="solid" />

      {/* pb-28：为右下角小鸥悬浮入口预留空间，避免压住列表末尾内容 */}
      <main className="page-enter relative mx-auto w-full max-w-4xl px-3 pb-28 pt-10 sm:px-5 sm:pt-14 lg:px-8">
        {/* 大面积浅紫白玻璃阅读区：标题、正文与操作全部承载于此，不与花田直接混合 */}
        <div className="glass-surface glass-notices rounded-3xl px-6 py-10 sm:px-10 sm:py-12">
          <section>
            <p className="text-sm font-medium tracking-[0.3em] text-brand-600">LANXUN</p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-ink-strong sm:text-4xl">
              澜讯
            </h1>
            <p className="mt-4 text-base leading-relaxed text-ink-soft">
              澜讯是观澜的水文志：每一段航程、每一次修缮、每一圈涟漪，都记在这里。
              全部内容来自真实的开发记录，无一虚构——水面之上是功能，水面之下是工夫。
            </p>
          </section>

          <div className="mt-10">
            {state.phase === 'loading' ? (
              <div className="flex flex-col items-center gap-3 py-14 text-ink-soft">
                <Loader2 className="h-8 w-8 animate-spin text-brand-600" aria-hidden="true" />
                <p className="text-sm">正在获取公告…</p>
              </div>
            ) : state.phase === 'error' ? (
              <EmptyState
                icon={Megaphone}
                title="无法加载公告"
                description={state.message ?? '请稍后重试。'}
                action={
                  <Button variant="secondary" size="sm" onClick={() => void reload()}>
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    重试
                  </Button>
                }
              />
            ) : state.items.length === 0 ? (
              <EmptyState
                icon={Megaphone}
                title="静水无痕"
                description="暂无新的航讯。潮信有期——平台的每一次更新与修缮，都会先在这里留下一圈涟漪。"
              />
            ) : (
              <>
                {/* 置顶栏目永远在普通公告之前，不参与时间排序与分页 */}
                {pinned ? <PinnedArchiveEntry item={pinned} /> : null}
                <ol className="divide-y divide-line/70">
                  {regularItems.map((item) => (
                    <li key={item.id} className="py-7 first:pt-0 last:pb-0">
                      <article>
                        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                          <h2 className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-lg font-bold text-ink-strong">
                            {item.title}
                            {item.version ? (
                              <span className="rounded-full bg-shallow px-2 py-0.5 text-xs font-semibold text-brand-700">
                                {item.version}
                              </span>
                            ) : null}
                          </h2>
                          <div className="flex shrink-0 flex-col items-end gap-1.5">
                            <Badge tone={typeTone(item.type)}>{item.type}</Badge>
                            <time className="text-xs text-ink-soft" dateTime={item.date ?? undefined}>
                              {item.date ? `发布于 ${item.date}` : '日期待记'}
                            </time>
                          </div>
                        </div>
                        {item.summary ? (
                          <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{item.summary}</p>
                        ) : null}
                        <ul className="mt-3 space-y-1.5 text-sm leading-relaxed text-ink">
                          {item.items.map((line) => (
                            <li key={line}>· {line}</li>
                          ))}
                        </ul>
                      </article>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>

          <footer className="mt-12 border-t border-line/70 pt-6 text-sm text-ink-soft">
            © 2026 观澜 AUREL · 见微知远，向新而行。
          </footer>
        </div>
      </main>

      {/* 小鸥悬浮入口：点击直达知途 AI 对话 */}
      <XiaouCompanion />
    </div>
  )
}
