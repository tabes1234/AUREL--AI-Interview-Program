import { useCallback, useEffect, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { ApiError, api } from '../api/client'
import type { HealthResponse } from '../types'

export type HealthStatus = 'loading' | 'online' | 'offline'

export interface HealthState {
  status: HealthStatus
  data: HealthResponse | null
  error: string | null
}

const POLL_INTERVAL_MS = 30_000

async function fetchHealth(setState: Dispatch<SetStateAction<HealthState>>) {
  try {
    const data = await api.health()
    setState({ status: 'online', data, error: null })
  } catch (error) {
    const message = error instanceof ApiError ? error.message : '未知错误'
    setState((prev) => ({ ...prev, status: 'offline', error: message }))
  }
}

export function useHealth() {
  const [state, setState] = useState<HealthState>({
    status: 'loading',
    data: null,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    const setSafe: Dispatch<SetStateAction<HealthState>> = (action) => {
      if (!cancelled) {
        setState(action)
      }
    }

    void fetchHealth(setSafe)
    const timerId = window.setInterval(() => {
      void fetchHealth(setSafe)
    }, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(timerId)
    }
  }, [])

  const refresh = useCallback(() => {
    setState((prev) => ({ ...prev, status: 'loading' }))
    void fetchHealth(setState)
  }, [])

  return { ...state, refresh }
}
