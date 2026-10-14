import { useEffect } from 'react'
import { isOnboardingDone, useOnboarding } from './onboarding-context'

/**
 * 行舟（/app）首次进入时自动开启一次引航；
 * 完成或跳过后保存标记，刷新与再次进入不再自动弹出。
 */
export function useOnboardingAutoStart(pathname: string) {
  const { startTour } = useOnboarding()
  useEffect(() => {
    if (pathname !== '/app') return
    if (isOnboardingDone()) return
    const timer = window.setTimeout(() => {
      if (!isOnboardingDone()) startTour()
    }, 600)
    return () => window.clearTimeout(timer)
  }, [pathname, startTour])
}
