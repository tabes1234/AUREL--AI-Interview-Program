import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  BarChart3,
  Compass,
  MessagesSquare,
  NotebookPen,
  Sailboat,
  X,
  type LucideIcon,
} from 'lucide-react'
import { LogoMark } from '../LogoMark'
import { cn } from '../../lib/cn'
import { markOnboardingDone, OnboardingContext } from './onboarding-context'

interface OnboardingStep {
  title: string
  body: string
  /** 对应的真实栏目 / 页面，展示在栏目标签中 */
  section: string
  /** 该栏目页面的真实截图（public/onboarding 下） */
  image: string
  icon: LucideIcon
}

/** 引航五步：每一步对应一个真实栏目并配真实界面截图，不描述尚未接入的能力 */
const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    title: '临水初见',
    body: '观水有术，必观其澜。你的每一次作答都会在这里激起回响，每一分成长都有迹可循——见微，方能知远。',
    section: '首页 · 观澜之意',
    image: '/onboarding/onboarding-home.png',
    icon: Compass,
  },
  {
    title: '扬帆行舟',
    body: '行舟是你的港湾：每日的训练任务与各处功能，皆沿这条水路停泊。从此处启程，随取随用。',
    section: '栏目 · 行舟（工作台）',
    image: '/onboarding/onboarding-app.png',
    icon: Sailboat,
  },
  {
    title: '问澜起笔',
    body: '择定行业与志业，问澜便落下第一问。题目由真实模型生成，追问随你的回答而深——步步见真。',
    section: '栏目 · 问澜（面试练习）',
    image: '/onboarding/onboarding-interview.png',
    icon: MessagesSquare,
  },
  {
    title: '观己知远',
    body: '观己把你的回答织成能力星图，每一分都附原文为证；回响收存每份报告。长处短处，静水照影，了然于目。',
    section: '栏目 · 观己（能力星图）',
    image: '/onboarding/onboarding-skills.png',
    icon: BarChart3,
  },
  {
    title: '泊岸拾澜',
    body: '名笺安放你的账户与设置，澜讯捎来每一封航讯。泊岸小憩，再启新程——观澜始终在这里。',
    section: '栏目 · 名笺（个人资料）',
    image: '/onboarding/onboarding-me.png',
    icon: NotebookPen,
  },
]

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1)

  const startTour = useCallback(() => {
    setDirection(1)
    setStep(0)
    setOpen(true)
  }, [])

  const finish = useCallback(() => {
    setOpen(false)
    markOnboardingDone()
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') finish()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, finish])

  const total = ONBOARDING_STEPS.length
  const isLast = step === total - 1

  const goPrev = () => {
    if (step <= 0) return
    setDirection(-1)
    setStep((s) => s - 1)
  }

  const goNext = () => {
    if (isLast) {
      finish()
      return
    }
    setDirection(1)
    setStep((s) => s + 1)
  }

  const current = ONBOARDING_STEPS[step]
  const CurrentIcon = current.icon

  return (
    <OnboardingContext.Provider value={{ startTour }}>
      {children}

      <AnimatePresence>
        {open ? (
          <motion.div
            key="onboarding-veil"
            className="fixed inset-0 z-[70] flex items-center justify-center bg-[#12294a]/60 p-4 backdrop-blur-[3px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={finish}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label="引航：观澜使用引导"
              className="relative grid max-h-[min(640px,92vh)] w-full max-w-2xl grid-rows-[minmax(0,1fr)] overflow-hidden rounded-3xl border border-line/70 bg-white shadow-raised sm:grid-cols-[224px_1fr]"
              initial={{ opacity: 0, y: 22, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.26, ease: [0.22, 0.61, 0.36, 1] }}
              onClick={(event) => event.stopPropagation()}
            >
              {/* 顶部细进度条 */}
              <div className="absolute inset-x-0 top-0 z-10 h-0.5 bg-mist" aria-hidden="true">
                <motion.div
                  className="h-full bg-gradient-to-r from-brand-500 to-brand-600"
                  animate={{ width: `${((step + 1) / total) * 100}%` }}
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                />
              </div>

              {/* 左侧品牌栏（桌面端）：深蓝渐变 + 波纹装饰 + 步骤目录 */}
              <div
                className="relative hidden min-h-0 flex-col overflow-hidden bg-[linear-gradient(168deg,#5B92E2_0%,#3E70BE_55%,#2E5AA8_100%)] p-6 sm:flex"
                aria-hidden="true"
              >
                {/* 波纹装饰 */}
                <svg
                  className="pointer-events-none absolute -right-8 top-4 w-56 opacity-30"
                  viewBox="0 0 220 90"
                  fill="none"
                >
                  <path
                    d="M0 22c26-12 52-12 78 0s52 12 78 0 40-9 64 2"
                    stroke="#FFFFFF"
                    strokeWidth="2.4"
                    strokeLinecap="round"
                  />
                  <path
                    d="M0 50c26-9 52-9 78 0s52 9 78 0 40-7 64 2"
                    stroke="#DCEBFF"
                    strokeWidth="2"
                    strokeLinecap="round"
                    opacity="0.8"
                  />
                  <path
                    d="M0 76c26-7 52-7 78 0s52 7 78 0 40-5 64 2"
                    stroke="#BDD8FC"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    opacity="0.6"
                  />
                  <circle cx="176" cy="14" r="6" fill="#FFE9BE" opacity="0.9" />
                </svg>

                <div className="relative flex items-center gap-2.5">
                  <LogoMark size={34} />
                  <div className="leading-none">
                    <p className="text-sm font-bold text-white">观澜 AUREL</p>
                    <p className="mt-1 text-[10px] tracking-wider text-shallow/85">引航</p>
                  </div>
                </div>

                {/* 步骤目录：当前项高亮 */}
                <nav className="relative mt-8 flex-1 space-y-1.5">
                  {ONBOARDING_STEPS.map((item, index) => {
                    const active = index === step
                    const passed = index < step
                    return (
                      <div
                        key={item.title}
                        className={cn(
                          'flex items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-medium transition-all duration-300',
                          active
                            ? 'bg-white/18 text-white shadow-[0_2px_10px_rgba(10,30,64,0.18)]'
                            : passed
                              ? 'text-white/75'
                              : 'text-white/45',
                        )}
                      >
                        <span
                          className={cn(
                            'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold transition-colors',
                            active
                              ? 'border-white/70 bg-white text-brand-700'
                              : passed
                                ? 'border-white/50 bg-white/15 text-white'
                                : 'border-white/30 text-white/60',
                          )}
                        >
                          {index + 1}
                        </span>
                        {item.title}
                      </div>
                    )
                  })}
                </nav>

                <p className="relative mt-6 text-[10px] leading-relaxed tracking-wider text-shallow/70">
                  见微知远，向新而行。
                </p>
              </div>

              {/* 右侧内容区 */}
              <div className="flex min-h-0 min-w-0 flex-col">
                {/* 头部：说明 + 关闭 */}
                <div className="flex items-center gap-3 border-b border-line/60 px-6 pb-4 pt-5">
                  <div className="min-w-0 flex-1">
                    <p className="text-base font-bold text-ink">引航</p>
                    <p className="mt-0.5 truncate text-xs text-ink-soft">
                      五步一程，临水问澜——愿它如灯引水，照见你的方向。
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={finish}
                    aria-label="关闭引航"
                    className="rounded-md p-1.5 text-ink-soft transition-colors hover:bg-mist hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>

                {/* 步骤内容：真实界面截图 + 图标章 + 按方向轻移切换 */}
                <div className="relative min-h-0 flex-1 overflow-y-auto px-6 py-5">
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                      key={step}
                      initial={{ opacity: 0, x: direction * 30 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: direction * -30 }}
                      transition={{ duration: 0.24, ease: 'easeOut' }}
                    >
                      {/* 对应栏目的真实界面截图 */}
                      <div className="overflow-hidden rounded-xl border border-line/70 bg-mist shadow-[0_2px_12px_rgba(10,30,64,0.08)]">
                        <img
                          src={current.image}
                          alt={`${current.title}对应的界面截图`}
                          className="h-36 w-full object-cover object-top sm:h-40"
                          decoding="async"
                        />
                      </div>

                      <div className="mt-4 flex items-center gap-3">
                        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-shallow to-mist shadow-[0_2px_10px_rgba(77,131,214,0.16)]">
                          <CurrentIcon className="h-6 w-6 text-brand-600" aria-hidden="true" />
                        </span>
                        <div className="min-w-0">
                          <p className="text-[11px] font-semibold tracking-[0.2em] text-brand-600">
                            第 {step + 1} 步 · 共 {total} 步
                          </p>
                          <h2 className="mt-0.5 text-xl font-bold text-ink">{current.title}</h2>
                        </div>
                        {/* 桌面端大数字水印 */}
                        <span
                          className="ml-auto hidden select-none text-6xl font-bold leading-none text-shallow/60 lg:block"
                          aria-hidden="true"
                        >
                          {String(step + 1).padStart(2, '0')}
                        </span>
                      </div>

                      {/* 对应栏目标签 */}
                      <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-mist px-2.5 py-1 text-[11px] font-semibold text-brand-700">
                        <CurrentIcon className="h-3.5 w-3.5" aria-hidden="true" />
                        {current.section}
                      </span>

                      <p className="mt-2.5 text-sm leading-relaxed text-ink-soft">{current.body}</p>
                    </motion.div>
                  </AnimatePresence>

                  {/* 步骤进度点（移动端主要进度指示） */}
                  <div className="mt-5 flex items-center gap-1.5 sm:hidden" aria-hidden="true">
                    {ONBOARDING_STEPS.map((item, index) => (
                      <span
                        key={item.title}
                        className={cn(
                          'h-1.5 rounded-full transition-all duration-300',
                          index === step ? 'w-5 bg-brand-600' : 'w-1.5 bg-ripple/70',
                        )}
                      />
                    ))}
                  </div>
                </div>

                {/* 底部操作：跳过 / 上一步 / 下一步（完成引航） */}
                <div className="flex items-center gap-2 border-t border-line/60 px-6 py-4">
                  <button
                    type="button"
                    onClick={finish}
                    className="rounded-lg px-3 py-2 text-sm font-medium text-ink-soft transition-colors hover:bg-mist hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                  >
                    跳过
                  </button>
                  <div className="flex-1" />
                  <button
                    type="button"
                    onClick={goPrev}
                    disabled={step === 0}
                    className={cn(
                      'rounded-lg border border-line px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50',
                      step === 0
                        ? 'cursor-not-allowed text-ink-soft/40'
                        : 'text-brand-600 hover:-translate-y-px hover:border-brand-600/40 hover:bg-brand-50 hover:shadow-[0_4px_12px_rgba(77,131,214,0.16)] active:translate-y-0 active:scale-[0.985]',
                    )}
                  >
                    上一步
                  </button>
                  <button
                    type="button"
                    onClick={goNext}
                    className="rounded-lg bg-[linear-gradient(180deg,#5589D9_0%,#4D83D6_100%)] px-5 py-2 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(49,95,173,0.18)] transition-all hover:-translate-y-px hover:bg-[linear-gradient(180deg,#4A7ECC_0%,#3F72BE_100%)] hover:shadow-[0_5px_14px_rgba(49,95,173,0.24)] active:translate-y-0 active:scale-[0.985] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                  >
                    {isLast ? '完成引航' : '下一步'}
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </OnboardingContext.Provider>
  )
}
