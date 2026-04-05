/**
 * WebSocket Context
 *
 * Provides a managed WebSocket connection to the real-time server.
 * Features:
 * - Automatic reconnect with exponential backoff (capped at 30s)
 * - Token-based authentication
 * - Type-safe event subscription / unsubscription
 * - Session subscription helpers
 * - Field lock / unlock helpers for co-editing
 * - Presence / cursor update helpers
 */

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useCallback,
  useState,
  ReactNode,
} from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WsReadyState = 'connecting' | 'open' | 'closed' | 'error'

export interface WsEvent {
  id: string
  type: string
  priority?: string
  data: Record<string, unknown>
  firm_id?: string
  user_id?: string
  session_id?: string
  timestamp: string
  source?: string
}

export type WsEventHandler = (event: WsEvent) => void

export interface WebSocketContextValue {
  /** Current connection state */
  readyState: WsReadyState

  /** Subscribe to events of a specific type. Returns an unsubscribe function. */
  on: (eventType: string, handler: WsEventHandler) => () => void

  /** Subscribe to all events on a return session. */
  subscribeSession: (sessionId: string) => void
  unsubscribeSession: (sessionId: string) => void

  /** Send a field lock request for co-editing. */
  lockField: (sessionId: string, fieldId: string, userName: string) => void
  /** Release a field lock. */
  unlockField: (sessionId: string, fieldId: string) => void

  /** Emit a presence / cursor position update. */
  updatePresence: (sessionId: string, activeField: string | null, userName: string, color?: string) => void

  /** Send a raw JSON message. */
  send: (msg: Record<string, unknown>) => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function useWebSocket(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext)
  if (!ctx) throw new Error('useWebSocket must be used inside <WebSocketProvider>')
  return ctx
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface WebSocketProviderProps {
  /** Auth token passed as ?token= query parameter. If absent, no connection is made. */
  token: string | null
  /** WebSocket URL base, e.g. "ws://localhost:8000/ws". Defaults to auto-detected. */
  url?: string
  children: ReactNode
}

const INITIAL_BACKOFF_MS = 500
const MAX_BACKOFF_MS = 30_000
const BACKOFF_MULTIPLIER = 1.5

function getWsUrl(token: string, customUrl?: string): string {
  if (customUrl) return `${customUrl}?token=${encodeURIComponent(token)}`
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`
}

export function WebSocketProvider({ token, url, children }: WebSocketProviderProps) {
  const [readyState, setReadyState] = useState<WsReadyState>('closed')
  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(INITIAL_BACKOFF_MS)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handlersRef = useRef<Map<string, Set<WsEventHandler>>>(new Map())
  const mountedRef = useRef(true)
  const pendingMessagesRef = useRef<string[]>([])

  // -------------------------------------------------------------------------
  // Connection management
  // -------------------------------------------------------------------------

  const connect = useCallback(() => {
    if (!token || !mountedRef.current) return

    setReadyState('connecting')
    const wsUrl = getWsUrl(token, url)
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      backoffRef.current = INITIAL_BACKOFF_MS
      setReadyState('open')
      // Flush queued messages
      const pending = pendingMessagesRef.current.splice(0)
      for (const msg of pending) ws.send(msg)
    }

    ws.onmessage = (evt) => {
      try {
        const event: WsEvent = JSON.parse(evt.data as string)
        const handlers = handlersRef.current.get(event.type)
        if (handlers) {
          for (const h of handlers) h(event)
        }
        // Wildcard handlers
        const wildcardHandlers = handlersRef.current.get('*')
        if (wildcardHandlers) {
          for (const h of wildcardHandlers) h(event)
        }
      } catch {
        // ignore malformed
      }
    }

    ws.onerror = () => {
      setReadyState('error')
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setReadyState('closed')
      wsRef.current = null
      // Exponential backoff reconnect
      const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS)
      backoffRef.current = Math.floor(backoffRef.current * BACKOFF_MULTIPLIER)
      reconnectTimerRef.current = setTimeout(connect, delay)
    }
  }, [token, url])

  useEffect(() => {
    mountedRef.current = true
    if (token) connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [token, connect])

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  const send = useCallback((msg: Record<string, unknown>) => {
    const json = JSON.stringify(msg)
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(json)
    } else {
      // Queue for delivery after reconnect
      pendingMessagesRef.current.push(json)
    }
  }, [])

  const on = useCallback((eventType: string, handler: WsEventHandler) => {
    if (!handlersRef.current.has(eventType)) {
      handlersRef.current.set(eventType, new Set())
    }
    handlersRef.current.get(eventType)!.add(handler)
    return () => {
      handlersRef.current.get(eventType)?.delete(handler)
    }
  }, [])

  const subscribeSession = useCallback((sessionId: string) => {
    send({ type: 'subscribe', session_id: sessionId })
  }, [send])

  const unsubscribeSession = useCallback((sessionId: string) => {
    send({ type: 'unsubscribe', session_id: sessionId })
  }, [send])

  const lockField = useCallback((sessionId: string, fieldId: string, userName: string) => {
    send({ type: 'field_lock', session_id: sessionId, field_id: fieldId, user_name: userName })
  }, [send])

  const unlockField = useCallback((sessionId: string, fieldId: string) => {
    send({ type: 'field_unlock', session_id: sessionId, field_id: fieldId })
  }, [send])

  const updatePresence = useCallback(
    (sessionId: string, activeField: string | null, userName: string, color?: string) => {
      send({ type: 'presence_update', session_id: sessionId, active_field: activeField, user_name: userName, color })
    },
    [send],
  )

  // -------------------------------------------------------------------------
  // Context value
  // -------------------------------------------------------------------------

  const value: WebSocketContextValue = {
    readyState,
    on,
    subscribeSession,
    unsubscribeSession,
    lockField,
    unlockField,
    updatePresence,
    send,
  }

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>
}

// ---------------------------------------------------------------------------
// Convenience hook: subscribe to a specific event type
// ---------------------------------------------------------------------------

export function useWsEvent(eventType: string, handler: WsEventHandler): void {
  const { on } = useWebSocket()
  useEffect(() => on(eventType, handler), [on, eventType, handler])
}
