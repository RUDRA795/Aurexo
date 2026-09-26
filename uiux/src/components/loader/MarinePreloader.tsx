import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Compass, Waves, Sparkles, ShieldCheck } from 'lucide-react';

const MARINE_QUOTES = [
  "“Listening to the living pulse of the oceans with collaborative AI agents.”",
  "“Earth Observation satellite telemetry: SST, Chlorophyll-a & Ocean State Forecasts synced.”",
  "“Safeguarding coastal fishermen with deterministic geofencing and zero hallucinations.”",
  "“Reasoning across 4,000+ ARGO floats, INCOIS WFS, and Copernicus Marine layers.”",
];

export const MarinePreloader: React.FC<{ onComplete?: () => void }> = ({ onComplete }) => {
  const [progress, setProgress] = useState(0);
  const [isFinished, setIsFinished] = useState(false);
  const [quoteIndex, setQuoteIndex] = useState(0);

  useEffect(() => {
    // Dynamic progressive counter
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          setTimeout(() => {
            setIsFinished(true);
            if (onComplete) onComplete();
          }, 350);
          return 100;
        }
        const diff = Math.floor(Math.random() * 8) + 4;
        return Math.min(100, prev + diff);
      });
    }, 60);

    // Rotate quotes smoothly
    const quoteTimer = setInterval(() => {
      setQuoteIndex((prev) => (prev + 1) % MARINE_QUOTES.length);
    }, 1800);

    return () => {
      clearInterval(timer);
      clearInterval(quoteTimer);
    };
  }, [onComplete]);

  return (
    <AnimatePresence>
      {!isFinished && (
        <motion.div
          key="marine-preloader"
          initial={{ opacity: 1 }}
          exit={{
            opacity: 0,
            scale: 1.04,
            transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] },
          }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#05111A] text-white selection:bg-transparent overflow-hidden"
        >
          {/* Bioluminescent Ocean Ambient Glow Blobs */}
          <div className="absolute w-[500px] h-[500px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none animate-pulse" />
          <div className="absolute w-[350px] h-[350px] bg-teal-500/10 rounded-full blur-[100px] pointer-events-none -bottom-10 -right-10" />

          <div className="relative z-10 flex flex-col items-center max-w-lg px-6 text-center">
            
            {/* Animated Oceanic Compass Emblem */}
            <div className="relative w-28 h-28 mb-8">
              <svg viewBox="0 0 100 100" className="w-full h-full drop-shadow-[0_0_25px_rgba(6,182,212,0.45)]">
                {/* Outer Ring */}
                <circle
                  cx="50"
                  cy="50"
                  r="45"
                  fill="none"
                  stroke="rgba(6, 182, 212, 0.2)"
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                />
                {/* Animated Progressive Marine Path */}
                <motion.path
                  d="M50 10 L58 42 L90 50 L58 58 L50 90 L42 58 L10 50 L42 42 Z"
                  fill="none"
                  stroke="url(#oceanPreloaderGrad)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: progress / 100 }}
                  transition={{ duration: 0.25, ease: 'easeOut' }}
                />
                {/* Wave Crest in the Center */}
                <motion.path
                  d="M35 52 Q 42 46, 50 52 T 65 52"
                  fill="none"
                  stroke="#22D3EE"
                  strokeWidth="2"
                  strokeLinecap="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: progress / 100 }}
                />
                <defs>
                  <linearGradient id="oceanPreloaderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#22D3EE" />
                    <stop offset="50%" stopColor="#06B6D4" />
                    <stop offset="100%" stopColor="#10B981" />
                  </linearGradient>
                </defs>
              </svg>

              {/* Pulsing center beacon */}
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
              </div>
            </div>

            {/* Tagline */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-cyan-950/70 border border-cyan-400/30 text-[11px] font-mono tracking-widest text-cyan-300 uppercase mb-4 shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>ISRO PS 26176 • ORCA MARINE TWIN</span>
            </motion.div>

            {/* Title */}
            <h1 className="text-2xl sm:text-3xl font-black font-display tracking-tight text-white mb-2">
              Aurexo <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400">Marine Intelligence</span>
            </h1>

            {/* Rotating Inspirational Quote */}
            <div className="h-12 flex items-center justify-center mb-6">
              <motion.p
                key={quoteIndex}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.5 }}
                className="text-xs sm:text-sm font-sans text-slate-300 font-light italic max-w-md leading-relaxed"
              >
                {MARINE_QUOTES[quoteIndex]}
              </motion.p>
            </div>

            {/* Glowing Gradient Progress Bar */}
            <div className="w-64 h-1.5 bg-ocean-900/90 rounded-full overflow-hidden p-0.5 border border-cyan-500/30 mb-3 shadow-[0_0_15px_rgba(6,182,212,0.25)]">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-500 via-teal-400 to-emerald-400 rounded-full"
                style={{ width: `${progress}%` }}
                transition={{ ease: 'easeOut' }}
              />
            </div>

            {/* Status & Percentage */}
            <div className="w-64 flex items-center justify-between text-[11px] font-mono text-slate-400">
              <span className="flex items-center gap-1 text-cyan-400">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span>{progress < 40 ? 'Calibrating Sensors' : progress < 80 ? 'Fetching Satellite SST' : 'Agents Ready'}</span>
              </span>
              <span className="text-cyan-300 font-bold tracking-wider">{progress}%</span>
            </div>

          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
