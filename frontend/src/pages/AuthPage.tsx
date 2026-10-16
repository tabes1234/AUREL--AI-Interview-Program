import { AtSign, KeyRound, Loader2, ShieldCheck, UserRound } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { PageBackground } from '../components/PageBackground'
import { LogoLockup, LogoMark } from '../components/LogoMark'
import { useAuth } from '../context/useAuth'
import { cn } from '../lib/cn'

// 与后端规则一致：用户名 3-24 位中英文/数字/下划线；密码 8-64 位且同时含字母与数字
const USERNAME_PATTERN = /^[A-Za-z0-9_\u4e00-\u9fff]{3,24}$/
const PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/

type AuthMode = 'register' | 'login'

interface AuthFormState {
  username: string
  password: string
  confirmPassword: string
  nickname: string
}

const EMPTY_FORM: AuthFormState = { username: '', password: '', confirmPassword: '', nickname: '' }

const inputClass =
  'w-full rounded-xl border border-line bg-white py-2.5 pl-10 pr-4 text-sm text-ink transition-shadow placeholder:text-ink-soft/50 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-600/20'

export default function AuthPage() {
  const { user, loading, refresh } = useAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const redirectTarget = searchParams.get('redirect') || '/app'

  const [mode, setMode] = useState<AuthMode>('register')
  const [form, setForm] = useState<AuthFormState>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  // 已登录用户访问 /auth 时直接回到目标页面
  if (!loading && user) {
    return <Navigate to={redirectTarget} replace />
  }

  const usernameOk = USERNAME_PATTERN.test(form.username.trim())
  const passwordOk = PASSWORD_PATTERN.test(form.password)
  const confirmOk = mode === 'login' || form.confirmPassword === form.password
  const nicknameOk = mode === 'login' || (form.nickname.trim().length >= 2 && form.nickname.trim().length <= 20)
  const formOk = usernameOk && passwordOk && confirmOk && nicknameOk

  const update = (patch: Partial<AuthFormState>) => {
    setForm((prev) => ({ ...prev, ...patch }))
    setMessage(null)
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!formOk || submitting) return
    setSubmitting(true)
    setMessage(null)
    try {
      if (mode === 'register') {
        await api.register({
          username: form.username.trim(),
          password: form.password,
          nickname: form.nickname.trim(),
        })
      } else {
        await api.login({ username: form.username.trim(), password: form.password })
      }
      // 会话 Cookie 已由后端下发；刷新全局登录态后再回到来路页面
      await refresh()
      navigate(redirectTarget, { replace: true })
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : '未能完成，请稍后再试',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const switchMode = (next: AuthMode) => {
    setMode(next)
    setForm(EMPTY_FORM)
    setMessage(null)
  }

  const handleTestLogin = async () => {
    if (submitting) return
    setSubmitting(true)
    setMessage(null)
    try {
      await api.testLogin()
      await refresh()
      navigate(redirectTarget, { replace: true })
    } catch (error) {
      setMessage({
        tone: 'error',
        text: error instanceof Error ? error.message : '未能进入，请稍后再试',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-surface">
      {/* 深夜蓝海场景背景（固定底层，pointer-events: none）+ 柔和光晕 */}
      <PageBackground scene="auth" />
      <div className="relative flex min-h-screen flex-col">
        <header className="flex items-center justify-between px-5 py-5 sm:px-8">
          <Link to="/" aria-label="返回观澜首页" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-shallow">
            <LogoLockup tone="light" />
          </Link>
          <Link to="/" className="text-sm text-shallow transition-colors hover:text-white">
            返回首页
          </Link>
        </header>

        <main className="flex flex-1 items-center justify-center px-4 pb-14 pt-2">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 0.61, 0.36, 1] }}
            className="grid w-full max-w-3xl overflow-hidden rounded-3xl shadow-raised glass-surface glass-auth md:grid-cols-[264px_1fr]"
          >
            {/* 左侧品牌面板（桌面端）：深蓝渐变 + 波纹装饰 + 品牌语 */}
            <div
              className="relative hidden flex-col overflow-hidden bg-[linear-gradient(168deg,#5B92E2_0%,#3E70BE_55%,#2E5AA8_100%)] p-7 md:flex"
              aria-hidden="true"
            >
              <svg
                className="pointer-events-none absolute -right-10 top-10 w-64 opacity-30"
                viewBox="0 0 240 100"
                fill="none"
              >
                <path
                  d="M0 24c28-13 56-13 84 0s56 13 84 0 44-10 72 2"
                  stroke="#FFFFFF"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                />
                <path
                  d="M0 56c28-10 56-10 84 0s56 10 84 0 44-8 72 2"
                  stroke="#DCEBFF"
                  strokeWidth="2"
                  strokeLinecap="round"
                  opacity="0.8"
                />
                <path
                  d="M0 86c28-8 56-8 84 0s56 8 84 0 44-6 72 2"
                  stroke="#BDD8FC"
                  strokeWidth="1.7"
                  strokeLinecap="round"
                  opacity="0.6"
                />
                <circle cx="192" cy="14" r="6.5" fill="#FFE9BE" opacity="0.9" />
              </svg>

              <div className="relative">
                <LogoMark size={40} />
                <p className="mt-4 text-lg font-bold text-white">观澜 AUREL</p>
                <p className="mt-1.5 text-xs leading-relaxed tracking-wider text-shallow/90">
                  见微知远，向新而行。
                </p>
                <p className="mt-1 text-[10px] tracking-[0.14em] text-shallow/60">
                  See the subtle. Shape what's next.
                </p>
              </div>

              <div className="relative mt-auto space-y-3 pt-10">
                {[
                  '每一次探索，都始于一次抵达',
                  '一个名字，一把钥匙，来去自在',
                  '让每一次成长都有迹可循',
                ].map((line) => (
                  <div key={line} className="flex items-center gap-2.5">
                    <span className="h-1 w-1 shrink-0 rounded-full bg-shallow/80" />
                    <p className="text-xs leading-relaxed text-shallow/85">{line}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* 右侧表单区 */}
            <div className="min-w-0 p-6 sm:p-9">
              <h1 className="text-center text-2xl font-bold text-ink">
                {mode === 'register' ? '初入观澜' : '再会观澜'}
              </h1>
              <p className="mt-2 text-center text-sm leading-relaxed text-ink-soft">
                {mode === 'register'
                  ? '取一个名字，设好用户名与密码，即刻开启你的学习之旅'
                  : '欢迎回来，报上用户名即可继续此前的旅程'}
              </p>

              {/* 模式切换 */}
              <div className="mt-6 grid grid-cols-2 gap-1 rounded-xl bg-mist/70 p-1" role="tablist">
                {(
                  [
                    { key: 'register', label: '初入观澜' },
                    { key: 'login', label: '再会观澜' },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    role="tab"
                    aria-selected={mode === tab.key}
                    onClick={() => switchMode(tab.key)}
                    className={cn(
                      'relative rounded-lg px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50',
                      mode === tab.key ? 'text-brand-700' : 'text-ink-soft hover:text-ink',
                    )}
                  >
                    {mode === tab.key ? (
                      <motion.span
                        layoutId="auth-tab-pill"
                        className="absolute inset-0 rounded-lg bg-white shadow-sm"
                        transition={{ type: 'spring', bounce: 0.2, duration: 0.45 }}
                        aria-hidden="true"
                      />
                    ) : null}
                    <span className="relative">{tab.label}</span>
                  </button>
                ))}
              </div>

              <form onSubmit={handleSubmit} className="mt-7 space-y-5" noValidate>
                {mode === 'register' ? (
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-ink">昵称</span>
                    <div className="relative">
                      <UserRound
                        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft/60"
                        aria-hidden="true"
                      />
                      <input
                        type="text"
                        value={form.nickname}
                        onChange={(e) => update({ nickname: e.target.value })}
                        placeholder="你希望被如何称呼（2-20 字）"
                        autoComplete="nickname"
                        maxLength={20}
                        className={inputClass}
                      />
                    </div>
                  </label>
                ) : null}

                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-ink">用户名</span>
                  <div className="relative">
                    <AtSign
                      className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft/60"
                      aria-hidden="true"
                    />
                    <input
                      type="text"
                      value={form.username}
                      onChange={(e) => update({ username: e.target.value })}
                      placeholder="3-24 位中英文、数字或下划线"
                      autoComplete="username"
                      maxLength={24}
                      className={inputClass}
                    />
                  </div>
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-ink">密码</span>
                  <div className="relative">
                    <KeyRound
                      className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft/60"
                      aria-hidden="true"
                    />
                    <input
                      type="password"
                      value={form.password}
                      onChange={(e) => update({ password: e.target.value })}
                      placeholder="8 位以上，同时包含字母与数字"
                      autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                      maxLength={64}
                      className={inputClass}
                    />
                  </div>
                </label>

                {mode === 'register' ? (
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-ink">确认密码</span>
                    <div className="relative">
                      <KeyRound
                        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft/60"
                        aria-hidden="true"
                      />
                      <input
                        type="password"
                        value={form.confirmPassword}
                        onChange={(e) => update({ confirmPassword: e.target.value })}
                        placeholder="再输入一次密码"
                        autoComplete="new-password"
                        maxLength={64}
                        className={inputClass}
                      />
                    </div>
                    {form.confirmPassword.length > 0 && !confirmOk ? (
                      <span className="mt-1.5 block text-xs text-rose-600">两次输入的密码还不一致</span>
                    ) : null}
                  </label>
                ) : null}

                <AnimatePresence>
                  {message ? (
                    <motion.p
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      role="status"
                      className={cn(
                        'flex items-start gap-1.5 rounded-xl px-3.5 py-2.5 text-sm leading-relaxed',
                        message.tone === 'ok'
                          ? 'bg-brand-50 text-brand-700'
                          : 'bg-rose-50 text-rose-700',
                      )}
                    >
                      <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                      {message.text}
                    </motion.p>
                  ) : null}
                </AnimatePresence>

                <button
                  type="submit"
                  disabled={!formOk || submitting}
                  className={cn(
                    'w-full rounded-xl px-4 py-3 text-base font-bold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50',
                    formOk && !submitting
                      ? 'bg-[linear-gradient(180deg,#5589D9_0%,#4D83D6_100%)] text-white shadow-[0_1px_2px_rgba(49,95,173,0.18)] hover:-translate-y-px hover:bg-[linear-gradient(180deg,#4A7ECC_0%,#3F72BE_100%)] hover:shadow-[0_6px_16px_rgba(49,95,173,0.26)] active:translate-y-0 active:scale-[0.985]'
                      : 'cursor-not-allowed bg-mist text-ink-soft/60',
                  )}
                >
                  {submitting ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                      正在确认…
                    </span>
                  ) : mode === 'register' ? (
                    '确认注册'
                  ) : (
                    '进入观澜'
                  )}
                </button>
              </form>
              <div className="mt-5 border-t border-line pt-4">
                <button
                  type="button"
                  onClick={handleTestLogin}
                  disabled={submitting}
                  className="w-full rounded-xl border border-line bg-white/70 px-4 py-3 text-sm font-semibold text-ink-soft transition hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? '正在进入…' : '测试登录 · 一键进入体验'}
                </button>
                <p className="mt-2 text-center text-xs leading-5 text-ink-soft">
                  无需注册，直接以访客身份体验全部功能；数据与其他账号相互独立
                </p>
              </div>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
