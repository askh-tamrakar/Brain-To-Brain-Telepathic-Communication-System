import React, { useEffect, useRef, useState } from 'react'
import LiveView from './LiveView'
import { MockWebSocket } from '../../services/MockWebSocket'

const USE_MOCK = true
const WS_URL = 'ws://localhost:8000/ws'

export default function TestView() {
  const [wsData, setWsData] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    const ws = USE_MOCK ? new MockWebSocket(WS_URL) : new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => console.log('WS open')
    ws.onmessage = (evt) => {
      // The MockWebSocket sends { data: JSON.stringify(...) } just like a real WebSocket MessageEvent
      // but some mocks may send objects directly. Handle both.
      try {
        if (typeof evt.data === 'string') {
          setWsData({ data: evt.data }) // keep as MessageEvent-like so LiveView.parse handles it
        } else if (evt.data && typeof evt.data === 'object') {
          // sometimes mock already sends object
          setWsData(evt.data)
        } else {
          // fallback: try to stringify and save
          setWsData({ data: JSON.stringify(evt) })
        }
      } catch (e) {
        console.error('App onmessage parse error', e, evt)
      }
    }
    ws.onerror = (e) => console.error('WS error', e)
    ws.onclose = () => console.log('WS closed')

    return () => { if (ws && ws.close) ws.close() }
  }, [])

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h1 className="text-3xl font-bold text-text mb-2 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          Test LiveView
        </h1>
        <p className="text-muted">Testing live signal visualization with mock data</p>
      </div>
      <LiveView wsData={wsData} />
    </div>
  )
}
