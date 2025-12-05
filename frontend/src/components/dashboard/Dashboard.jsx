import React, { useState, useEffect, useMemo } from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import LiveView from '../views/LiveView'
import CommandVisualizer from '../views/CommandVisualizer'
import RecordingsView from '../views/RecordingsView'
import DevicesView from '../views/DevicesView'
import SettingsView from '../views/SettingsView'

/**
 * Dashboard Component
 * 
 * Main application dashboard with:
 * - WebSocket connection management
 * - Multi-page navigation
 * - Real-time signal monitoring
 * - Device and recording management
 * - System settings
 */

export default function Dashboard() {
  // Navigation state
  const [currentPage, setCurrentPage] = useState('live')
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // WebSocket connection
  const {
    status: wsStatus,
    lastMessage,
    latency,
    messageCount,
    connect,
    disconnect,
    send
  } = useWebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8765')

  // Local state
  const [connectionHistory, setConnectionHistory] = useState([])

  /**
   * Track connection status changes
   */
  useEffect(() => {
    setConnectionHistory(prev => [
      ...prev,
      {
        status: wsStatus,
        timestamp: new Date().toLocaleTimeString(),
        latency
      }
    ].slice(-10)) // Keep last 10 events
  }, [wsStatus])

  /**
   * Send test command to backend
   */
  const sendTestCommand = () => {
    send({
      command: 'test',
      timestamp: Date.now(),
      message: 'Hello from React!'
    })
  }

  /**
   * Start data acquisition
   */
  const handleStartAcquisition = () => {
    send({
      command: 'start_acquisition',
      timestamp: Date.now()
    })
  }

  /**
   * Stop data acquisition
   */
  const handleStopAcquisition = () => {
    send({
      command: 'stop_acquisition',
      timestamp: Date.now()
    })
  }

  /**
   * Get connection status color
   */
  const getStatusColor = (status) => {
    switch (status) {
      case 'connected':
        return '#10b981' // green
      case 'connecting':
        return '#f59e0b' // amber
      case 'disconnected':
        return '#ef4444' // red
      case 'error':
        return '#dc2626' // dark red
      default:
        return '#6b7280' // gray
    }
  }

  /**
   * Connection status badge
   */
  const ConnectionStatus = () => (
    <div className="flex items-center gap-3 px-4 py-2 bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Status indicator */}
      <div
        className="w-3 h-3 rounded-full"
        style={{ backgroundColor: getStatusColor(wsStatus) }}
      />

      {/* Status text */}
      <span className="text-sm font-medium text-gray-700 capitalize">
        {wsStatus}
      </span>

      {/* Connection details */}
      {wsStatus === 'connected' && (
        <>
          <div className="h-5 w-px bg-gray-200" />
          <span className="text-xs text-gray-500">
            {latency.toFixed(2)}ms RTT
          </span>
          <span className="text-xs text-gray-500">
            {messageCount} msgs
          </span>
        </>
      )}

      {/* Error retry button */}
      {wsStatus === 'error' && (
        <button
          onClick={connect}
          className="ml-2 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        >
          Retry
        </button>
      )}

      {/* Manual disconnect */}
      {wsStatus === 'connected' && (
        <button
          onClick={disconnect}
          className="ml-auto px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
        >
          Disconnect
        </button>
      )}
    </div>
  )

  /**
   * Connection stats panel
   */
  const ConnectionStats = () => (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {/* Status */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="text-xs font-medium text-gray-500 mb-1">STATUS</div>
        <div className="text-lg font-bold capitalize text-gray-900">
          {wsStatus}
        </div>
      </div>

      {/* Latency */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="text-xs font-medium text-gray-500 mb-1">LATENCY</div>
        <div className="text-lg font-bold text-gray-900">
          {wsStatus === 'connected' ? `${latency.toFixed(1)}ms` : '—'}
        </div>
      </div>

      {/* Message count */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="text-xs font-medium text-gray-500 mb-1">MESSAGES</div>
        <div className="text-lg font-bold text-gray-900">{messageCount}</div>
      </div>

      {/* Last update */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <div className="text-xs font-medium text-gray-500 mb-1">LAST UPDATE</div>
        <div className="text-lg font-bold text-gray-900">
          {lastMessage
            ? new Date(lastMessage.timestamp).toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
              })
            : '—'}
        </div>
      </div>
    </div>
  )

  /**
   * Control panel for acquisition
   */
  const ControlPanel = () => (
    <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Acquisition Controls</h3>

      <div className="space-y-4">
        {/* Buttons */}
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleStartAcquisition}
            disabled={wsStatus !== 'connected'}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            ▶ Start Acquisition
          </button>

          <button
            onClick={handleStopAcquisition}
            disabled={wsStatus !== 'connected'}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            ⏹ Stop Acquisition
          </button>

          <button
            onClick={sendTestCommand}
            disabled={wsStatus !== 'connected'}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            🧪 Test Command
          </button>
        </div>

        {/* Status info */}
        <div className="text-sm text-gray-600">
          {wsStatus === 'connected' ? (
            <p>✓ Connected to EMG pipeline at ws://localhost:8765</p>
          ) : wsStatus === 'connecting' ? (
            <p>⏳ Connecting to backend...</p>
          ) : (
            <p>✗ Not connected. {wsStatus === 'error' && 'Retrying...'}</p>
          )}
        </div>
      </div>
    </div>
  )

  /**
   * Connection history
   */
  const ConnectionHistory = () => (
    <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Connection History</h3>

      <div className="space-y-2 text-sm">
        {connectionHistory.length === 0 ? (
          <p className="text-gray-500">No connection events yet</p>
        ) : (
          connectionHistory
            .slice()
            .reverse()
            .map((event, idx) => (
              <div
                key={idx}
                className="flex justify-between items-center py-2 px-3 bg-gray-50 rounded border border-gray-100"
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: getStatusColor(event.status) }}
                  />
                  <span className="font-medium text-gray-700 capitalize">
                    {event.status}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  {event.latency > 0 && (
                    <span className="text-gray-500">{event.latency.toFixed(1)}ms</span>
                  )}
                  <span className="text-gray-400 text-xs">{event.timestamp}</span>
                </div>
              </div>
            ))
        )}
      </div>
    </div>
  )

  /**
   * Page content router
   */
  const renderPageContent = () => {
    switch (currentPage) {
      case 'live':
        return (
          <div className="space-y-6">
            <ConnectionStats />
            <ControlPanel />
            {wsStatus === 'connected' && lastMessage && (
              <LiveView wsData={lastMessage.data} />
            )}
            {wsStatus !== 'connected' && (
              <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500 border border-gray-200">
                <p className="text-lg font-medium mb-2">Waiting for connection...</p>
                <p className="text-sm">
                  {wsStatus === 'error'
                    ? 'Connection failed. Retrying...'
                    : 'Connecting to EMG pipeline'}
                </p>
              </div>
            )}
          </div>
        )

      case 'devices':
        return <DevicesView wsStatus={wsStatus} />

      case 'recordings':
        return <RecordingsView />

      case 'settings':
        return <SettingsView />

      default:
        return <div>Page not found</div>
    }
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      {sidebarOpen && <Sidebar currentPage={currentPage} setCurrentPage={setCurrentPage} />}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <Topbar
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          connectionStatus={<ConnectionStatus />}
        />

        {/* Page content */}
        <main className="flex-1 overflow-auto bg-gray-100">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {renderPageContent()}
          </div>

          {/* Connection history (bottom right, always visible in development) */}
          {process.env.NODE_ENV === 'development' && (
            <div className="fixed bottom-4 right-4 w-80 bg-white rounded-lg shadow-lg border border-gray-200 max-h-48 overflow-auto">
              <div className="p-4">
                <ConnectionHistory />
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
