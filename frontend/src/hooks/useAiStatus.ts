import { useCallback, useEffect, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { api } from '../api/client'
import type { AiStatus } from '../types'

export interface AiStatusState {
  loading: boolean
  data: AiStatus | null
  error: string | null
}

async function fetchAiStatus(setState: Dispatch<SetStateAction<AiStatusState>>) {
  try {
    const data = await api.aiStatus()
    setState({ loading: false, data, error: null })
  } catch {
    setState((prev) => ({ ...prev, loading: false, error: '无法获取 AI 配置状态' }))
  }
}

export function useAiStatus() {
  const [state, setState] = useState<AiStatusState>({
    loading: true,
    data: null,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    const setSafe: Dispatch<SetStateAction<AiStatusState>> = (action) => {
      if (!cancelled) {
        setState(action)
      }
    }
    void fetchAiStatus(setSafe)
    return () => {
      cancelled = true
    }
  }, [])

  const refresh = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true }))
    void fetchAiStatus(setState)
  }, [])

  return { ...state, refresh }
}
