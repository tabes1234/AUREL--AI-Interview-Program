import { ArrowLeft, Loader2, Pin, RefreshCw, ScrollText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { PageBackground } from '../components/PageBackground'
import { PointerGlow } from '../components/PointerGlow'
import { SiteHeader } from '../components/layout/SiteHeader'
import { XiaouCompanion } from '../components/XiaouCompanion'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { renderInline } from '../lib/inlineCode'
import type { TechArchiveDetail } from '../types'

/** 章节标题「01｜项目概览」→ 序号着色 + 标题正文 */
function SectionHeading({ heading }: { heading: string }) {
  const separatorIndex = heading.indexOf('｜')
  if (separatorIndex > 0) {
    return (
      <h2 className="text-xl font-bold tracking-tight text-ink-strong sm:text-2xl">
        <span className="mr-2 font-semibold text-amber-600">{heading.slice(0, separatorIndex)}</span>
        {heading.slice(separatorIndex + 1)}
      </h2>
    )
  }
  return <h2 className="text-xl font-bold tracking-tight text-ink-strong sm:text-2xl">{heading}</h2>
}

/** 置顶技术档案阅读页：完整 12 章节正文，数据来自 /api/v1/announcements/project-tech-archive。 */
export default function TechArchivePage() {
  const [state, setState] = useState<{
    phase: 'loading' | 'error' | 'ready'
    detail: TechArchiveDetail | null
    message: string | null
  }>({ phase: 'loading', detail: null, message: null })

  async function reload() {
    setState({ phase: 'loading', detail: null, message: null })
    try {
      const data = await api.getTechArchive()
      setState({ phase: 'ready', detail: data, message: null })
    } catch (error) {
      setState({
        phase: 'error',
        detail: null,
        message: error instanceof ApiError ? error.message : '加载技术档案失败',
      })
    }
  }

  useEffect(() => {
    document.title = '项目技术档案 | 观澜 AUREL'
    let cancelled = false
    api
      .getTechArchive()
      .then((data) => {
        if (!cancelled) setState({ phase: 'ready', detail: data, message: null })
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            phase: 'error',
            detail: null,
            message: error instanceof ApiError ? error.message : '加载技术档案失败',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const detail = state.detail

  return (
    <div className="relative min-h-screen bg-surface">
      {/* 午后薰衣草场景背景（固定底层，pointer-events: none）+ 柔和光晕 */}
      <PageBackground scene="notices" />
      <PointerGlow intensity="faint" />
      <SiteHeader variant="solid" />

      {/* pb-28：为右下角小鸥悬浮入口预留空间 */}
      <main className="page-enter relative mx-auto w-full max-w-4xl px-3 pb-28 pt-10 sm:px-5 sm:pt-14 lg:px-8">
        <div className="glass-surface glass-notices rounded-3xl px-6 py-10 sm:px-10 sm:py-12">
          {state.phase === 'loading' ? (
            <div className="flex flex-col items-center gap-3 py-14 text-ink-soft">
              <Loader2 className="h-8 w-8 animate-spin text-brand-600" aria-hidden="true" />
              <p className="text-sm">正在打开技术档案…</p>
            </div>
          ) : state.phase === 'error' || !detail ? (
            <EmptyState
              icon={ScrollText}
              title="无法打开技术档案"
              description={state.message ?? '请稍后重试。'}
              action={
                <div className="flex flex-wrap items-center justify-center gap-3">
                  <Button variant="secondary" size="sm" onClick={() => void reload()}>
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    重试
                  </Button>
                  <Link
                    to="/announcements"
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                    返回澜讯
                  </Link>
                </div>
              }
            />
          ) : (
            <>
              {/* 档案头部：返回、标识、标题与副题 */}
              <div>
                <Link
                  to="/announcements"
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 transition hover:text-brand-700"
                >
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                  返回澜讯
                </Link>

                <div className="mt-5 flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-300/70 bg-amber-50/90 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
                    <Pin className="h-3 w-3" aria-hidden="true" />
                    置顶公告
                  </span>
                  <Badge tone="brand">{detail.announcement.type}</Badge>
                  {detail.announcement.importance ? (
                    <span className="rounded-full border border-amber-200/80 bg-white/70 px-2.5 py-0.5 text-xs font-medium text-amber-600">
                      {detail.announcement.importance}
                    </span>
                  ) : null}
                  {detail.announcement.tags
                    ?.filter((tag) => tag !== '置顶公告')
                    .map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-mist px-2.5 py-0.5 text-xs text-ink-soft"
                      >
                        {tag}
                      </span>
                    ))}
                </div>

                <h1 className="mt-4 text-3xl font-bold tracking-tight text-ink-strong sm:text-4xl">
                  {detail.announcement.title}
                </h1>
                <p className="mt-3 text-base font-medium text-brand-700">
                  见微知远，向新而行。
                </p>
                <time
                  className="mt-2 block text-xs text-ink-soft"
                  dateTime={
                    detail.announcement.updated_at ?? detail.announcement.date ?? undefined
                  }
                >
                  更新于{' '}
                  {detail.announcement.updated_at ?? detail.announcement.date ?? '日期待记'} ·
                  本档案随项目迭代持续更新
                </time>
              </div>

              {/* 12 章节正文：一个整体阅读区，用留白与细分隔线建立层次 */}
              <div className="mt-10 space-y-12 border-t border-line/70 pt-10">
                {detail.sections.map((section) => (
                  <section key={section.id} id={section.id} aria-label={section.heading}>
                    <SectionHeading heading={section.heading} />
                    {section.paragraphs.length > 0 ? (
                      <div className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink">
                        {section.paragraphs.map((paragraph, index) => (
                          <p key={index}>{renderInline(paragraph)}</p>
                        ))}
                      </div>
                    ) : null}

                    {section.bullets.length > 0 ? (
                      <ul className="mt-4 space-y-2.5 text-[15px] leading-relaxed text-ink">
                        {section.bullets.map((bullet, index) => (
                          <li key={index} className="flex gap-2.5">
                            <span
                              className="mt-[10px] h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400"
                              aria-hidden="true"
                            />
                            <span>{renderInline(bullet)}</span>
                          </li>
                        ))}
                      </ul>
                    ) : null}

                    {section.table_head && section.table_rows ? (
                      <div className="mt-5 overflow-x-auto rounded-xl border border-line/80">
                        <table className="w-full min-w-[560px] border-collapse text-left text-sm">
                          <thead>
                            <tr className="bg-mist/70">
                              {section.table_head.map((head) => (
                                <th
                                  key={head}
                                  scope="col"
                                  className="whitespace-nowrap px-4 py-2.5 font-semibold text-ink-strong"
                                >
                                  {head}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-line/70">
                            {section.table_rows.map((row, rowIndex) => (
                              <tr key={rowIndex} className="align-top">
                                {row.map((cell, cellIndex) => (
                                  <td
                                    key={cellIndex}
                                    className={
                                      cellIndex === 0
                                        ? 'whitespace-nowrap px-4 py-2.5 font-medium text-ink-strong'
                                        : 'px-4 py-2.5 leading-relaxed text-ink'
                                    }
                                  >
                                    {renderInline(cell)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </section>
                ))}
              </div>

              <footer className="mt-12 border-t border-line/70 pt-6 text-sm text-ink-soft">
                © 2026 观澜 AUREL · 见微知远，向新而行。
              </footer>
            </>
          )}
        </div>
      </main>

      {/* 小鸥悬浮入口：点击直达知途 AI 对话 */}
      <XiaouCompanion />
    </div>
  )
}
