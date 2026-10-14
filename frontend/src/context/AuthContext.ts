import { createContext } from 'react'
import type { AuthUser } from '../types'

export interface AuthContextValue {
  user: AuthUser | null
  /** 首次 /auth/me 探测是否仍在进行 */
  loading: boolean
  refresh: () => Promise<AuthUser | null>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
