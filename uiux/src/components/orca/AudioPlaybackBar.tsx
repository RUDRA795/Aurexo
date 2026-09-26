import React, { useState, useEffect } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Radio,
  Sliders,
  Sparkles,
} from 'lucide-react';

// Exact generated image asset paths
const ASSET_AERIAL = '/src/assets/images/orca_aerial_drone_1790253431565.jpg';
const ASSET_AUV = '/src/assets/images/orca_underwater_auv_1790253447145.jpg';
const ASSET_GLOBE = '/src/assets/images/orca_marine_globe_1790253462650.jpg';

export const AudioPlaybackBar: React.FC = () => {
  const {
    isAudioPlaying,
    toggleAudio,
    setFocusedTarget,
    focusedTarget,
    dayNightMode,
    setDayNightMode,
  } = useOrcaStore();

  const [isPlaying, setIsPlaying] = useState(true);
  const [seconds, setSeconds] = useState(1384); // 23:04 in seconds
  const totalSeconds = 3520; // 58:40

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying) {
      timer = setInterval(() => {
        setSeconds((prev) => (prev >= totalSeconds ? 0 : prev + 1));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPlaying]);

  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center justify-between w-full max-w-4xl mx-auto glass-panel p-2.5 px-4 rounded-2xl border border-cyan-500/30 shadow-[0_12px_40px_rgba(0,0,0,0.8)] backdrop-blur-2xl">
      {/* 1. Glowing Thumbnail Cards (matching Video 1 & 2 "glowing cards, Scenario, Surveillance") */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setFocusedTarget('drone')}
          className={`flex items-center gap-2 p-1.5 pr-3 rounded-xl border transition-all group ${
            focusedTarget === 'drone'
              ? 'bg-cyan-500/25 border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)]'
              : 'bg-slate-900/60 border-slate-700/60 hover:border-cyan-500/40'
          }`}
        >
          <img
            src={ASSET_AERIAL}
            alt="Aerial Drone"
            referrerPolicy="no-referrer"
            className="w-8 h-8 rounded-lg object-cover border border-cyan-400/40"
          />
          <div className="text-left">
            <span className="text-[10px] font-mono uppercase text-cyan-300 block font-bold leading-tight">
              Surveillance
            </span>
            <span className="text-[9px] text-slate-400 font-mono">Aerial Drone</span>
          </div>
        </button>

        <button
          onClick={() => setFocusedTarget('auv')}
          className={`flex items-center gap-2 p-1.5 pr-3 rounded-xl border transition-all group ${
            focusedTarget === 'auv'
              ? 'bg-emerald-500/25 border-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
              : 'bg-slate-900/60 border-slate-700/60 hover:border-emerald-500/40'
          }`}
        >
          <img
            src={ASSET_AUV}
            alt="Underwater Sub"
            referrerPolicy="no-referrer"
            className="w-8 h-8 rounded-lg object-cover border border-emerald-400/40"
          />
          <div className="text-left">
            <span className="text-[10px] font-mono uppercase text-emerald-300 block font-bold leading-tight">
              Scenario
            </span>
            <span className="text-[9px] text-slate-400 font-mono">Sub AUV</span>
          </div>
        </button>

        <button
          onClick={() => setFocusedTarget('center')}
          className={`hidden md:flex items-center gap-2 p-1.5 pr-3 rounded-xl border transition-all group ${
            focusedTarget === 'center'
              ? 'bg-blue-500/25 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]'
              : 'bg-slate-900/60 border-slate-700/60 hover:border-blue-500/40'
          }`}
        >
          <img
            src={ASSET_GLOBE}
            alt="Digital Twin Globe"
            referrerPolicy="no-referrer"
            className="w-8 h-8 rounded-lg object-cover border border-blue-400/40"
          />
          <div className="text-left">
            <span className="text-[10px] font-mono uppercase text-blue-300 block font-bold leading-tight">
              Digital Twin
            </span>
            <span className="text-[9px] text-slate-400 font-mono">Earth Basin</span>
          </div>
        </button>
      </div>

      {/* 2. Simulation Playback Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSeconds((s) => Math.max(0, s - 30))}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors"
          title="Rewind 30s"
        >
          <SkipBack className="w-4 h-4" />
        </button>

        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="p-2.5 rounded-full bg-cyan-400 hover:bg-cyan-300 text-slate-950 shadow-[0_0_20px_rgba(6,182,212,0.4)] transition-transform active:scale-95"
          title={isPlaying ? 'Pause Simulation' : 'Resume Simulation'}
        >
          {isPlaying ? <Pause className="w-4 h-4 fill-slate-950" /> : <Play className="w-4 h-4 fill-slate-950 ml-0.5" />}
        </button>

        <button
          onClick={() => setSeconds((s) => Math.min(totalSeconds, s + 30))}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors"
          title="Forward 30s"
        >
          <SkipForward className="w-4 h-4" />
        </button>

        {/* Time scrubber */}
        <div className="hidden sm:flex items-center gap-2 ml-2 font-mono text-xs text-slate-400">
          <span className="text-cyan-300 tabular-nums">{formatTime(seconds)}</span>
          <div className="w-28 h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
            <div
              className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full transition-all duration-300"
              style={{ width: `${(seconds / totalSeconds) * 100}%` }}
            />
          </div>
          <span className="tabular-nums">{formatTime(totalSeconds)}</span>
        </div>
      </div>

      {/* 3. Ocean Audio Ambience & Lighting Mode */}
      <div className="flex items-center gap-2">
        <button
          onClick={toggleAudio}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-xs font-mono transition-colors ${
            isAudioPlaying
              ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.2)]'
              : 'bg-slate-900/60 border-slate-700/60 text-slate-400 hover:text-white'
          }`}
          title="Synthesize procedural ocean waves sound"
        >
          {isAudioPlaying ? (
            <>
              <Volume2 className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
              <span className="hidden sm:inline">Ocean Waves</span>
            </>
          ) : (
            <>
              <VolumeX className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Muted</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
