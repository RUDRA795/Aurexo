import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { OceanCanvas } from '../ocean/OceanCanvas';
import { MarineGlobe } from '../map/MarineGlobe';
import { OrcaTimeline } from './OrcaTimeline';
import { MarineDataCards } from './MarineDataCards';
import { AudioPlaybackBar } from './AudioPlaybackBar';
import { OrcaAvatar } from './OrcaAvatar';
import { OrcaChatHud } from './OrcaChatHud';
import { OrcaEvidence } from './OrcaEvidence';
import { OrcaVerification } from './OrcaVerification';
import { OrcaProvenance } from './OrcaProvenance';
import { OrcaEcosystemView } from './OrcaEcosystemView';
import { OrcaSurveillanceView } from './OrcaSurveillanceView';
import { BackendSettingsModal } from './BackendSettingsModal';
import {
  Sun,
  Moon,
  MessageSquare,
  Search,
  Server,
  Activity,
  Layers,
  Compass,
} from 'lucide-react';

export const OrcaCommandCenter: React.FC = () => {
  const {
    activeTab,
    setActiveTab,
    isConnected,
    connectionMode,
    dayNightMode,
    setDayNightMode,
    isChatOpen,
    setIsChatOpen,
    agentStatus,
    isRunning,
  } = useOrcaStore();

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsChatOpen(true);
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#030914] text-slate-100 flex flex-col font-sans select-none">
      {/* 1. Persistent 3D Procedural Ocean Canvas (Underlying living environment) */}
      <OceanCanvas />

      {/* 2. Top Navigation Bar (Strict 3-Zone Contract) */}
      <header className="relative z-30 flex items-center justify-between px-6 py-3.5 border-b border-cyan-500/15 glass-panel backdrop-blur-xl">
        {/* Zone 1: Single text element wordmark */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.3)]">
            <span className="w-3.5 h-3.5 rotate-45 bg-cyan-400 rounded-sm" />
          </div>
          <span className="text-lg font-display font-extrabold tracking-wider text-white">
            ORCA
          </span>
          <span className="hidden sm:inline text-xs font-mono text-cyan-400/80 border-l border-white/10 pl-3">
            Marine Intelligence
          </span>
        </div>

        {/* Zone 2: 4-5 clean text navigation links */}
        <nav className="hidden md:flex items-center gap-7 text-sm font-medium">
          <button
            onClick={() => setActiveTab('command')}
            className={`transition-colors relative py-1 ${
              activeTab === 'command'
                ? 'text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Dashboard
            {activeTab === 'command' && (
              <span className="absolute -bottom-3.5 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('ecosystem')}
            className={`transition-colors relative py-1 ${
              activeTab === 'ecosystem'
                ? 'text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Ecosystem
            {activeTab === 'ecosystem' && (
              <span className="absolute -bottom-3.5 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('surveillance')}
            className={`transition-colors relative py-1 ${
              activeTab === 'surveillance'
                ? 'text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Surveillance
            {activeTab === 'surveillance' && (
              <span className="absolute -bottom-3.5 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('evidence')}
            className={`transition-colors relative py-1 ${
              activeTab === 'evidence'
                ? 'text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Evidence
            {activeTab === 'evidence' && (
              <span className="absolute -bottom-3.5 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('verification')}
            className={`transition-colors relative py-1 ${
              activeTab === 'verification'
                ? 'text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Verification
            {activeTab === 'verification' && (
              <span className="absolute -bottom-3.5 left-0 right-0 h-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            )}
          </button>
        </nav>

        {/* Zone 3: 1-2 primary actions */}
        <div className="flex items-center gap-3">
          {/* Quick Search */}
          <form onSubmit={handleSearchSubmit} className="hidden lg:flex items-center relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search marine layers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-900/60 border border-slate-700/60 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono w-44"
            />
          </form>

          {/* Backend Connection Status Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-mono transition-colors ${
              isConnected
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                : 'bg-amber-950/40 border-amber-500/40 text-amber-300'
            }`}
            title="Configure FastAPI Backend URL"
          >
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
            <span className="hidden sm:inline">
              {isConnected ? 'FASTAPI LIVE' : 'SANDBOX SIM'}
            </span>
          </button>

          {/* Atmosphere Lighting Toggle */}
          <button
            onClick={() => setDayNightMode(dayNightMode === 'night' ? 'day' : 'night')}
            className="p-2 rounded-xl glass-panel text-slate-300 hover:text-white transition-colors"
            title="Toggle Atmosphere Lighting"
          >
            {dayNightMode === 'night' ? (
              <Sun className="w-4 h-4 text-amber-300" />
            ) : (
              <Moon className="w-4 h-4 text-cyan-300" />
            )}
          </button>

          {/* Chat Launcher shortcut */}
          <button
            onClick={() => setIsChatOpen(!isChatOpen)}
            className="px-3.5 py-1.5 text-xs font-bold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded-xl transition-all shadow-[0_0_15px_rgba(6,182,212,0.4)] flex items-center gap-1.5"
          >
            <MessageSquare className="w-3.5 h-3.5 fill-slate-950" />
            <span>ORCA AI</span>
          </button>
        </div>
      </header>

      {/* 3. Main Center Workspace */}
      <main className="relative z-10 flex-1 flex flex-col overflow-hidden p-4 md:p-6 pb-20">
        {activeTab === 'command' && (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 h-full min-h-0">
            {/* Left Column: AI Agent Timeline & Fleet HUD */}
            <div className="lg:col-span-3 h-full min-h-[300px]">
              <OrcaTimeline />
            </div>

            {/* Center Column: 3D Digital Twin Globe & Spatial Map */}
            <div className="lg:col-span-6 h-full min-h-[400px] glass-panel rounded-2xl border border-cyan-500/20 shadow-2xl overflow-hidden relative">
              <MarineGlobe />
            </div>

            {/* Right Column: Marine Telemetry & Scenario Lab */}
            <div className="lg:col-span-3 h-full min-h-[300px]">
              <MarineDataCards />
            </div>
          </div>
        )}

        {activeTab === 'ecosystem' && <OrcaEcosystemView />}

        {activeTab === 'surveillance' && <OrcaSurveillanceView />}

        {activeTab === 'evidence' && (
          <div className="flex-1 max-w-5xl mx-auto w-full h-full">
            <OrcaEvidence />
          </div>
        )}

        {activeTab === 'verification' && (
          <div className="flex-1 max-w-6xl mx-auto w-full h-full grid grid-cols-1 lg:grid-cols-2 gap-4">
            <OrcaVerification />
            <OrcaProvenance />
          </div>
        )}
      </main>

      {/* 4. Bottom Simulation / Audio Control Bar */}
      <div className="fixed bottom-4 left-6 right-6 z-20 pointer-events-auto">
        <AudioPlaybackBar />
      </div>

      {/* 5. Persistent Draggable AI Assistant Avatar (Bottom Right) */}
      <OrcaAvatar />

      {/* 6. Expandable AI Chat HUD */}
      <OrcaChatHud />

      {/* 7. Backend Settings & URL Modal */}
      <BackendSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
};
