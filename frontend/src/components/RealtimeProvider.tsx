import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react'

import type { RealtimeEvent } from '../types'
import { RealtimeContext, type Listener } from './realtime-context'

export function RealtimeProvider({ children }: PropsWithChildren) {
  const listeners = useRef(new Set<Listener>())
  const [connected, setConnected] = useState(false)
  const [lastEventAt, setLastEventAt] = useState<string | null>(null)

  useEffect(() => {
    let closed = false
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (closed) return
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${protocol}://${window.location.host}/ws`)

      socket.onopen = () => {
        setConnected(true)
      }

      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as RealtimeEvent
          setLastEventAt(event.timestamp)
          listeners.current.forEach((listener) => listener(event))
        } catch {
          // Ignore malformed events.
        }
      }

      socket.onclose = () => {
        setConnected(false)
        if (!closed) {
          reconnectTimer = setTimeout(connect, 2000)
        }
      }

      socket.onerror = () => {
        socket?.close()
      }
    }

    connect()

    return () => {
      closed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [])

  const subscribe = useCallback((listener: Listener) => {
    listeners.current.add(listener)
    return () => {
      listeners.current.delete(listener)
    }
  }, [])

  const value = useMemo(
    () => ({
      connected,
      lastEventAt,
      subscribe,
    }),
    [connected, lastEventAt, subscribe],
  )

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>
}
