/**
 * useTaxCalcWebSocket
 *
 * Dedicated hook for the /ws/tax-calc/{sessionId} WebSocket.
 * Handles:
 * - Connection lifecycle with exponential backoff reconnect
 * - 500 ms debounced sends (matches server debounce requirement)
 * - Incoming result and error handling
 */

import { useRef, useEffect, useCallback, useState } from 'react'

export interface TaxCalcInput {
  income: {
    wages?: number
    interest_income?: number
    dividend_income?: number
    capital_gains?: number
    business_income?: number
    rental_income?: number
    other_income?: number
  }
  withholdings?: {
    federal?: number
  }
  filing_status?: string
  num_dependents?: number
  state_code?: string
}

export interface TaxCalcResult {
  tax_liability: number
  refund_or_owed: number
  is_refund: boolean
  federal_tax: number
  state_tax: number
  effective_rate: number
  marginal_rate: number
  confidence: number
}

interface UseTaxCalcWebSocketOptions {
  sessionId: string
  token: string | null
  onResult: (result: TaxCalcResult, requestId?: string) => void
  onError?: (error: string, requestId?: string) => void
  debounceMs?: number
}

const INITIAL_BACKOFF_MS = 500
const MAX_BACKOFF_MS = 30_000
const BACKOFF_MULTIPLIER = 1.5

export function useTaxCalcWebSocket({
  sessionId,
  token,
  onResult,
  onError,
  debounceMs = 500,
}: UseTaxCalcWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingInputRef = useRef<TaxCalcInput | null>(null)
  const pendingRequestIdRef = useRef<string | null>(null)
  const backoffRef = useRef(INITIAL_BACKOFF_MS)
  const mountedRef = useRef(true)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [connected, setConnected] = useState(false)

  const getUrl = useCallback(() => {
    if (!token || !sessionId) return null
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/tax-calc/${encodeURIComponent(sessionId)}?token=${encodeURIComponent(token)}`
  }, [token, sessionId])

  const flushPending = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    if (!pendingInputRef.current) return
    wsRef.current.send(
      JSON.stringify({
        type: 'calc_update',
        request_id: pendingRequestIdRef.current,
        ...pendingInputRef.current,
      }),
    )
    pendingInputRef.current = null
    pendingRequestIdRef.current = null
  }, [])

  const connect = useCallback(() => {
    const wsUrl = getUrl()
    if (!wsUrl || !mountedRef.current) return

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      backoffRef.current = INITIAL_BACKOFF_MS
      setConnected(true)
      flushPending()
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string)
        if (msg.type === 'tax_calc_result') {
          onResult(msg.data as TaxCalcResult, msg.data?.request_id)
        } else if (msg.type === 'tax_calc_error') {
          onError?.(msg.error as string, msg.request_id)
        }
      } catch {
        // ignore
      }
    }

    ws.onerror = () => {
      // onclose will trigger reconnect
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setConnected(false)
      wsRef.current = null
      const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS)
      backoffRef.current = Math.floor(backoffRef.current * BACKOFF_MULTIPLIER)
      reconnectTimerRef.current = setTimeout(connect, delay)
    }
  }, [getUrl, flushPending, onResult, onError])

  useEffect(() => {
    mountedRef.current = true
    if (token && sessionId) connect()
    return () => {
      mountedRef.current = false
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [token, sessionId, connect])

  /**
   * Debounced send — queues the latest input and flushes after debounceMs.
   * If the WebSocket is not yet connected, the input is held until connected.
   */
  const sendCalcUpdate = useCallback(
    (input: TaxCalcInput) => {
      const requestId = `req-${Date.now()}`
      pendingInputRef.current = input
      pendingRequestIdRef.current = requestId

      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = setTimeout(() => {
        flushPending()
      }, debounceMs)
    },
    [flushPending, debounceMs],
  )

  return { sendCalcUpdate, connected }
}
