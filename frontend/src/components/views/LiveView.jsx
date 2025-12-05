import React, { useState, useEffect, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'

/**
 * LiveView Component
 * Receives WebSocket data from RUN_EMG.py pipeline
 * Handles EEG (multi-channel), EOG (single), and EMG (single/dual) signals
 * 
 * Expected WebSocket message format:
 * {
 *   "source": "EMG" | "EEG" | "EOG",
 *   "timestamp": 1234567890123,
 *   "fs": 512.0,
 *   "window": [[ch0_samples], [ch1_samples], ...]
 * }
 */
export default function LiveView({ wsData }) {
  // Per-channel buffers
  const [eegByChannel, setEegByChannel] = useState({}) // {chIndex: [{time,value}, ...]}
  const [eogData, setEogData] = useState([])
  const [emgData, setEmgData] = useState([])
  const [emgCh1Data, setEmgCh1Data] = useState([]) // Second EMG channel (if present)

  // UI controls
  const [timeWindowMs, setTimeWindowMs] = useState(10000) // 10s default
  const [isPaused, setIsPaused] = useState(false)
  const [displayMode, setDisplayMode] = useState('single') // 'single' | 'overlay'
  const [selectedChannel, setSelectedChannel] = useState(0)
  const [dataSource, setDataSource] = useState('') // Track signal source type

  // Limits
  const MAX_POINTS_PER_MESSAGE = 120
  const MAX_POINTS_PER_CHANNEL = 50000

  /**
   * Push channel points with time window filtering
   */
  const pushChannelPoints = (chIdx, pts) => {
    setEegByChannel(prev => {
      const current = prev[chIdx] ?? []
      const merged = [...current, ...pts]
      const lastTs = merged.length ? merged[merged.length - 1].time : Date.now()
      const cutoff = lastTs - timeWindowMs
      const trimmed = merged.filter(p => p.time >= cutoff)
      if (trimmed.length > MAX_POINTS_PER_CHANNEL) {
        return { ...prev, [chIdx]: trimmed.slice(-MAX_POINTS_PER_CHANNEL) }
      }
      return { ...prev, [chIdx]: trimmed }
    })
  }

  /**
   * Push single signal points with time window filtering
   */
  const pushSingleByTimeWindow = (setter, pts) => {
    setter(prev => {
      if (!pts || pts.length === 0) return prev
      const merged = [...prev, ...pts]
      const lastTs = merged.length ? merged[merged.length - 1].time : Date.now()
      const cutoff = lastTs - timeWindowMs
      const sliced = merged.filter(p => p.time >= cutoff)
      if (sliced.length > MAX_POINTS_PER_CHANNEL) {
        return sliced.slice(-MAX_POINTS_PER_CHANNEL)
      }
      return sliced
    })
  }

  /**
   * Get known EEG channels from buffer keys
   */
  const knownEegChannels = useMemo(() => {
    return Object.keys(eegByChannel)
      .map(k => Number(k))
      .sort((a, b) => a - b)
  }, [eegByChannel])

  /**
   * Main WebSocket data processing
   */
  useEffect(() => {
    if (!wsData || isPaused) return

    let payload = null
    try {
      const jsonText = typeof wsData === 'string' ? wsData : wsData.data ?? null
      if (!jsonText) return
      payload = JSON.parse(jsonText)
    } catch (err) {
      console.error('LiveView: failed to parse wsData', err, wsData)
      return
    }

    if (!payload || !payload.window || !Array.isArray(payload.window)) return

    const source = (payload.source || '').toUpperCase()
    const fs = Number(payload.fs) || 512
    const endTs = Number(payload.timestamp) || Date.now()
    const channels = payload.window
    const nChannels = channels.length

    // Handle empty channels
    if (nChannels === 0) return

    // Get first channel samples (reference for timing)
    const samples = Array.isArray(channels[0]) ? channels[0] : []
    const n = samples.length

    if (n === 0) return

    // Track source type for UI
    if (source !== dataSource) {
      setDataSource(source)
    }

    // Limit points per message to maintain performance
    const stride = Math.max(1, Math.floor(n / MAX_POINTS_PER_MESSAGE))

    // Build per-sample timestamps (common for all channels)
    // Sample i at index (i - (n-1)) represents: endTs + (i - (n-1))*(1000/fs) ms
    const timestamps = []
    for (let i = 0; i < n; i += stride) {
      const offsetMs = Math.round((i - (n - 1)) * (1000 / fs))
      timestamps.push(endTs + offsetMs)
    }

    /**
     * MULTI-CHANNEL SIGNALS (EEG)
     * For EEG or signals with 8+ channels, display per-channel
     */
    if (source === 'EEG' || nChannels >= 8) {
      for (let ch = 0; ch < nChannels; ch++) {
        const chSamples = Array.isArray(channels[ch]) ? channels[ch] : []
        if (!chSamples || chSamples.length === 0) continue

        const pts = []
        for (let i = 0, idx = 0; i < chSamples.length; i += stride, idx++) {
          const t = timestamps[idx] ?? endTs - Math.round((n - 1 - i) * (1000 / fs))
          const v = Number(chSamples[i])
          pts.push({ time: t, value: Number.isFinite(v) ? v : 0 })
        }
        pushChannelPoints(ch, pts)
      }
    }
    /**
     * DUAL-CHANNEL SIGNALS (EMG - 2 channels)
     * Flexor (ch0) and Extensor (ch1)
     */
    else if (source === 'EMG' && nChannels === 2) {
      // Process both channels
      const pts0 = []
      const pts1 = []

      const samples0 = Array.isArray(channels[0]) ? channels[0] : []
      const samples1 = Array.isArray(channels[1]) ? channels[1] : []

      for (let i = 0, idx = 0; i < n; i += stride, idx++) {
        const t = timestamps[idx] ?? endTs - Math.round((n - 1 - i) * (1000 / fs))

        if (i < samples0.length) {
          const v0 = Number(samples0[i])
          pts0.push({ time: t, value: Number.isFinite(v0) ? v0 : 0 })
        }

        if (i < samples1.length) {
          const v1 = Number(samples1[i])
          pts1.push({ time: t, value: Number.isFinite(v1) ? v1 : 0 })
        }
      }

      pushSingleByTimeWindow(setEmgData, pts0)
      pushSingleByTimeWindow(setEmgCh1Data, pts1)
    }
    /**
     * SINGLE-CHANNEL SIGNALS
     * EOG or EMG (single channel), or generic single-channel
     */
    else {
      const samples0 = Array.isArray(channels[0]) ? channels[0] : []
      const pts = []

      for (let i = 0, idx = 0; i < samples0.length; i += stride, idx++) {
        const t = timestamps[idx] ?? endTs - Math.round((n - 1 - i) * (1000 / fs))
        const v = Number(samples0[i])
        pts.push({ time: t, value: Number.isFinite(v) ? v : 0 })
      }

      // Route to appropriate signal type
      if (source === 'EOG') {
        pushSingleByTimeWindow(setEogData, pts)
      } else if (source === 'EMG') {
        pushSingleByTimeWindow(setEmgData, pts)
      } else {
        // Heuristic fallback: treat 2 channels as EOG, else EMG
        if (nChannels === 2) {
          pushSingleByTimeWindow(setEogData, pts)
        } else {
          pushSingleByTimeWindow(setEmgData, pts)
        }
      }
    }
  }, [wsData, isPaused, timeWindowMs]) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Select EEG data to display
   * Single mode: show selected channel only
   * Overlay mode: show all channels
   */
  const eegChartProp = useMemo(() => {
    if (displayMode === 'overlay') {
      return { byChannel: eegByChannel }
    } else {
      const ch = Number(selectedChannel)
      if (eegByChannel[ch]) return { data: eegByChannel[ch] }
      const keys = Object.keys(eegByChannel)
      if (keys.length === 0) return { data: [] }
      const fallback = Number(keys[0])
      return { data: eegByChannel[fallback] ?? [] }
    }
  }, [displayMode, selectedChannel, eegByChannel])

  return (
    <div className="space-y-4 p-4">
      {/* Control Panel */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Pause/Resume & Time Window */}
          <div className="flex gap-3 items-center flex-wrap">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                isPaused
                  ? 'bg-green-600 hover:bg-green-700'
                  : 'bg-yellow-600 hover:bg-yellow-700'
              } text-white`}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>

            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">Time window:</label>
              <select
                value={timeWindowMs}
                onChange={e => setTimeWindowMs(Number(e.target.value))}
                className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm focus:ring-2 focus:ring-blue-500"
              >
                <option value={5000}>5 s</option>
                <option value={10000}>10 s</option>
                <option value={30000}>30 s</option>
                <option value={60000}>60 s</option>
              </select>
            </div>

            {/* Data source indicator */}
            {dataSource && (
              <div className="text-sm font-semibold px-3 py-1 bg-blue-100 text-blue-800 rounded-lg">
                {dataSource}
              </div>
            )}
          </div>

          {/* Display mode for EEG */}
          {Object.keys(eegByChannel).length > 0 && (
            <div className="flex gap-4 items-center">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-gray-700">Display:</span>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="displayMode"
                    value="single"
                    checked={displayMode === 'single'}
                    onChange={() => setDisplayMode('single')}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">Single</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="displayMode"
                    value="overlay"
                    checked={displayMode === 'overlay'}
                    onChange={() => setDisplayMode('overlay')}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">Overlay</span>
                </label>
              </div>

              {displayMode === 'single' && (
                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium text-gray-700">Channel:</label>
                  <select
                    value={selectedChannel}
                    onChange={e => setSelectedChannel(Number(e.target.value))}
                    className="px-3 py-1 border border-gray-300 rounded bg-white text-sm focus:ring-2 focus:ring-blue-500"
                  >
                    {knownEegChannels.length === 0 && <option value={0}>0</option>}
                    {knownEegChannels.map(ch => (
                      <option key={ch} value={ch}>
                        Ch {ch}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Signal Charts */}
      <div className="space-y-6">
        {/* EEG Chart - Only show if data exists */}
        {Object.keys(eegByChannel).length > 0 && (
          <SignalChart
            title="EEG - Brain Waves (Multi-channel)"
            color="#3b82f6"
            timeWindowMs={timeWindowMs}
            {...eegChartProp}
            channelLabelPrefix="Ch"
          />
        )}

        {/* EMG Chart - Primary channel (Flexor) */}
        {emgData.length > 0 && (
          <SignalChart
            title="EMG - Flexor (Channel 0)"
            data={emgData}
            color="#f59e0b"
            timeWindowMs={timeWindowMs}
          />
        )}

        {/* EMG Chart - Secondary channel (Extensor) */}
        {emgCh1Data.length > 0 && (
          <SignalChart
            title="EMG - Extensor (Channel 1)"
            data={emgCh1Data}
            color="#ef4444"
            timeWindowMs={timeWindowMs}
          />
        )}

        {/* EOG Chart */}
        {eogData.length > 0 && (
          <SignalChart
            title="EOG - Eye Movement"
            data={eogData}
            color="#10b981"
            timeWindowMs={timeWindowMs}
          />
        )}

        {/* No data message */}
        {emgData.length === 0 && eogData.length === 0 && Object.keys(eegByChannel).length === 0 && (
          <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
            <p className="text-lg font-medium">Waiting for WebSocket data...</p>
            <p className="text-sm mt-2">Connect to ws://localhost:8765</p>
          </div>
        )}
      </div>
    </div>
  )
}
