import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowDown,
  Copy,
  Menu,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Plus,
  RefreshCw,
  SendHorizontal,
  Square,
  Trash2,
  X,
} from 'lucide-react'
import { api, ApiError, streamCareerChat } from '../api/client'
import { GullMascot } from '../components/GullMascot'
import CareerAdvisorPanel from '../components/career/CareerAdvisorPanel'
import { cn } from '../lib/cn'
import type { CareerConversation, CareerMessage } from '../types'

/** 首次进入知途的欢迎语（产品文案，保持原文） */
const WELCOME_TEXT =
  '你好，我是小鸥。我们可以从你目前的学习、经历，或正在困扰你的职业问题开始；你不必一次告诉我所有信息，我们可以慢慢梳理。'

/** 快捷开场：点击即可作为第一条消息发出（也可直接自由输入） */
const QUICK_STARTS = [
  '我还不知道自己适合什么职业。',
  '我已经有目标，但不知道如何准备。',
  '我想探索其他行业。',
  '我想分析自己的能力与短板。',
  '我想分析一份真实岗位描述。',
  '我想制定接下来几个月的成长计划。',
]

const NETWORK_ERROR = '网络请求失败：无法连接后端服务'

function formatTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 本地消息：等待 meta 确认前的乐观消息用负数 id */
type LocalMessage = CareerMessage & { pending?: boolean; failed?: boolean }

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}

const EMPTY_MESSAGES: LocalMessage[] = []

export default function CareerGuidePage() {
  // ---------- 会话列表 ----------
  const [conversations, setConversations] = useState<CareerConversation[]>([])
  const [listError, setListError] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [mobileListOpen, setMobileListOpen] = useState(false)

  // ---------- 当前会话与消息 ----------
  const [activeId, setActiveId] = useState<number | null>(null)
  const [chat, setChat] = useState<{ id: number; messages: LocalMessage[] } | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  // ---------- 发送 / 流式 ----------
  const [draft, setDraft] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [sendError, setSendError] = useState<{ message: string; canRetry: boolean } | null>(null)
  const [retryContent, setRetryContent] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ---------- 标题编辑 ----------
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null)
  const [titleDraft, setTitleDraft] = useState('')

  // ---------- 右栏与滚动 ----------
  const [panelOpen, setPanelOpen] = useState(true)
  const [dataVersion, setDataVersion] = useState(0)
  const [atBottom, setAtBottom] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef('')

  // 稳定的列表刷新（读取 ref，避免回调随 search 变化重建）
  const refreshConversations = useCallback(() => {
    return api
      .listCareerConversations(searchRef.current)
      .then((items) => {
        setConversations(items)
        setListError(false)
      })
      .catch(() => setListError(true))
  }, [])

  // 首次进入 / 搜索词变化：拉取会话列表（搜索 300ms 防抖）
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  useEffect(() => {
    let alive = true
    searchRef.current = search
    api
      .listCareerConversations(search)
      .then((items) => {
        if (!alive) return
        setConversations(items)
        setListError(false)
        // 已有旅程时自动回到最近一段对话（只在尚未选中时）
        setActiveId((current) => current ?? items[0]?.id ?? null)
      })
      .catch(() => {
        if (alive) setListError(true)
      })
    return () => {
      alive = false
    }
  }, [search])

  // 切换会话：拉取完整消息流
  useEffect(() => {
    if (activeId == null) return
    let alive = true
    api
      .getCareerConversation(activeId)
      .then((detail) => {
        if (alive) {
          setChat({ id: detail.id, messages: detail.messages })
          setAtBottom(true)
          setDetailError(null)
        }
      })
      .catch((err) => {
        if (alive) setDetailError(errorMessage(err, '这段对话暂时打不开了，请稍后再试'))
      })
    return () => {
      alive = false
    }
  }, [activeId])

  const messages = useMemo(
    () => (chat && chat.id === activeId ? chat.messages : EMPTY_MESSAGES),
    [chat, activeId],
  )

  // 新内容到达时自动贴底（用户没有向上翻时）
  useEffect(() => {
    if (!atBottom) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, streamText, streaming, atBottom])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80)
  }

  const scrollToBottom = () => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    setAtBottom(true)
  }

  // ---------- 流式核心：发送 / 重试 / 重新生成 共用 ----------
  const runStream = useCallback(
    (conversationId: number, mode: 'stream' | 'regenerate', content: string | null) => {
      const controller = new AbortController()
      abortRef.current = controller
      setStreaming(true)
      setStreamText('')
      setSendError(null)
      setRetryContent(null)

      if (mode === 'stream' && content) {
        // 乐观插入用户消息，meta 事件到达后替换为服务端记录
        setChat((prev) =>
          prev && prev.id === conversationId
            ? {
                ...prev,
                messages: [
                  ...prev.messages,
                  { id: -Date.now(), role: 'user', content, created_at: new Date().toISOString(), pending: true },
                ],
              }
            : prev,
        )
      }
      if (mode === 'regenerate') {
        // 先移除最后一条 AI 回复（服务端会真实替换）
        setChat((prev) => {
          if (!prev || prev.id !== conversationId) return prev
          const next = [...prev.messages]
          if (next.length > 0 && next[next.length - 1].role === 'assistant') next.pop()
          return { ...prev, messages: next }
        })
      }

      let partialText = ''

      const finish = () => {
        setStreaming(false)
        setStreamText('')
        abortRef.current = null
        refreshConversations().catch(() => undefined)
      }

      return streamCareerChat(
        conversationId,
        mode,
        content,
        {
          onMeta: (meta) => {
            setChat((prev) => {
              if (!prev || prev.id !== conversationId) return prev
              const next = [...prev.messages]
              if (mode === 'stream' && content) {
                const index = next.findIndex((m) => m.id < 0 && m.content === content)
                if (index >= 0) next[index] = { ...meta.user_message }
                else next.push(meta.user_message)
              }
              return { ...prev, messages: next }
            })
          },
          onDelta: (text) => {
            partialText += text
            setStreamText((prev) => prev + text)
          },
          onDone: (done) => {
            setChat((prev) =>
              prev && prev.id === conversationId
                ? { ...prev, messages: [...prev.messages, done.assistant_message] }
                : prev,
            )
            finish()
          },
          onError: (error) => {
            if (error.partial_saved && partialText) {
              setChat((prev) =>
                prev && prev.id === conversationId
                  ? {
                      ...prev,
                      messages: [
                        ...prev.messages,
                        {
                          id: -(Date.now() + 1),
                          role: 'assistant',
                          content: partialText,
                          created_at: new Date().toISOString(),
                        },
                      ],
                    }
                  : prev,
              )
            }
            setSendError({
              message: error.message,
              canRetry: mode === 'stream' && !error.partial_saved,
            })
            setRetryContent(mode === 'stream' && !error.partial_saved ? content : null)
            finish()
          },
          onEnd: () => {
            setDataVersion((n) => n + 1)
          },
        },
        controller.signal,
      )
        .catch((err) => {
          if (err instanceof DOMException && err.name === 'AbortError') {
            // 停止生成：服务端会保留已生成的部分；本地先展示，稍后与服务端同步
            if (partialText) {
              setChat((prev) =>
                prev && prev.id === conversationId
                  ? {
                      ...prev,
                      messages: [
                        ...prev.messages,
                        {
                          id: -(Date.now() + 2),
                          role: 'assistant',
                          content: partialText,
                          created_at: new Date().toISOString(),
                        },
                      ],
                    }
                  : prev,
              )
            }
            finish()
            window.setTimeout(() => {
              api
                .getCareerConversation(conversationId)
                .then((detail) => setChat({ id: detail.id, messages: detail.messages }))
                .catch(() => undefined)
            }, 800)
            return
          }
          // 请求没到达服务端（HTTP 错误等）：撤掉乐观插入的用户消息
          if (mode === 'stream' && content) {
            setChat((prev) =>
              prev && prev.id === conversationId
                ? {
                    ...prev,
                    messages: prev.messages.filter(
                      (m) => !(m.id < 0 && m.content === content),
                    ),
                  }
                : prev,
            )
          }
          setSendError({ message: errorMessage(err, NETWORK_ERROR), canRetry: mode === 'stream' })
          setRetryContent(mode === 'stream' ? content : null)
          finish()
        })
    },
    [refreshConversations],
  )

  const ensureConversation = useCallback((): Promise<number> => {
    if (activeId != null) return Promise.resolve(activeId)
    return api.createCareerConversation().then((conv) => {
      setConversations((prev) => [conv, ...prev])
      setChat(null)
      setActiveId(conv.id)
      return conv.id
    })
  }, [activeId])

  const send = () => {
    const content = draft.trim()
    if (!content || streaming) return
    setDraft('')
    ensureConversation()
      .then((id) => runStream(id, 'stream', content))
      .catch((err) => {
        setDraft(content) // 建会话失败也不丢用户的话
        setSendError({ message: errorMessage(err, NETWORK_ERROR), canRetry: false })
      })
  }

  const retry = () => {
    const content = retryContent
    if (!content || !activeId || streaming) return
    runStream(activeId, 'stream', content)
  }

  const regenerate = () => {
    if (!activeId || streaming) return
    runStream(activeId, 'regenerate', null)
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  const startNew = () => {
    setSendError(null)
    setRetryContent(null)
    api
      .createCareerConversation()
      .then((conv) => {
        setConversations((prev) => [conv, ...prev])
        setChat(null)
        setActiveId(conv.id)
        setMobileListOpen(false)
      })
      .catch((err) => {
        setSendError({ message: errorMessage(err, NETWORK_ERROR), canRetry: false })
      })
  }

  const removeConversation = (id: number) => {
    if (!window.confirm('确定删除这段对话吗？消息记录将一并删除，无法恢复。')) return
    api
      .deleteCareerConversation(id)
      .then(() => {
        setConversations((prev) => prev.filter((item) => item.id !== id))
        if (activeId === id) {
          setActiveId(null)
          setChat(null)
        }
      })
      .catch((err) => {
        setSendError({ message: errorMessage(err, NETWORK_ERROR), canRetry: false })
      })
  }

  const saveTitle = (id: number) => {
    const title = titleDraft.trim()
    setEditingTitleId(null)
    if (!title) return
    api
      .renameCareerConversation(id, title)
      .then((conv) => {
        setConversations((prev) => prev.map((item) => (item.id === conv.id ? conv : item)))
      })
      .catch((err) => {
        setSendError({ message: errorMessage(err, NETWORK_ERROR), canRetry: false })
      })
  }

  const sendQuickStart = (text: string) => {
    if (streaming) return
    ensureConversation()
      .then((id) => runStream(id, 'stream', text))
      .catch((err) => {
        setSendError({ message: errorMessage(err, NETWORK_ERROR), canRetry: false })
      })
  }

  const copyMessage = (content: string) => {
    navigator.clipboard?.writeText(content).catch(() => undefined)
  }

  const lastAssistantIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'assistant') return i
    }
    return -1
  }, [messages])

  const showWelcome = messages.length === 0 && !streaming && activeId != null

  return (
    <div className="flex h-[calc(100vh-13rem)] min-h-[560px] gap-8">
      {/* ---------- 左：历史会话（移动端为抽屉） ---------- */}
      {mobileListOpen ? (
        <div
          className="fixed inset-0 z-40 bg-ink/20 backdrop-blur-sm md:hidden"
          onClick={() => setMobileListOpen(false)}
          aria-hidden="true"
        />
      ) : null}
      <aside
        className={cn(
          'flex-col border-r border-line/70',
          mobileListOpen
            ? 'fixed inset-y-0 left-0 z-50 flex w-72 bg-[#F8FBFF] px-5 py-6 md:static md:z-auto md:w-64 md:shrink-0 md:bg-transparent md:py-0 md:pl-0 md:pr-5'
            : 'hidden w-64 shrink-0 md:flex',
        )}
      >
        <div className="flex items-center justify-between px-2">
          <h2 className="text-sm font-semibold tracking-wide text-ink-strong">对话手记</h2>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={startNew}
              className="inline-flex items-center gap-1 rounded-full bg-mist px-2.5 py-1 text-xs font-semibold text-brand-700 transition-colors hover:bg-shallow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              新对话
            </button>
            <button
              type="button"
              onClick={() => setMobileListOpen(false)}
              className="rounded-md p-1 text-ink-soft hover:text-ink md:hidden"
              aria-label="关闭列表"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
        <div className="mt-2 px-2">
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="搜索对话…"
            className="w-full rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
          />
        </div>
        <ul className="mt-2 flex-1 space-y-1 overflow-y-auto pb-2">
          {conversations.map((conv) => (
            <li key={conv.id} className="group relative">
              {editingTitleId === conv.id ? (
                <div className="px-2 py-1.5">
                  <input
                    value={titleDraft}
                    onChange={(event) => setTitleDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') saveTitle(conv.id)
                      if (event.key === 'Escape') setEditingTitleId(null)
                    }}
                    autoFocus
                    maxLength={60}
                    className="w-full rounded-lg border border-ripple bg-white px-2 py-1.5 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ripple/40"
                  />
                  <p className="mt-1 text-[11px] text-ink-soft">Enter 保存，Esc 取消</p>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setSendError(null)
                      setRetryContent(null)
                      setActiveId(conv.id)
                      setMobileListOpen(false)
                    }}
                    className={cn(
                      'w-full rounded-lg px-3 py-2.5 pr-14 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
                      conv.id === activeId
                        ? 'bg-gradient-to-r from-shallow/80 via-mist/70 to-transparent'
                        : 'hover:bg-white/70',
                    )}
                  >
                    <span
                      className={cn(
                        'block truncate text-sm font-medium',
                        conv.id === activeId ? 'text-brand-700' : 'text-ink',
                      )}
                    >
                      {conv.title}
                    </span>
                    <span className="mt-0.5 block text-xs text-ink-soft">
                      {conv.message_count > 0 ? `${conv.message_count} 条对话 · ` : '尚未开言 · '}
                      {formatTime(conv.updated_at)}
                    </span>
                  </button>
                  <span className="absolute right-2 top-2.5 flex items-center gap-0.5 opacity-0 transition-all focus-within:opacity-100 group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingTitleId(conv.id)
                        setTitleDraft(conv.title)
                      }}
                      title="重命名"
                      aria-label={`重命名对话：${conv.title}`}
                      className="rounded-md p-1 text-ink-soft/60 transition-colors hover:bg-mist hover:text-brand-600 focus-visible:outline-none"
                    >
                      <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeConversation(conv.id)}
                      title="删除这段对话"
                      aria-label={`删除对话：${conv.title}`}
                      className="rounded-md p-1 text-ink-soft/50 transition-colors hover:bg-mist hover:text-brand-600 focus-visible:outline-none"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </span>
                </>
              )}
            </li>
          ))}
          {conversations.length === 0 && !listError ? (
            <li className="px-3 py-6 text-sm leading-relaxed text-ink-soft">
              {search ? '没有匹配的对话。' : '还没有对话。每一段远行，都始于第一次问路。'}
            </li>
          ) : null}
          {listError ? (
            <li className="px-3 py-6 text-sm leading-relaxed text-ink-soft">
              对话列表暂时取不到，请稍后刷新重试。
            </li>
          ) : null}
        </ul>
      </aside>

      {/* ---------- 中：与小鸥的对话 ---------- */}
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-4 border-b border-line/70 pb-4">
          <div className="flex min-w-0 items-center gap-3.5">
            <button
              type="button"
              onClick={() => setMobileListOpen(true)}
              className="rounded-lg p-2 text-ink-soft transition-colors hover:bg-mist hover:text-brand-600 focus-visible:outline-none md:hidden"
              aria-label="打开对话列表"
            >
              <Menu className="h-[18px] w-[18px]" aria-hidden="true" />
            </button>
            <span className="shrink-0 rounded-full bg-mist p-1 ring-1 ring-line/70">
              <GullMascot size={44} status={streaming ? 'thinking' : 'idle'} />
            </span>
            <div className="min-w-0">
              <h1 className="text-xl font-bold tracking-tight text-ink-strong">知途 · 小鸥</h1>
              <p className="mt-0.5 truncate text-sm text-ink-soft">
                陪你梳理经历、发现可能，把目标变成可以逐步完成的行动
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={startNew}
              title="开始新的对话"
              className="rounded-lg p-2 text-ink-soft transition-colors hover:bg-mist hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40 md:hidden"
            >
              <Plus className="h-[18px] w-[18px]" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => setPanelOpen((prev) => !prev)}
              title={panelOpen ? '收起档案与计划' : '展开档案与计划'}
              className="hidden rounded-lg p-2 text-ink-soft transition-colors hover:bg-mist hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40 xl:block"
            >
              {panelOpen ? (
                <PanelRightClose className="h-[18px] w-[18px]" aria-hidden="true" />
              ) : (
                <PanelRightOpen className="h-[18px] w-[18px]" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {/* 消息流 */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="relative flex-1 overflow-y-auto py-6 pr-1"
        >
          {detailError ? (
            <p className="py-8 text-center text-sm text-ink-soft">{detailError}</p>
          ) : activeId == null ? (
            <div className="flex h-full flex-col items-center justify-center px-4 text-center">
              <GullMascot size={96} />
              <p className="mt-6 text-lg font-semibold text-ink-strong">每一段远行，都始于第一次问路。</p>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-soft">
                点「开始新的对话」，小鸥会陪你从当下的处境聊起。
              </p>
              <button
                type="button"
                onClick={startNew}
                className="mt-6 inline-flex items-center gap-2 rounded-full bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-card transition-all hover:bg-brand-700 hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                开始新的对话
              </button>
            </div>
          ) : showWelcome ? (
            <div className="mx-auto max-w-2xl">
              <div className="flex items-start gap-3">
                <span className="shrink-0 rounded-full bg-mist p-0.5 ring-1 ring-line/60">
                  <GullMascot size={40} />
                </span>
                <p className="rounded-2xl rounded-tl-md bg-white/85 px-4 py-3 text-[15px] leading-relaxed text-ink shadow-card">
                  {WELCOME_TEXT}
                </p>
              </div>
              <div className="mt-5 flex flex-col items-start gap-2 pl-12">
                {QUICK_STARTS.map((text) => (
                  <button
                    key={text}
                    type="button"
                    onClick={() => sendQuickStart(text)}
                    className="rounded-full border border-line bg-white/80 px-4 py-2 text-sm text-ink transition-colors hover:border-ripple hover:bg-mist hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
                  >
                    {text}
                  </button>
                ))}
                <p className="mt-1 text-xs text-ink-soft">也可以直接在下面输入，不必先回答任何问卷。</p>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-2xl space-y-6">
              {messages.map((message, index) =>
                message.role === 'user' ? (
                  <div key={message.id} className="flex justify-end">
                    <p
                      className={cn(
                        'max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md px-4 py-2.5 text-[15px] leading-relaxed text-ink',
                        message.pending ? 'bg-shallow/35' : 'bg-shallow/60',
                      )}
                    >
                      {message.content}
                    </p>
                  </div>
                ) : (
                  <div key={message.id} className="group flex items-start gap-3">
                    <span className="mt-0.5 shrink-0 rounded-full bg-mist p-0.5 ring-1 ring-line/60">
                      <GullMascot size={32} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">
                        {message.content}
                      </p>
                      <div className="mt-1 flex items-center gap-3 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                        <button
                          type="button"
                          onClick={() => copyMessage(message.content)}
                          className="inline-flex items-center gap-1 text-xs text-ink-soft transition-colors hover:text-brand-700 focus-visible:outline-none"
                        >
                          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                          复制
                        </button>
                        {index === lastAssistantIndex && !streaming ? (
                          <button
                            type="button"
                            onClick={regenerate}
                            className="inline-flex items-center gap-1 text-xs text-ink-soft transition-colors hover:text-brand-700 focus-visible:outline-none"
                          >
                            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                            重新生成
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ),
              )}

              {streaming ? (
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 shrink-0 rounded-full bg-mist p-0.5 ring-1 ring-line/60">
                    <GullMascot size={32} status="thinking" />
                  </span>
                  <div className="min-w-0 flex-1">
                    {streamText ? (
                      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">{streamText}</p>
                    ) : (
                      <p className="text-sm text-ink-soft">小鸥正在翻看你的档案与这段对话……</p>
                    )}
                    <button
                      type="button"
                      onClick={stop}
                      className="mt-2 inline-flex items-center gap-1 rounded-full border border-line bg-white px-3 py-1 text-xs font-medium text-ink-soft transition-colors hover:border-ripple hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
                    >
                      <Square className="h-3 w-3" aria-hidden="true" />
                      停止生成
                    </button>
                  </div>
                </div>
              ) : null}

              {sendError ? (
                <div className="rounded-xl border border-line bg-white/85 px-4 py-3">
                  <p className="text-sm leading-relaxed text-ink-soft">
                    这次没有回应：{sendError.message}
                    {sendError.canRetry ? '。你的话已经记录，可以直接重试。' : ''}
                  </p>
                  {sendError.canRetry && retryContent ? (
                    <button
                      type="button"
                      onClick={retry}
                      className="mt-2 inline-flex items-center gap-1 rounded-full bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                    >
                      <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                      重试
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}

          {!atBottom && messages.length > 0 ? (
            <button
              type="button"
              onClick={scrollToBottom}
              className="sticky bottom-4 left-full mr-1 flex h-9 w-9 items-center justify-center rounded-full border border-line bg-white text-ink-soft shadow-card transition-colors hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
              aria-label="回到底部"
            >
              <ArrowDown className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        {/* 输入区 */}
        <div className="border-t border-line/70 pt-4">
          <div className="flex items-end gap-3">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  send()
                }
              }}
              rows={2}
              maxLength={4000}
              placeholder="向小鸥说说你的困惑或计划……（Enter 发送，Shift+Enter 换行）"
              className="min-h-[52px] flex-1 resize-none rounded-xl border border-line bg-white/85 px-4 py-3 text-[15px] leading-relaxed text-ink placeholder:text-ink-soft/60 focus:border-ripple focus:outline-none focus:ring-2 focus:ring-ripple/40"
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="inline-flex h-[52px] shrink-0 items-center gap-2 rounded-xl border border-line bg-white px-5 text-sm font-semibold text-ink-soft transition-colors hover:border-ripple hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
              >
                <Square className="h-4 w-4" aria-hidden="true" />
                停止
              </button>
            ) : (
              <button
                type="button"
                onClick={send}
                disabled={!draft.trim()}
                className="inline-flex h-[52px] shrink-0 items-center gap-2 rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white shadow-card transition-all hover:bg-brand-700 hover:shadow-raised disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
              >
                <SendHorizontal className="h-4 w-4" aria-hidden="true" />
                送出
              </button>
            )}
          </div>
        </div>
      </section>

      {/* ---------- 右：档案 / 计划 / 联动 ---------- */}
      {panelOpen ? (
        <aside className="hidden w-80 shrink-0 border-l border-line/70 pl-6 xl:block">
          <CareerAdvisorPanel conversationId={activeId} dataVersion={dataVersion} />
        </aside>
      ) : null}
    </div>
  )
}
