import React from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import LiveView from '../views/LiveView'

/**
 * Simplified Dashboard - Works with Tailwind
 * Use this if the full Dashboard is showing white
 */

export default function Dashboard() {
  const {
    status: wsStatus,
    lastMessage,
    latency,
    messageCount,
    send
  } = useWebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8765//ws')

  const handleStartAcquisition = () => {
    send({
      command: 'start_acquisition',
      timestamp: Date.now()
    })
  }

  const handleStopAcquisition = () => {
    send({
      command: 'stop_acquisition',
      timestamp: Date.now()
    })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">EMG Signal Monitor</h1>
            
            {/* Connection Status */}
            <div className="flex items-center gap-3 px-4 py-2 bg-gray-100 rounded-lg">
              <div
                className={`w-3 h-3 rounded-full ${
                  wsStatus === 'connected'
                    ? 'bg-green-500'
                    : wsStatus === 'connecting'
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
              />
              <span className="text-sm font-medium text-gray-700 capitalize">
                {wsStatus}
              </span>
              {wsStatus === 'connected' && (
                <>
                  <span className="text-xs text-gray-500">{latency.toFixed(1)}ms</span>
                  <span className="text-xs text-gray-500">{messageCount} msgs</span>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          {/* Connection Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-xs font-medium text-gray-500 uppercase">Status</div>
              <div className="text-2xl font-bold text-gray-900 capitalize mt-1">
                {wsStatus}
              </div>
            </div>

            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-xs font-medium text-gray-500 uppercase">Latency</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">
                {wsStatus === 'connected' ? `${latency.toFixed(1)}ms` : '—'}
              </div>
            </div>

            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-xs font-medium text-gray-500 uppercase">Messages</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">{messageCount}</div>
            </div>

            <div className="bg-white rounded-lg p-4 shadow">
              <div className="text-xs font-medium text-gray-500 uppercase">Last Update</div>
              <div className="text-lg font-bold text-gray-900 mt-1">
                {lastMessage
                  ? new Date(lastMessage.timestamp).toLocaleTimeString('en-US', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit'
                    })
                  : '—'}
              </div>
            </div>
          </div>

          {/* Control Panel */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Acquisition Controls</h2>
            
            <div className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleStartAcquisition}
                  disabled={wsStatus !== 'connected'}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  ▶ Start Acquisition
                </button>

                <button
                  onClick={handleStopAcquisition}
                  disabled={wsStatus !== 'connected'}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  ⏹ Stop Acquisition
                </button>
              </div>

              <div className="text-sm text-gray-600">
                {wsStatus === 'connected' ? (
                  <p>✓ Connected to EMG pipeline</p>
                ) : wsStatus === 'connecting' ? (
                  <p>⏳ Connecting...</p>
                ) : (
                  <p>✗ Not connected {wsStatus === 'error' && '(Retrying...)'}</p>
                )}
              </div>
            </div>
          </div>

          {/* LiveView */}
          {wsStatus === 'connected' && lastMessage ? (
            <div className="bg-white rounded-lg shadow p-6">
              <LiveView wsData={lastMessage.data} />
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <p className="text-gray-500 text-lg">
                {wsStatus === 'connecting' 
                  ? '⏳ Connecting to backend...' 
                  : '✗ Waiting for connection...'}
              </p>
              <p className="text-gray-400 text-sm mt-2">
                Start backend with: python RUN_EMG.py
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
