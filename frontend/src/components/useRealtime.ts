import { useContext } from 'react'

import { RealtimeContext } from './realtime-context'

export function useRealtime() {
  const context = useContext(RealtimeContext)
  if (!context) {
    throw new Error('useRealtime must be used within RealtimeProvider')
  }
  return context
}
