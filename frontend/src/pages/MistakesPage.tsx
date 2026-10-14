import { BrainCircuit, ChevronDown, ChevronUp, Loader2, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import { PageHeading, SectionHead, StatStrip } from '../components/editorial/Editorial'
import { PageTransition } from '../components/motion/PageTransition'
import { Badge } from '../components/ui/Badge'
import { Button, ButtonLink } from '../components/ui/Button'
import { formatDateTime } from '../lib/format'
import type { MistakeCardOut } from '../types'

const GRADE_OPTIONS: { grade: number; label: string; description: string }[] = [
  { grade: 0, label: '想不起来了', description: '完全忘了' },
  { grade: 3, label: '勉强想起', description: '磕磕绊绊' },
  { grade: 4, label: '想起来了', description: '略费了一番功夫' },
  { grade: 5, label: '轻松想起', description: '脱口而出' },
]

/** 回澜：Editorial 编辑式布局 —— StatStrip 统计带 + 细线错题行，无卡片。 */
export default function MistakesPage() {
  const [cards, setCards] = useState<MistakeCardOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reviewingId, setReviewingId] = useState<number | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [flash, setFlash] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .listMistakes()
      .then((data) => {
        if (active) setCards(data.cards)
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

  async function review(cardId: number, grade: number) {
    setReviewingId(cardId)
    setFlash(null)
    try {
      const updated = await api.reviewMistake(cardId, grade)
      setCards((prev) => prev.map((card) => (card.id === cardId ? updated : card)))
      setFlash(
        grade >= 3
          ? `记下了。下一回在 ${updated.interval_days} 天后再遇见它。`
          : '没关系，水滴石穿。明天再来见它一次。',
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '复习打卡失败')
    } finally {
      setReviewingId(null)
    }
  }

  async function remove(cardId: number) {
    try {
      await api.deleteMistake(cardId)
      setCards((prev) => prev.filter((card) => card.id !== cardId))
      setFlash(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '删除失败')
    }
  }

  const dueCards = cards.filter((card) => card.is_due)
  const masteredCount = cards.filter((card) => card.repetitions >= 3).length

  return (
    <PageTransition>
      <PageHeading
        kicker="洞察"
        title="回澜"
        subtitle="逝者如斯，而未尝往也。答错的题不必回避——按记忆节律隔日重温，直到它成为你的浪潮。"
      />

      {flash ? (
        <p className="mt-6 rounded-lg border border-ripple/60 bg-brand-50/60 px-4 py-2.5 text-sm text-brand-700">
          {flash}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-6 text-sm text-red-600">
          {error}
        </p>
      ) : null}

      {/* 统计带：大数字直接融入页面，无卡片 */}
      {!loading && cards.length > 0 ? (
        <StatStrip
          className="mt-10"
          items={[
            { label: '收进的错题', value: cards.length },
            {
              label: '今日待复习',
              value: dueCards.length,
              hint: dueCards.length > 0 ? '现在正是重温的时辰' : '尚无到期之题',
            },
            { label: '已牢固掌握', value: masteredCount, hint: '复习三次以上' },
            {
              label: '掌握率',
              value: `${Math.round((masteredCount * 100) / cards.length)}%`,
              hint: '已牢固掌握的占比',
            },
          ]}
        />
      ) : null}

      {/* 错题簿：细线行列表，无卡片 */}
      <section className="mt-12" aria-label="错题簿">
        <SectionHead
          title="错题簿"
          note={
            loading
              ? undefined
              : cards.length > 0
                ? `共 ${cards.length} 题 · ${dueCards.length} 题今日到期`
                : undefined
          }
        />
        <div className="mt-2">
          {loading ? (
            <p className="flex items-center gap-2 py-8 text-sm text-ink-soft">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              正在翻开错题本…
            </p>
          ) : cards.length === 0 ? (
            <div className="py-8">
              <p className="max-w-xl text-sm leading-relaxed text-ink-soft">
                错题本还是空白的。在回响的报告里，把值得再想一次的题目收进来，这里会为你安排复习节律。
              </p>
              <ButtonLink to="/reports" variant="secondary" size="sm" className="mt-4">
                去回响找题
              </ButtonLink>
            </div>
          ) : (
            <div className="divide-y divide-line/70">
              {cards.map((card) => {
                const due = card.is_due
                const expanded = expandedId === card.id
                return (
                  <article
                    key={card.id}
                    className="group -mx-3 px-3 py-5 transition-colors duration-200 hover:bg-white/70"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="text-[15px] font-semibold leading-relaxed text-ink-strong transition-colors group-hover:text-brand-700">
                          {card.question_content.length > 48
                            ? `${card.question_content.slice(0, 48)}…`
                            : card.question_content}
                        </h3>
                        <p className="mt-1 text-xs text-ink-soft">
                          {card.position}
                          {card.dimension ? ` · ${card.dimension}` : ''}
                          {card.category ? ` · ${card.category}` : ''}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {due ? (
                          <Badge tone="brand">待复习</Badge>
                        ) : (
                          <Badge tone="neutral">{formatDateTime(card.due_at)} 复习</Badge>
                        )}
                        <Badge tone="preview">复习 {card.review_count} 次</Badge>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => setExpandedId(expanded ? null : card.id)}
                      className="mt-3 flex items-center gap-1.5 text-xs text-ink-soft transition-colors hover:text-brand-600"
                      aria-expanded={expanded}
                    >
                      {expanded ? (
                        <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      {expanded ? '收起当时的回答与提示' : '展开当时的回答与提示'}
                    </button>
                    {expanded ? (
                      <div className="mt-3 space-y-3 border-l-2 border-ripple/50 pl-4">
                        <div>
                          <p className="text-xs font-semibold text-ink-soft">我的回答</p>
                          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                            {card.my_answer || '（当时未留下回答）'}
                          </p>
                        </div>
                        {card.goal ? (
                          <div>
                            <p className="text-xs font-semibold text-ink-soft">考察意图</p>
                            <p className="mt-1 text-sm leading-relaxed text-ink">{card.goal}</p>
                          </div>
                        ) : null}
                        {card.rubric && card.rubric.length > 0 ? (
                          <div>
                            <p className="text-xs font-semibold text-ink-soft">参考要点</p>
                            <ul className="mt-1 space-y-1">
                              {card.rubric.map((item, index) => (
                                <li
                                  key={index}
                                  className="flex gap-2 text-sm leading-relaxed text-ink"
                                >
                                  <span
                                    aria-hidden="true"
                                    className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand-600"
                                  />
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        <p className="text-xs text-ink-soft">
                          记忆参数：间隔 {card.interval_days} 天 · 熟练度系数{' '}
                          {card.ease_factor.toFixed(2)} · 上次复习{' '}
                          {card.last_reviewed_at ? formatDateTime(card.last_reviewed_at) : '尚未复习'}
                        </p>
                      </div>
                    ) : null}

                    {/* 复习区：仅到期卡展示回忆自评 */}
                    <div className="mt-4 border-t border-line pt-4">
                      {due ? (
                        <div>
                          <p className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                            <BrainCircuit className="h-4 w-4 text-brand-600" aria-hidden="true" />
                            先自己回想一遍，再如实告诉它想起来了没有：
                          </p>
                          <div className="mt-2.5 flex flex-wrap gap-2">
                            {GRADE_OPTIONS.map((option) => (
                              <Button
                                key={option.grade}
                                variant={option.grade >= 4 ? 'primary' : 'secondary'}
                                size="sm"
                                disabled={reviewingId === card.id}
                                onClick={() => void review(card.id, option.grade)}
                                title={option.description}
                              >
                                {reviewingId === card.id ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                                ) : null}
                                {option.label}
                              </Button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs text-ink-soft">
                          还未到期——让记忆沉一沉，到期时它会浮现到这里。
                        </p>
                      )}
                      <div className="mt-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void remove(card.id)}
                          className="text-ink-soft/70"
                          aria-label="从错题本移除"
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                          移除
                        </Button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </div>
      </section>
    </PageTransition>
  )
}
