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
    let reconnectDelayMs = 2000

    const scheduleReconnect = () => {
      if (closed) return
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(connect, reconnectDelayMs)
      reconnectDelayMs = Math.min(reconnectDelayMs * 1.5, 15000)
    }

    const backendReachable = async () => {
      try {
        const response = await fetch('/api/health', { cache: 'no-store' })
        return response.ok
      } catch {
        return false
      }
    }

    const connect = async () => {
      if (closed) return
      const reachable = await backendReachable()
      if (!reachable) {
        setConnected(false)
        scheduleReconnect()
        return
      }
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${protocol}://${window.location.host}/ws`)

      socket.onopen = () => {
        setConnected(true)
        reconnectDelayMs = 2000
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
        scheduleReconnect()
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
