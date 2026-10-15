// 使用事件上报：登录用户在工作区页面的访问事件（观澜管理中心数据源之一）。
// - 30 秒去重在后端执行，这里仅做失败静默（上报绝不影响页面本身）；
// - 仅上报模块标识与页面名，不含任何输入内容。

import { api } from '../api/client'

/** 前端路由 → 模块标识（与后端 usage_tracking.MODULES 白名单一致） */
const ROUTE_MODULES: { prefix: string; module: string; name: string }[] = [
  { prefix: '/app', module: 'xingzhou', name: 'dashboard' },
  { prefix: '/career-guide', module: 'zhitu', name: 'career_chat' },
  { prefix: '/interview/new', module: 'wenlan', name: 'interview_new' },
  { prefix: '/interview/preview', module: 'wenlan', name: 'interview_preview' },
  { prefix: '/interview/session', module: 'wenlan', name: 'interview_session' },
  { prefix: '/reports', module: 'huixiang', name: 'reports' },
  { prefix: '/knowledge', module: 'zhicang', name: 'knowledge' },
  { prefix: '/skills', module: 'guanji', name: 'skills' },
  { prefix: '/matching', module: 'heqi', name: 'matching' },
  { prefix: '/expression', module: 'tinglan', name: 'expression' },
  { prefix: '/jobs', module: 'zhigang', name: 'jobs' },
  { prefix: '/job-library', module: 'zhichao', name: 'job_library' },
  { prefix: '/resume-gallery', module: 'shibei', name: 'resume_gallery' },
  { prefix: '/resume', module: 'lvli', name: 'resume' },
  { prefix: '/mistakes', module: 'huilan', name: 'mistakes' },
  { prefix: '/challenges', module: 'duheng', name: 'challenges' },
  { prefix: '/concerto', module: 'xiezou', name: 'concerto' },
]

/** 前缀最长匹配优先，避免 /interview/new 被 /interview 吞掉 */
export function resolveModule(pathname: string): { module: string; name: string } | null {
  const matches = ROUTE_MODULES.filter((r) => pathname === r.prefix || pathname.startsWith(`${r.prefix}/`) || pathname.startsWith(r.prefix))
  if (matches.length === 0) return null
  matches.sort((a, b) => b.prefix.length - a.prefix.length)
  return matches[0]
}

/** 路由变化时调用：静默上报页面访问（错误吞掉，不打扰用户） */
export function trackPageView(pathname: string): void {
  const target = resolveModule(pathname)
  if (!target) return
  api.reportPageView(target.module, target.name).catch(() => {
    // 统计上报失败不影响用户体验
  })
}
