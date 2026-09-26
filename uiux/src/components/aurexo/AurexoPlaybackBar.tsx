import React, { useState, useEffect } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  FastForward,
  Clock,
  Radio,
  Sliders,
  Volume2
} from 'lucide-react';

export const AurexoPlaybackBar: React.FC = () => {
  const { isRunning, focusedTarget, setFocusedTarget } = useOrcaStore();
  const [isPlaying, setIsPlaying] = useState(true);
  const [timelineSec, setTimelineSec] = useState(42);

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setTimelineSec((sec) => (sec + 1) % 180);
    }, 1000);
    return () => clearInterval(interval);
  }, [isPlaying]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `14:32:${secs < 10 ? '0' : ''}${secs} UTC`;
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 max-w-xl w-[92%] sm:w-auto">
      <div className="glass-panel-ocean px-4 py-2.5 rounded-full border border-cyan-500/30 shadow-2xl flex items-center justify-between gap-4">
        
        {/* Playback Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTimelineSec(0)}
            title="Jump to Start"
            className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-ocean-900/60 transition-colors cursor-pointer"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setTimelineSec((s) => Math.max(0, s - 10))}
            title="Rewind 10s"
            className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-ocean-900/60 transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            title={isPlaying ? 'Pause Simulation' : 'Play Simulation'}
            className="p-2 rounded-full bg-cyan-500 text-ocean-950 shadow-md shadow-cyan-500/30 hover:bg-cyan-400 transition-all scale-105 active:scale-95 cursor-pointer"
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
          </button>

          <button
            onClick={() => setTimelineSec((s) => Math.min(180, s + 10))}
            title="Fast Forward 10s"
            className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-ocean-900/60 transition-colors cursor-pointer"
          >
            <FastForward className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setTimelineSec(180)}
            title="Jump to Live"
            className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-ocean-900/60 transition-colors cursor-pointer"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Timecode Indicator */}
        <div className="hidden sm:flex items-center gap-1.5 text-xs font-mono font-bold text-cyan-200 border-l border-cyan-500/20 pl-3">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>{formatTime(timelineSec)}</span>
        </div>

        {/* Mission Timeline Mini Scrubber */}
        <div className="w-20 sm:w-28 flex items-center">
          <input
            type="range"
            min="0"
            max="180"
            value={timelineSec}
            onChange={(e) => setTimelineSec(Number(e.target.value))}
            className="w-full h-1 bg-ocean-900 rounded-lg appearance-none cursor-pointer accent-cyan-400"
          />
        </div>

        {/* Craft Focus Quick Toggle */}
        <div className="hidden md:flex items-center gap-1 border-l border-cyan-500/20 pl-3">
          <button
            onClick={() => setFocusedTarget('drone')}
            className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
              focusedTarget === 'drone'
                ? 'bg-cyan-500 text-ocean-950 shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Aero-01
          </button>
          <button
            onClick={() => setFocusedTarget('auv')}
            className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold transition-all cursor-pointer ${
              focusedTarget === 'auv'
                ? 'bg-teal-400 text-ocean-950 shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Sub-04
          </button>
        </div>

      </div>
    </div>
  );
};
