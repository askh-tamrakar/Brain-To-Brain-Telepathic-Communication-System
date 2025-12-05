import { useState, useEffect, useRef } from 'react'

/**
 * useWebSocket Hook
 * 
 * Manages WebSocket connection with EMG pipeline backend
 * Features:
 * - Auto-reconnect on disconnect
 * - Ping/pong latency measurement
 * - Message buffering
 * - Error handling
 * 
 * Usage:
 * const { status, lastMessage, latency, connect, disconnect, send } = useWebSocket('ws://localhost:8765')
 * 
 * Status: 'disconnected' | 'connecting' | 'connected' | 'error'
 * LastMessage: { data: string, timestamp: number }
 * Latency: number (milliseconds)
 */

const PING_INTERVAL = 1000 // 1 second between pings
const RECONNECT_INTERVAL = 3000 // 3 seconds between reconnect attempts
const MAX_RECONNECT_ATTEMPTS = 5

export function useWebSocket(url, autoConnect = true) {
  // Connection state
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [latency, setLatency] = useState(0)
  const [messageCount, setMessageCount] = useState(0)

  // Refs
  const wsRef = useRef(null)
  const pingTimerRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const pendingPingsRef = useRef(new Map())

  /**
   * Connect to WebSocket server
   */
  const connect = () => {
    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected')
      return
    }

    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket connection in progress')
      return
    }

    console.log(`[WebSocket] Connecting to ${url}...`)
    setStatus('connecting')

    try {
      wsRef.current = new WebSocket(url)

      /**
       * Connection opened
       */
      wsRef.current.onopen = () => {
        console.log('[WebSocket] ✓ Connected')
        setStatus('connected')
        reconnectAttemptsRef.current = 0 // Reset reconnect counter

        // Start ping/pong for latency measurement
        startPingLoop()
      }

      /**
       * Message received
       */
      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)

          // Handle pong response
          if (msg.type === 'pong') {
            const pendingPing = pendingPingsRef.current.get(msg.id)
            if (pendingPing) {
              const rtt = performance.now() - pendingPing.t0
              setLatency(parseFloat(rtt.toFixed(2)))
              pendingPingsRef.current.delete(msg.id)
            }
            return
          }

          // Handle regular data message
          setLastMessage({
            data: event.data,
            timestamp: Date.now(),
            parsed: msg
          })
          setMessageCount(prev => prev + 1)
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err)
        }
      }

      /**
       * Connection error
       */
      wsRef.current.onerror = (error) => {
        console.error('[WebSocket] ✗ Error:', error)
        setStatus('error')
      }

      /**
       * Connection closed
       */
      wsRef.current.onclose = () => {
        console.log('[WebSocket] Disconnected')
        setStatus('disconnected')
        stopPingLoop()

        // Attempt to reconnect
        if (autoConnect && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1
          console.log(
            `[WebSocket] Reconnecting... (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
          )

          reconnectTimerRef.current = setTimeout(() => {
            connect()
          }, RECONNECT_INTERVAL)
        } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          console.error('[WebSocket] Max reconnect attempts reached')
          setStatus('error')
        }
      }
    } catch (err) {
      console.error('[WebSocket] Failed to create WebSocket:', err)
      setStatus('error')
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  const disconnect = () => {
    console.log('[WebSocket] Disconnecting...')
    stopPingLoop()
    clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
  }

  /**
   * Send a message to WebSocket server
   */
  const send = (data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        const message = typeof data === 'string' ? data : JSON.stringify(data)
        wsRef.current.send(message)
      } catch (err) {
        console.error('[WebSocket] Failed to send message:', err)
      }
    } else {
      console.warn('[WebSocket] Cannot send - not connected')
    }
  }

  /**
   * Start sending ping messages for latency measurement
   */
  const startPingLoop = () => {
    stopPingLoop() // Clear existing timer

    pingTimerRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const id = Math.random().toString(36).slice(2, 10)
        const t0 = performance.now()

        // Store pending ping
        pendingPingsRef.current.set(id, { t0 })

        // Send ping
        try {
          wsRef.current.send(
            JSON.stringify({
              type: 'ping',
              id,
              t0
            })
          )
        } catch (err) {
          console.error('[WebSocket] Failed to send ping:', err)
        }

        // Clean up old pings (older than 5 seconds)
        const now = performance.now()
        for (const [pingId, pingData] of pendingPingsRef.current.entries()) {
          if (now - pingData.t0 > 5000) {
            pendingPingsRef.current.delete(pingId)
          }
        }
      }
    }, PING_INTERVAL)
  }

  /**
   * Stop sending ping messages
   */
  const stopPingLoop = () => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current)
      pingTimerRef.current = null
    }
    pendingPingsRef.current.clear()
  }

  /**
   * Auto-connect on mount if enabled
   */
  useEffect(() => {
    if (autoConnect) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [url, autoConnect])

  return {
    // State
    status,
    lastMessage,
    latency,
    messageCount,

    // Connection control
    connect,
    disconnect,

    // Communication
    send,

    // Raw WebSocket (for advanced use)
    ws: wsRef.current
  }
}

/**
 * Hook variants for specific use cases
 */

/**
 * useWebSocketWithReconnect - Custom reconnect policy
 */
export function useWebSocketWithReconnect(
  url,
  {
    autoConnect = true,
    maxAttempts = 10,
    retryDelay = 2000,
    onConnect = null,
    onDisconnect = null,
    onError = null
  } = {}
) {
  const hook = useWebSocket(url, false)
  const retriesRef = useRef(0)
  const reconnectTimerRef = useRef(null)

  const customConnect = () => {
    hook.connect()
    onConnect?.()
  }

  const customDisconnect = () => {
    hook.disconnect()
    clearTimeout(reconnectTimerRef.current)
    onDisconnect?.()
  }

  useEffect(() => {
    if (hook.status === 'error' && autoConnect && retriesRef.current < maxAttempts) {
      retriesRef.current += 1
      console.log(`Retrying connection (${retriesRef.current}/${maxAttempts})...`)

      reconnectTimerRef.current = setTimeout(() => {
        customConnect()
      }, retryDelay)
    } else if (hook.status === 'connected') {
      retriesRef.current = 0
    }
  }, [hook.status])

  useEffect(() => {
    if (autoConnect) {
      customConnect()
    }

    return () => {
      customDisconnect()
    }
  }, [])

  return {
    ...hook,
    connect: customConnect,
    disconnect: customDisconnect,
    retries: retriesRef.current
  }
}

/**
 * useWebSocketData - Simplified hook for just getting data
 */
export function useWebSocketData(url) {
  const [data, setData] = useState([])
  const { lastMessage, status } = useWebSocket(url)

  useEffect(() => {
    if (lastMessage?.parsed) {
      setData(prev => [...prev, lastMessage.parsed])
    }
  }, [lastMessage])

  return { data, status }
}
