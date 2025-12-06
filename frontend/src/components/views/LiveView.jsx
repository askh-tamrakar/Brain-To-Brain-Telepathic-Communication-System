import React, { useState, useEffect, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'

/**
 * LiveView (Python-WS streaming) with multi-channel EEG support.
 * - EEG buffer is stored per-channel: eegByChannel = { 0: [{time,value}, ...], 1: [...] }
 * - UI: Single-channel (choose index) or Overlay all channels
 */

export default function LiveView({ wsData }) {
  // per-channel buffers for EEG, single buffers for EOG/EMG
  const [eegByChannel, setEegByChannel] = useState({}) // {chIndex: [{time,value}, ...]}
  const [eogData, setEogData] = useState([])
  const [emgData, setEmgData] = useState([])

  // UI controls
  const [timeWindowMs, setTimeWindowMs] = useState(10000) // 10s
  const [isPaused, setIsPaused] = useState(false)
  const [displayMode, setDisplayMode] = useState('single') // 'single' | 'overlay'
  const [selectedChannel, setSelectedChannel] = useState(0)

  // limits
  const MAX_POINTS_PER_MESSAGE = 120
  const MAX_POINTS_PER_CHANNEL = 50000

  // helper to push per-channel and trim by time window
  const pushChannelPoints = (chIdx, pts) => {
    setEegByChannel(prev => {
      const current = prev[chIdx] ?? []
      const merged = [...current, ...pts]
      const lastTs = merged.length ? merged[merged.length - 1].time : Date.now()
      const cutoff = lastTs - timeWindowMs
      const trimmed = merged.filter(p => p.time >= cutoff)
      if (trimmed.length > MAX_POINTS_PER_CHANNEL) return { ...prev, [chIdx]: trimmed.slice(-MAX_POINTS_PER_CHANNEL) }
      return { ...prev, [chIdx]: trimmed }
    })
  }

  const pushSingleByTimeWindow = (setter, pts) => {
    setter(prev => {
      if (!pts || pts.length === 0) return prev
      const merged = [...prev, ...pts]
      const lastTs = merged.length ? merged[merged.length - 1].time : Date.now()
      const cutoff = lastTs - timeWindowMs
      const sliced = merged.filter(p => p.time >= cutoff)
      if (sliced.length > MAX_POINTS_PER_CHANNEL) return sliced.slice(-MAX_POINTS_PER_CHANNEL)
      return sliced
    })
  }

  // compute known EEG channel count from buffer keys
  const knownEegChannels = useMemo(() => {
    return Object.keys(eegByChannel).map(k => Number(k)).sort((a, b) => a - b)
  }, [eegByChannel])

  useEffect(() => {
    if (!wsData || isPaused) return

    let payload = null
    try {
      const jsonText = typeof wsData === 'string' ? wsData : (wsData.data ?? null)
      if (!jsonText) return
      payload = JSON.parse(jsonText)
    } catch (err) {
      console.error('LiveView: failed to parse wsData', err, wsData)
      return
    }

    if (!payload || !payload.window || !Array.isArray(payload.window)) return
    const source = (payload.source || '').toUpperCase()
    const fs = Number(payload.fs) || 250
    const endTs = Number(payload.timestamp) || Date.now()
    const channels = payload.window
    const nChannels = channels.length
    const samples = Array.isArray(channels[0]) ? channels[0] : []
    const n = samples.length
    if (n === 0) return

    // limit points per message
    const stride = Math.max(1, Math.floor(n / MAX_POINTS_PER_MESSAGE))

    // Build per-sample timestamps (common for all channels)
    // sample i offset from end: (i - (n - 1))*(1000/fs)
    const timestamps = []
    for (let i = 0; i < n; i += stride) {
      const offsetMs = Math.round((i - (n - 1)) * (1000 / fs))
      timestamps.push(endTs + offsetMs)
    }

    // For EEG (multi-channel), create points per channel and push to per-channel buffers
    if (source === 'EEG' || nChannels >= 8) {
      // ensure we handle all channels even if some are missing
      for (let ch = 0; ch < nChannels; ch++) {
        const chSamples = Array.isArray(channels[ch]) ? channels[ch] : []
        if (!chSamples || chSamples.length === 0) continue
        const pts = []
        for (let i = 0, idx = 0; i < chSamples.length; i += stride, idx++) {
          const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)))
          const v = Number(chSamples[i])
          pts.push({ time: t, value: Number.isFinite(v) ? v : 0 })
        }
        pushChannelPoints(ch, pts)
      }
    } else {
      // non-EEG: pick first channel only
      const samples0 = samples
      const pts = []
      for (let i = 0, idx = 0; i < samples0.length; i += stride, idx++) {
        const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)))
        const v = Number(samples0[i])
        pts.push({ time: t, value: Number.isFinite(v) ? v : 0 })
      }

      if (source === 'EOG') pushSingleByTimeWindow(setEogData, pts)
      else if (source === 'EMG') pushSingleByTimeWindow(setEmgData, pts)
      else {
        // heuristics: if 2 channels try EOG, else EMG fallback
        if (nChannels === 2) pushSingleByTimeWindow(setEogData, pts)
        else pushSingleByTimeWindow(setEmgData, pts)
      }
    }
  }, [wsData, isPaused, timeWindowMs]) // eslint-disable-line react-hooks/exhaustive-deps

  // Select data to pass to SignalChart for EEG:
  // - single mode: pass selected channel's array as `data`
  // - overlay mode: pass entire eegByChannel as `byChannel`
  const eegChartProp = useMemo(() => {
    if (displayMode === 'overlay') {
      return { byChannel: eegByChannel }
    } else {
      // ensure selectedChannel exists; if not, pick lowest existing
      const ch = Number(selectedChannel)
      if (eegByChannel[ch]) return { data: eegByChannel[ch] }
      const keys = Object.keys(eegByChannel)
      if (keys.length === 0) return { data: [] }
      const fallback = Number(keys[0])
      return { data: eegByChannel[fallback] ?? [] }
    }
  }, [displayMode, selectedChannel, eegByChannel])

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex gap-3 items-center flex-wrap">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className={`px-6 py-3 rounded-xl font-bold transition-all shadow-glow ${isPaused
                  ? 'bg-accent text-primary-contrast hover:opacity-90'
                  : 'bg-primary text-primary-contrast hover:opacity-90'
                }`}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>

            <label className="text-sm font-bold text-text">Time window:</label>
            <select
              value={timeWindowMs}
              onChange={(e) => setTimeWindowMs(Number(e.target.value))}
              className="px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 outline-none"
            >
              <option value={5000}>5 s</option>
              <option value={10000}>10 s</option>
              <option value={30000}>30 s</option>
              <option value={60000}>60 s</option>
            </select>
          </div>

          <div className="flex gap-6 items-center flex-wrap">
            <div className="flex items-center gap-3">
              <label className="text-sm font-bold text-text">EEG Display:</label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="displayMode"
                  value="single"
                  checked={displayMode === 'single'}
                  onChange={() => setDisplayMode('single')}
                  className="w-5 h-5 text-primary"
                />
                <span className="text-sm font-medium text-text">Single</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="displayMode"
                  value="overlay"
                  checked={displayMode === 'overlay'}
                  onChange={() => setDisplayMode('overlay')}
                  className="w-5 h-5 text-primary"
                />
                <span className="text-sm font-medium text-text">Overlay all</span>
              </label>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-sm font-bold text-text">Channel:</label>
              <select
                value={selectedChannel}
                onChange={(e) => setSelectedChannel(Number(e.target.value))}
                className="px-3 py-2 bg-bg border border-border text-text rounded-lg outline-none"
                disabled={displayMode === 'overlay'}
              >
                {knownEegChannels.length === 0 && <option value={0}>0</option>}
                {knownEegChannels.map(ch => (
                  <option key={ch} value={ch}>Ch {ch}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      <SignalChart
        title="EEG - Brain Waves"
        color="#3b82f6"
        timeWindowMs={timeWindowMs}
        {...eegChartProp}
        channelLabelPrefix="Ch"
      />

      <SignalChart title="EOG - Eye Movement" data={eogData} color="#10b981" timeWindowMs={timeWindowMs} />
      <SignalChart title="EMG - Muscle Activity" data={emgData} color="#f59e0b" timeWindowMs={timeWindowMs} />
    </div>
  )
}
