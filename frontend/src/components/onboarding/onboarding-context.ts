import { createContext, useContext } from 'react'

export const ONBOARDING_DONE_KEY = 'aurel_onboarding_done'

export interface OnboardingContextValue {
  startTour: () => void
}

export const OnboardingContext = createContext<OnboardingContextValue | null>(null)

export function useOnboarding(): OnboardingContextValue {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding 必须在 OnboardingProvider 内使用')
  return ctx
}

/** 是否已完成过引航（非敏感 UI 状态，仅存于本地浏览器） */
export function isOnboardingDone(): boolean {
  try {
    return window.localStorage.getItem(ONBOARDING_DONE_KEY) === '1'
  } catch {
    // 隐私模式等无法读写 localStorage 时视为已完成，避免反复打扰
    return true
  }
}

export function markOnboardingDone() {
  try {
    window.localStorage.setItem(ONBOARDING_DONE_KEY, '1')
  } catch {
    // 忽略存储失败
  }
}
