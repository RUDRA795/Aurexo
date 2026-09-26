import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Compass,
  ArrowRight,
  ShieldCheck,
  Radio,
  Cpu,
  Layers,
  Waves,
  Navigation,
  Anchor,
  Play
} from 'lucide-react';
import turtleImg from '../../assets/images/sea_turtle_avatar_1790254462691.jpg';
import droneImg from '../../assets/images/aurexo_hero_drone_1790254474498.jpg';

interface Props {
  onComplete: () => void;
}

export const AurexoCinematicSplash: React.FC<Props> = ({ onComplete }) => {
  const [phase, setPhase] = useState<'intro' | 'scanning' | 'ready'>('intro');
  const [progress, setProgress] = useState(0);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    // Phase 1: Turtle swim & ocean caustics (0 - 1.5s)
    // Phase 2: Autonomous telemetry scan & Agentic AI lock (1.5 - 3.2s)
    // Phase 3: Ready to enter command deck
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          setPhase('ready');
          return 100;
        }
        if (prev > 45 && phase === 'intro') {
          setPhase('scanning');
        }
        return prev + 1.25;
      });
    }, 40);

    return () => clearInterval(progressInterval);
  }, [phase]);

  const handleEnter = () => {
    setIsExiting(true);
    setTimeout(() => {
      onComplete();
    }, 700);
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center overflow-hidden transition-all duration-700 ${
        isExiting ? 'opacity-0 scale-105 pointer-events-none' : 'opacity-100 scale-100'
      }`}
      style={{
        background: 'radial-gradient(ellipse at 50% 30%, #e0f2fe 0%, #bae6fd 45%, #7dd3fc 85%, #38bdf8 100%)'
      }}
    >
      {/* Background Volumetric Light Shafts & Sunlit Caustics */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {/* Sun Flare top center */}
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[700px] h-[700px] bg-gradient-to-b from-white/90 via-sky-200/50 to-transparent rounded-full filter blur-3xl opacity-80 animate-pulse duration-1000" />
        
        {/* Volumetric Ray 1 */}
        <div
          className="absolute -top-20 left-1/4 w-32 h-[120vh] bg-gradient-to-b from-white/60 via-cyan-100/20 to-transparent transform -rotate-12 filter blur-xl pointer-events-none"
        />
        {/* Volumetric Ray 2 */}
        <div
          className="absolute -top-20 right-1/4 w-44 h-[120vh] bg-gradient-to-b from-white/50 via-teal-100/20 to-transparent transform rotate-12 filter blur-xl pointer-events-none"
        />

        {/* Ambient Oceanic Grid Overlay */}
        <div
          className="absolute inset-0 opacity-15"
          style={{
            backgroundImage: `radial-gradient(rgba(14, 116, 144, 0.4) 1px, transparent 1px)`,
            backgroundSize: '36px 36px'
          }}
        />
      </div>

      {/* Floating Spatial Telemetry Elements (matching reference video HUD) */}
      <div className="absolute inset-0 pointer-events-none z-10 max-w-6xl mx-auto p-6 md:p-12 flex flex-col justify-between">
        
        {/* Top Header Splash HUD */}
        <div className="flex items-center justify-between">
          <div className="glass-panel-premium px-4 py-2 rounded-2xl flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-500 animate-ping" />
            <span className="font-mono text-xs font-bold text-slate-800 tracking-wider">
              ORCA PROTOCOL // ISRO PS-26176
            </span>
          </div>

          <div className="glass-panel-premium px-4 py-2 rounded-2xl flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span className="font-mono text-xs font-bold text-emerald-800">
              ZERO-HALLUCINATION VERIFICATION GATE
            </span>
          </div>
        </div>

        {/* Floating Spatial Coordinate Pins */}
        <div className="flex justify-between items-center w-full px-4">
          <div className="glass-card-premium p-3 rounded-2xl max-w-[200px] border border-white/80 shadow-xl hidden md:block transform -rotate-2 animate-float-slow">
            <div className="flex items-center gap-2 mb-1">
              <Compass className="w-3.5 h-3.5 text-cyan-600" />
              <span className="text-[10px] font-mono font-bold text-slate-800">INCOIS FEED</span>
            </div>
            <p className="text-[11px] font-mono text-slate-600">PFZ WFS Polygon Active</p>
            <p className="text-[10px] font-mono text-emerald-600 font-bold">15.42°N, 73.41°E</p>
          </div>

          <div className="glass-card-premium p-3 rounded-2xl max-w-[200px] border border-white/80 shadow-xl hidden md:block transform rotate-2 animate-float-slow duration-7000">
            <div className="flex items-center gap-2 mb-1">
              <Radio className="w-3.5 h-3.5 text-teal-600" />
              <span className="text-[10px] font-mono font-bold text-slate-800">COPERNICUS SST</span>
            </div>
            <p className="text-[11px] font-mono text-slate-600">Thermal Front: 28.2°C</p>
            <p className="text-[10px] font-mono text-cyan-700 font-bold">Anomaly: +0.3°C</p>
          </div>
        </div>

        {/* Bottom Status Ticker */}
        <div className="flex items-center justify-between text-xs font-mono text-slate-600">
          <div className="glass-pill-premium px-3.5 py-1.5 rounded-full flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Multi-Agent Swarm Initialized (LangGraph Engine)</span>
          </div>

          <button
            onClick={handleEnter}
            className="glass-pill-premium px-4 py-1.5 rounded-full text-cyan-800 font-bold hover:bg-white transition-all pointer-events-auto cursor-pointer flex items-center gap-1.5"
          >
            <span>Skip Intro</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>

      {/* Center Cinematic Stage Card */}
      <div className="relative z-20 max-w-lg w-full mx-4 flex flex-col items-center text-center">
        
        {/* Realistic Sea Turtle Cinematic Avatar (Hero Presence) */}
        <div className="relative mb-6">
          {/* Animated Caustic Water Halo */}
          <div className="absolute -inset-8 rounded-full bg-gradient-to-tr from-cyan-400/40 via-sky-300/40 to-teal-300/30 filter blur-2xl animate-pulse pointer-events-none" />
          
          {/* Circular Glassmorphism Viewport with Realistic Sea Turtle */}
          <div className="relative w-44 h-44 sm:w-52 sm:h-52 rounded-full p-2.5 glass-card-premium border-2 border-white/90 shadow-[0_20px_60px_rgba(14,165,233,0.35)] flex items-center justify-center animate-turtle">
            
            <div className="relative w-full h-full rounded-full overflow-hidden border border-white/80 shadow-inner">
              <img
                src={turtleImg}
                alt="Realistic Sea Turtle swimming in crystal turquoise water"
                className="w-full h-full object-cover object-center transform hover:scale-105 transition-transform duration-700"
              />
              
              {/* Underwater Caustic Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-cyan-900/30 via-transparent to-white/20 pointer-events-none" />

              {/* Swimming Bubbles */}
              <div className="absolute bottom-2 left-6 w-2 h-2 rounded-full bg-white/70 animate-ping duration-1000" />
              <div className="absolute bottom-5 right-8 w-1.5 h-1.5 rounded-full bg-white/80 animate-ping duration-700" />
            </div>

            {/* Orbiting Acoustic Sonar Wave Rings */}
            <div className="absolute inset-0 rounded-full border border-cyan-400/50 animate-water-ripple pointer-events-none" />
            <div className="absolute -inset-3 rounded-full border border-sky-300/30 animate-water-ripple duration-3000 pointer-events-none" />
          </div>

          {/* Floating "Agentic AI" Micro Badge */}
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 glass-pill-premium px-3.5 py-1 rounded-full border border-cyan-300 shadow-md flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-cyan-600 animate-spin duration-3000" />
            <span className="text-[10px] font-mono font-bold text-slate-800 tracking-wider">
              AUREXO SENTINEL
            </span>
          </div>
        </div>

        {/* Title & Brand Headline */}
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-black text-slate-900 font-display tracking-tight leading-tight mb-2">
          Aurexo
        </h1>

        <p className="text-xs sm:text-sm font-mono text-cyan-900 font-semibold tracking-wide uppercase mb-4">
          Oceanic Ecosystem Reasoning & Multi-Agent Marine Twin
        </p>

        <p className="text-xs sm:text-sm text-slate-600 max-w-sm mx-auto font-sans leading-relaxed mb-6">
          Zero-hallucination spatial intelligence fusing INCOIS satellite telemetry, maritime aerial drones, and benthic submersibles.
        </p>

        {/* Progress Bar & Telemetry Status */}
        <div className="w-full max-w-xs mb-6">
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-700 mb-1.5 font-semibold">
            <span>
              {progress < 40 && 'Syncing INCOIS WFS Services...'}
              {progress >= 40 && progress < 80 && 'Loading Copernicus SST & Bathymetry...'}
              {progress >= 80 && progress < 100 && 'Compiling Verification Consensus...'}
              {progress === 100 && 'Marine Digital Twin Synchronized'}
            </span>
            <span>{Math.round(progress)}%</span>
          </div>

          <div className="w-full h-2 rounded-full bg-white/70 backdrop-blur-md overflow-hidden p-0.5 border border-white/90 shadow-inner">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-sky-500 to-teal-400 transition-all duration-150 shadow-sm"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Enter Command Deck Action Button (Glass Specular Shine) */}
        <button
          onClick={handleEnter}
          className="group relative px-7 py-3.5 rounded-2xl glass-button-specular text-slate-900 font-display font-bold text-sm shadow-[0_12px_30px_rgba(14,165,233,0.3)] hover:shadow-[0_16px_40px_rgba(14,165,233,0.45)] transform hover:-translate-y-0.5 transition-all flex items-center gap-3 cursor-pointer overflow-hidden"
        >
          {/* Specular Shimmer Ray */}
          <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full duration-1000 bg-gradient-to-r from-transparent via-white/70 to-transparent transition-transform pointer-events-none" />

          <Play className="w-4 h-4 text-cyan-600 fill-cyan-600" />
          <span>ENTER COMMAND DECK</span>
          <ArrowRight className="w-4 h-4 text-slate-500 group-hover:translate-x-1 transition-transform" />
        </button>

      </div>

    </div>
  );
};
