import React, { useState } from 'react'

export default function DevicesView() {
  const [selectedSensors, setSelectedSensors] = useState(['EEG', 'EOG', 'EMG'])
  const [samplingRate, setSamplingRate] = useState(250)
  const [filterLow, setFilterLow] = useState(1)
  const [filterHigh, setFilterHigh] = useState(45)
  const [testStatus, setTestStatus] = useState(null)

  const toggleSensor = (sensor) => {
    if (selectedSensors.includes(sensor)) {
      setSelectedSensors(prev => prev.filter(s => s !== sensor))
    } else {
      setSelectedSensors(prev => [...prev, sensor])
    }
  }

  const testStream = () => {
    setTestStatus('testing')
    setTimeout(() => {
      setTestStatus('success')
      setTimeout(() => setTestStatus(null), 3000)
    }, 2000)
  }

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h2 className="text-2xl font-bold text-text mb-6 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          Device Configuration
        </h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-bold text-text mb-3">Sensor Selection</label>
            <div className="flex gap-4">
              {['EEG', 'EOG', 'EMG'].map(sensor => (
                <label key={sensor} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={selectedSensors.includes(sensor)}
                    onChange={() => toggleSensor(sensor)}
                    className="w-6 h-6 text-primary rounded-lg focus:ring-2 focus:ring-primary/50 border-border bg-bg"
                  />
                  <span className="font-bold text-text group-hover:text-primary transition-colors">{sensor}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-bold text-text mb-3">Sampling Rate (Hz)</label>
            <select
              value={samplingRate}
              onChange={(e) => setSamplingRate(Number(e.target.value))}
              className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
            >
              <option value={125}>125 Hz</option>
              <option value={250}>250 Hz</option>
              <option value={500}>500 Hz</option>
              <option value={1000}>1000 Hz</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-bold text-text mb-3">High-pass Filter (Hz)</label>
              <input
                type="number"
                value={filterLow}
                onChange={(e) => setFilterLow(Number(e.target.value))}
                className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                min="0.1"
                step="0.1"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-text mb-3">Low-pass Filter (Hz)</label>
              <input
                type="number"
                value={filterHigh}
                onChange={(e) => setFilterHigh(Number(e.target.value))}
                className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                min="1"
                step="1"
              />
            </div>
          </div>

          <button
            onClick={testStream}
            disabled={testStatus === 'testing'}
            className={`w-full py-4 rounded-xl font-bold text-lg transition-all shadow-glow ${testStatus === 'testing'
                ? 'bg-accent text-primary-contrast cursor-wait animate-pulse'
                : testStatus === 'success'
                  ? 'bg-accent text-primary-contrast'
                  : 'bg-primary text-primary-contrast hover:opacity-90 hover:translate-y-[-2px] active:translate-y-[0px]'
              }`}
          >
            {testStatus === 'testing' && '🧪 Testing Stream...'}
            {testStatus === 'success' && '✅ Test Successful!'}
            {!testStatus && '🧪 Test Stream'}
          </button>
        </div>
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">Current Configuration</h3>
        <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-5 space-y-3 border border-border">
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Active Sensors:</span>
            <span className="font-bold text-text">{selectedSensors.join(', ') || 'None'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Sampling Rate:</span>
            <span className="font-bold text-text">{samplingRate} Hz</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Filter Range:</span>
            <span className="font-bold text-text">{filterLow} - {filterHigh} Hz</span>
          </div>
        </div>
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">Saved Profiles</h3>
        <div className="flex flex-col items-center justify-center py-12 text-muted space-y-3">
          <div className="w-16 h-16 rounded-full bg-bg border border-border flex items-center justify-center">
            <span className="text-2xl">📋</span>
          </div>
          <p>No saved device profiles. Configure and save a profile above.</p>
        </div>
      </div>
    </div>
  )
}
