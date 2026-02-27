import { createContext } from 'react'
import type { RealtimeEvent } from '../types'

export type Listener = (event: RealtimeEvent) => void

export type RealtimeContextValue = {
  connected: boolean
  lastEventAt: string | null
  subscribe: (listener: Listener) => () => void
}

export const RealtimeContext = createContext<RealtimeContextValue | null>(null)
