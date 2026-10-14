import {
  AudioLines,
  Bird,
  BookOpenText,
  Briefcase,
  FileText,
  Home,
  LayoutDashboard,
  MessageSquareText,
  NotebookPen,
  Orbit,
  PenLine,
  Puzzle,
  Scale,
  UserRound,
  Users,
  Waves,
} from 'lucide-react'
import { motion } from 'motion/react'
import type { LucideIcon } from 'lucide-react'
import { Link, NavLink } from 'react-router-dom'
import { LogoLockup } from '../LogoMark'
import { ServiceStatus } from '../ServiceStatus'
import { useAuth } from '../../context/useAuth'
import { cn } from '../../lib/cn'

interface NavEntry {
  to?: string
  label: string
  hint: string
  icon: LucideIcon
  available?: boolean
}

/** 侧边栏分组：启程 / 洞察 / 知行（未实现的模块如实标注，不伪装可用） */
const NAV_GROUPS: { title: string; entries: NavEntry[] }[] = [
  {
    title: '启程',
    entries: [
      { to: '/app', label: '行舟', hint: '工作区总览', icon: LayoutDashboard, available: true },
      {
        to: '/interview/new',
        label: '问澜',
        hint: '行业职业选择与面试训练',
        icon: MessageSquareText,
        available: true,
      },
      {
        to: '/career-guide',
        label: '知途',
        hint: 'AI 职业顾问「小鸥」，问路知途',
        icon: Bird,
        available: true,
      },
    ],
  },
  {
    title: '洞察',
    entries: [
      { to: '/skills', label: '观己', hint: '能力星图与训练建议', icon: Orbit, available: true },
      { to: '/reports', label: '回响', hint: '训练历史与评分报告', icon: FileText, available: true },
      { to: '/challenges', label: '度衡', hint: '限时挑战，服务端计时判卷', icon: Scale, available: true },
      { to: '/mistakes', label: '回澜', hint: '错题本与间隔复习', icon: NotebookPen, available: true },
    ],
  },
  {
    title: '知行',
    entries: [
      {
        to: '/jobs',
        label: '知岗',
        hint: '读懂岗位所需，找准能力对应',
        icon: Briefcase,
        available: true,
      },
      {
        to: '/job-library',
        label: '知潮',
        hint: '真实岗位资料库，潮起有信',
        icon: Waves,
        available: true,
      },
      {
        to: '/resume',
        label: '履历成章',
        hint: '让经历有序，让优势成章',
        icon: PenLine,
        available: true,
      },
      { to: '/matching', label: '合契', hint: '简历与岗位匹配', icon: Puzzle, available: true },
      { to: '/knowledge', label: '知藏', hint: '知识库，出题有据', icon: BookOpenText, available: true },
      { to: '/expression', label: '听澜', hint: '语音表达分析', icon: AudioLines, available: true },
      { to: '/concerto', label: '协奏', hint: '三席同台的表达协作台', icon: Users, available: true },
    ],
  },
]

interface SidebarNavProps {
  /** 桌面侧栏与移动抽屉同时挂载时，layoutId 指示条需要彼此区分 */
  indicatorId: string
  onNavigate?: () => void
}

/** 编辑式侧栏：无框导航行 + 左侧细指示线 + 分组眉题细线，浅蓝白渐变底。 */
export function SidebarNav({ indicatorId, onNavigate }: SidebarNavProps) {
  const { user } = useAuth()
  return (
    <div className="flex h-full flex-col">
      <div className="px-6 pb-2 pt-7">
        <Link
          to="/"
          onClick={onNavigate}
          aria-label="返回观澜首页"
          className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
        >
          <LogoLockup />
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-4 pb-4 pt-2" aria-label="工作台导航">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mt-6 first:mt-3">
            {/* 分组眉题：字距拉开的小字 + 向右渐隐细线 */}
            <div className="mb-2 flex items-center gap-3 px-2">
              <p className="text-[11px] font-semibold tracking-[0.26em] text-ink-soft/80">
                {group.title}
              </p>
              <span
                aria-hidden="true"
                className="h-px flex-1 bg-gradient-to-r from-line to-transparent"
              />
            </div>
            <ul>
              {group.entries.map((entry) =>
                entry.available && entry.to ? (
                  <li key={entry.label}>
                    <NavLink
                      to={entry.to}
                      onClick={onNavigate}
                      title={entry.hint}
                      className={({ isActive }) =>
                        cn(
                          'group relative flex items-center gap-3 rounded-lg py-2 pl-4 pr-3 text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
                          isActive
                            ? 'bg-gradient-to-r from-shallow/80 via-mist/70 to-transparent text-brand-700'
                            : 'text-ink-soft hover:bg-white/70 hover:text-ink',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          {/* 左侧细指示线：选中时出现，跨组平滑移动 */}
                          {isActive ? (
                            <motion.span
                              layoutId={`sidebar-nav-indicator-${indicatorId}`}
                              className="absolute inset-y-1 left-0 w-[3px] rounded-full bg-brand-600"
                              transition={{ type: 'spring', bounce: 0.2, duration: 0.45 }}
                              aria-hidden="true"
                            />
                          ) : null}
                          <entry.icon
                            className={cn(
                              'h-[17px] w-[17px] shrink-0 transition-colors',
                              isActive ? 'text-brand-600' : 'text-ink-soft/75 group-hover:text-brand-600/80',
                            )}
                            aria-hidden="true"
                          />
                          {/* 仅显示功能名；模块说明经整行的 title 悬停提示呈现，避免占位文字挤占宽度截断功能名 */}
                          <span className="min-w-0 flex-1 truncate">{entry.label}</span>
                        </>
                      )}
                    </NavLink>
                  </li>
                ) : (
                  <li
                    key={entry.label}
                    title={entry.hint}
                    aria-disabled="true"
                    className="flex cursor-not-allowed items-center gap-3 rounded-lg py-2 pl-4 pr-3 text-sm font-medium text-ink-soft/45"
                  >
                    <entry.icon className="h-[17px] w-[17px] shrink-0 text-ink-soft/35" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate">{entry.label}</span>
                    <span className="rounded-full bg-slate-100 px-1.5 py-px text-[10px] font-normal text-ink-soft/70">
                      即将上线
                    </span>
                  </li>
                ),
              )}
            </ul>
          </div>
        ))}
      </nav>

      {/* 底部：服务状态与账户入口，视觉上退居其次 */}
      <div className="space-y-2.5 border-t border-line/70 px-5 py-4">
        <ServiceStatus className="justify-start" />
        <div className="flex items-center justify-between gap-2">
          <NavLink
            to={user ? '/me' : '/auth'}
            onClick={onNavigate}
            title={user ? '查看我的名笺' : '登录后查看我的名笺'}
            className={({ isActive }) =>
              cn(
                'flex min-w-0 items-center gap-2 rounded-lg px-1.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40',
                isActive ? 'text-brand-700' : 'text-ink-soft hover:text-brand-600',
              )
            }
          >
            <UserRound className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="truncate">我的名笺</span>
            <span className="truncate text-xs font-normal text-ink-soft/75">
              {user ? user.nickname : '未登录'}
            </span>
          </NavLink>
          <Link
            to="/"
            onClick={onNavigate}
            title="返回首页"
            className="flex shrink-0 items-center gap-1.5 rounded-lg p-1.5 text-ink-soft transition-colors hover:bg-white/70 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40"
          >
            <Home className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </div>
  )
}
