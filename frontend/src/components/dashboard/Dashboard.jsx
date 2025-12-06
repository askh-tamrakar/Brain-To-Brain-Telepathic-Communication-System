import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import LiveView from '../views/LiveView'
import CommandVisualizer from '../views/CommandVisualizer'
import RecordingsView from '../views/RecordingsView'
import DevicesView from '../views/DevicesView'
import ChatView from '../views/ChatView'
import MockView from '../views/MockView'
import SettingsView from '../views/SettingsView'
import TestView from '../views/TestView'

import '../../styles/App.css';
import themePresets from '../themes/presets';
import ScrollStack, { ScrollStackItem } from '../ui/ScrollStack';
import PillNav from '../ui/PillNav';
import Pill from '../ui/Pill';

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [currentPage, setCurrentPage] = useState('live')
  // const [sidebarOpen, setSidebarOpen] = useState(true)
  const { status, lastMessage, latency, connect, disconnect } = useWebSocket(
    import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
  )
  const [theme, setTheme] = React.useState(() => localStorage.getItem('theme') || 'theme-violet');
  const [navColors, setNavColors] = React.useState({ base: '#000000', pill: '#ffffff', pillText: '#000000', hoverText: '#ffffff' });
  const [authView, setAuthView] = useState(null);
  const isAuthenticated = !!user;

  // Theme management
  React.useEffect(() => {
    const root = document.documentElement;
    const existing = Array.from(root.classList).filter(c => c.startsWith('theme-'));
    if (existing.length) root.classList.remove(...existing);
    root.classList.add(theme);
    localStorage.setItem('theme', theme);

    const cs = getComputedStyle(root);
    const accent = cs.getPropertyValue('--accent').trim() || '#121212';
    const text = cs.getPropertyValue('--text').trim() || '#ffffff';
    setNavColors({ base: accent, pill: text, pillText: accent, hoverText: text });
  }, [theme]);

  // Pill size calculation
  const [pillSize, setPillSize] = React.useState({ width: 0, height: 0 });
  React.useEffect(() => {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    context.font = '16px Inter, sans-serif';

    let maxWidth = 0;
    themePresets.forEach(p => {
      const metrics = context.measureText(p.label);
      const w = metrics.width;
      if (w > maxWidth) maxWidth = w;
    });

    const paddedWidth = Math.ceil(maxWidth + 60);
    setPillSize({ width: paddedWidth, height: 40 });
  }, []);

  useEffect(() => {
    connect()
  }, [])

  const handleSignupSuccess = () => {
    setAuthView(null);
  };

  const handleLoginSuccess = () => {
    setAuthView(null);
  };

  return (
    <div className="app-root">
      {/* Navigation */}
      <div className="topbar">
        <div className="topbar-inner container">
          <div className="brand">
            <video muted autoPlay loop playsInline preload="auto" aria-label="logo animation">
              <source src="/Resources/Encryption.mp4" type="video/mp4" />
            </video>
            <div className="title">
              NeuroKeys
            </div>
          </div>

          <nav className="nav">
            <div className="pill-nav" style={{ background: 'transparent', border: 'none', boxShadow: 'none', padding: 0 }}>
              <PillNav
                items={[
                  { label: 'Live', onClick: () => setCurrentPage('live'), href: '#live' },
                  { label: 'Commands', onClick: () => setCurrentPage('commands'), href: '#commands' },
                  { label: 'Recordings', onClick: () => setCurrentPage('recordings'), href: '#recordings' },
                  { label: 'Devices', onClick: () => setCurrentPage('devices'), href: '#devices' },
                  { label: 'Chat', onClick: () => setCurrentPage('chat'), href: '#chat' },
                  { label: 'Settings', onClick: () => setCurrentPage('settings'), href: '#settings' },
                  { label: 'Test', onClick: () => setCurrentPage('test'), href: '#test' },
                  {
                    label: 'Theme',
                    type: 'pill',
                    key: 'theme-dropdown',
                    menu: ({ close }) => (
                      <ScrollStack>
                        {themePresets.map((p) => (
                          <ScrollStackItem key={p.value}>
                            <Pill
                              label={p.label}
                              pillHeight={42}
                              pillWidth={pillSize.width}
                              active={theme === p.value}
                              onClick={() => {
                                setTheme(p.value);
                                close?.();
                              }}
                              baseColor={p.accent}
                              pillColor={p.text}
                              hoveredTextColor={p.text}
                              pillTextColor={p.accent}
                            />
                          </ScrollStackItem>
                        ))}
                      </ScrollStack>
                    )
                  }
                ]}
                activeHref={`#${currentPage}`}
                className="custom-nav"
                ease="power2.easeOut"
                baseColor={navColors.base}
                pillColor={navColors.pill}
                hoveredPillTextColor={navColors.hoverText}
                pillTextColor={navColors.pillText}
              />
            </div>
          </nav>

          <button
            className="btn-encrypting"
            onClick={() => document.getElementById('encrypt-card')?.scrollIntoView({ behavior: 'smooth' })}
          >
            Connect
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="container" style={{ flex: 1, padding: '24px 0', overflowY: 'auto' }}>
        {currentPage === 'live' && <LiveView wsData={lastMessage} />}
        {currentPage === 'commands' && <CommandVisualizer wsData={lastMessage} />}
        {currentPage === 'recordings' && <RecordingsView />}
        {currentPage === 'devices' && <DevicesView />}
        {currentPage === 'chat' && <ChatView wsData={lastMessage} />}
        {currentPage === 'mock' && <MockView />}
        {currentPage === 'settings' && <SettingsView />}
        {currentPage === 'test' && <TestView />}
      </div>

      {/* Footer */}
      <div className="footer">
        NeuroKeys: BCI Typing Project •{' '}
        <a onClick={() => setAuthView('signup')} className="muted" href="#signup" rel="noreferrer">
          Sign Up
        </a>
        {' '} •{' '}
        <a
          className="muted"
          href="https://github.com/askh-tamrakar/NeuroKeys-BCI_Typing_Project"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </div>
    </div>
  );
}