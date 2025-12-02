import React, { useState, useEffect } from 'react'

export default function CommandVisualizer({ wsData }) {
  const [commands, setCommands] = useState([])
  const [liveText, setLiveText] = useState('')
  const [activeKey, setActiveKey] = useState(null)

  const keyboard = [
    ['A', 'B', 'C', 'D', 'E'],
    ['F', 'G', 'H', 'I', 'J'],
    ['K', 'L', 'M', 'N', 'O'],
    ['P', 'Q', 'R', 'S', 'T'],
    ['U', 'V', 'W', 'X', 'Y', 'Z']
  ]

  useEffect(() => {
    if (!wsData) return

    try {
      const parsed = JSON.parse(wsData.data)
      if (parsed.type !== 'command') return

      const cmd = { ...parsed, id: Date.now() }
      setCommands(prev => [cmd, ...prev].slice(0, 20))

      setActiveKey(parsed.command)
      setTimeout(() => setActiveKey(null), 300)

      if (parsed.command === 'ENTER') {
        // Trigger enter animation
      } else if (parsed.command === 'BACKSPACE') {
        setLiveText(prev => prev.slice(0, -1))
      } else {
        setLiveText(prev => prev + parsed.command)
      }
    } catch (e) {
      console.error('Command parse error:', e)
    }
  }, [wsData])

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h2 className="text-2xl font-bold text-text mb-6 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          Command Recognition
        </h2>

        <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-5 mb-6 border border-border">
          <div className="text-sm text-muted mb-3 font-medium">Live Text Preview:</div>
          <div className="text-2xl font-mono min-h-[4rem] bg-surface rounded-lg p-4 border border-border text-text">
            {liveText || <span className="text-muted/50">Waiting for input...</span>}
          </div>
        </div>

        <div className="space-y-3 mb-6">
          {keyboard.map((row, i) => (
            <div key={i} className="flex justify-center gap-2">
              {row.map(key => (
                <div
                  key={key}
                  className={`command-key w-14 h-14 flex items-center justify-center rounded-xl border-2 font-bold text-lg transition-all duration-200
                    ${activeKey === key
                      ? 'bg-primary border-primary text-primary-contrast scale-110 shadow-glow'
                      : 'border-border bg-surface text-text hover:border-primary/50'}`}
                >
                  {key}
                </div>
              ))}
            </div>
          ))}
          <div className="flex justify-center gap-3 mt-6">
            <div
              className={`command-key px-8 h-14 flex items-center justify-center rounded-xl border-2 font-bold transition-all duration-200
                ${activeKey === 'BACKSPACE'
                  ? 'bg-primary border-primary text-primary-contrast scale-110 shadow-glow'
                  : 'border-border bg-surface text-text hover:border-primary/50'}`}
            >
              ⌫ BACK
            </div>
            <div
              className={`command-key px-12 h-14 flex items-center justify-center rounded-xl border-2 font-bold transition-all duration-200
                ${activeKey === 'ENTER'
                  ? 'bg-accent border-accent text-primary-contrast scale-110 shadow-glow'
                  : 'border-border bg-surface text-text hover:border-accent/50'}`}
            >
              ↵ ENTER
            </div>
          </div>
        </div>
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">Command Timeline</h3>
        <div className="space-y-2 max-h-80 overflow-y-auto scrollbar-hide">
          {commands.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted space-y-3">
              <div className="w-16 h-16 rounded-full bg-bg border border-border flex items-center justify-center">
                <span className="text-2xl">⌨️</span>
              </div>
              <p>Waiting for recognized commands...</p>
            </div>
          ) : (
            commands.map(cmd => (
              <div key={cmd.id} className="flex items-center justify-between p-4 bg-bg rounded-xl border border-border hover:border-primary/50 transition-all">
                <div className="flex items-center gap-4">
                  <span className="text-3xl font-bold text-primary">{cmd.command}</span>
                  <span className="text-sm text-muted">
                    {new Date(cmd.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-sm font-bold text-accent">
                  {(cmd.confidence * 100).toFixed(1)}%
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
