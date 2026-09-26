import React, { useState, useRef, useEffect } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { Activity, ShieldCheck, Sparkles, Waves, Compass, BrainCircuit, Maximize2 } from 'lucide-react';
import seaTurtleImg from '../../assets/images/sea_turtle_avatar_1790254462691.jpg';

export const SeaTurtleAvatar: React.FC = () => {
  const {
    agentStatus,
    activeTool,
    isChatOpen,
    setIsChatOpen,
    avatarPosition,
    setAvatarPosition,
    verification,
  } = useOrcaStore();

  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const avatarRef = useRef<HTMLDivElement>(null);

  // Status mapping for the sea turtle guardian
  const getStatusDetails = () => {
    switch (agentStatus) {
      case 'planning':
        return { label: 'Reasoning Route', color: 'from-amber-400 to-amber-600', ring: 'ring-amber-400', badge: 'bg-amber-500/10 text-amber-700 border-amber-300' };
      case 'querying_pfz':
        return { label: 'PFZ Sonar Scan', color: 'from-cyan-500 to-blue-600', ring: 'ring-cyan-400', badge: 'bg-cyan-500/10 text-cyan-700 border-cyan-300' };
      case 'retrieving_sst':
        return { label: 'Thermal Analysis', color: 'from-sky-400 to-indigo-600', ring: 'ring-sky-400', badge: 'bg-sky-500/10 text-sky-700 border-sky-300' };
      case 'checking_weather':
        return { label: 'Met-Ocean Swell', color: 'from-teal-400 to-emerald-600', ring: 'ring-teal-400', badge: 'bg-teal-500/10 text-teal-700 border-teal-300' };
      case 'retrieving_chlorophyll':
        return { label: 'Bio-Chlorophyll', color: 'from-emerald-400 to-green-600', ring: 'ring-emerald-400', badge: 'bg-emerald-500/10 text-emerald-700 border-emerald-300' };
      case 'searching_advisories':
        return { label: 'Knowledge Graph', color: 'from-violet-400 to-purple-600', ring: 'ring-violet-400', badge: 'bg-violet-500/10 text-violet-700 border-violet-300' };
      case 'verifying':
        return { label: 'Cross-Consensus', color: 'from-blue-500 to-indigo-600', ring: 'ring-blue-400', badge: 'bg-blue-500/10 text-blue-700 border-blue-300' };
      case 'complete':
        return { label: 'Verified Complete', color: 'from-emerald-400 to-teal-600', ring: 'ring-emerald-400', badge: 'bg-emerald-500/10 text-emerald-700 border-emerald-300' };
      case 'error':
        return { label: 'Sensory Anomaly', color: 'from-rose-400 to-red-600', ring: 'ring-rose-400', badge: 'bg-rose-500/10 text-rose-700 border-rose-300' };
      default:
        return { label: 'Aurexo Sentinel', color: 'from-cyan-400 to-teal-500', ring: 'ring-cyan-300', badge: 'bg-sky-500/10 text-sky-700 border-sky-200' };
    }
  };

  const status = getStatusDetails();

  // Drag physics & containment
  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag with left click
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragOffset({
      x: e.clientX - avatarPosition.x,
      y: e.clientY - avatarPosition.y,
    });
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const margin = 20;
      const size = 110;
      const newX = Math.max(margin, Math.min(window.innerWidth - size - margin, e.clientX - dragOffset.x));
      const newY = Math.max(margin, Math.min(window.innerHeight - size - margin, e.clientY - dragOffset.y));
      setAvatarPosition({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      if (isDragging) {
        setIsDragging(false);
      }
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset, avatarPosition, setAvatarPosition]);

  return (
    <div
      ref={avatarRef}
      style={{
        transform: `translate3d(${avatarPosition.x}px, ${avatarPosition.y}px, 0)`,
        touchAction: 'none',
      }}
      className={`fixed top-0 left-0 z-50 transition-transform ${isDragging ? 'cursor-grabbing duration-0' : 'cursor-pointer duration-300'}`}
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Outer Aquatic Halo & Status Pulse */}
      <div className="relative group select-none">
        
        {/* Subtle Water Caustic Aura */}
        <div className={`absolute -inset-3 rounded-full opacity-60 filter blur-md bg-gradient-to-tr ${status.color} animate-water-ripple pointer-events-none`} />

        {/* Concentric Sonar Ring when active */}
        {agentStatus !== 'idle' && (
          <div className="absolute -inset-5 rounded-full border border-cyan-400/40 animate-ping pointer-events-none opacity-40" />
        )}

        {/* Glassmorphic Lens Container */}
        <div
          onClick={(e) => {
            if (!isDragging) {
              e.stopPropagation();
              setIsChatOpen(!isChatOpen);
            }
          }}
          className={`relative w-24 h-24 md:w-28 md:h-28 rounded-full p-[3px] bg-white/70 backdrop-blur-xl border border-white/90 shadow-[0_12px_36px_rgba(14,116,144,0.22)] transition-all duration-300 hover:scale-105 active:scale-95 ${
            isHovered ? 'ring-4 ring-cyan-400/40' : ''
          }`}
        >
          {/* Internal Ocean Chamber with Photorealistic Sea Turtle */}
          <div className="w-full h-full rounded-full overflow-hidden relative shadow-inner bg-gradient-to-b from-sky-300 via-cyan-500 to-teal-800">
            
            {/* The Real Sea Turtle Photographic Asset */}
            <img
              src={seaTurtleImg}
              alt="Aurexo Sea Turtle AI Companion"
              className="w-full h-full object-cover object-center animate-turtle scale-110 transform transition-transform duration-700 group-hover:scale-125"
            />

            {/* Aquatic Caustic Overlay Shimmer */}
            <div className="absolute inset-0 bg-gradient-to-t from-sky-900/30 via-transparent to-white/30 pointer-events-none mix-blend-overlay" />

            {/* Floating Water Sparkle Particles */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              <span className="absolute top-2 left-3 w-1.5 h-1.5 bg-white/80 rounded-full animate-ping opacity-75" />
              <span className="absolute bottom-3 right-4 w-1 h-1 bg-cyan-200/90 rounded-full animate-pulse" />
              <span className="absolute top-6 right-2 w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" />
            </div>

            {/* Specular Curvature Highlight */}
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(ellipse_at_30%_20%,rgba(255,255,255,0.7)_0%,transparent_50%)] pointer-events-none" />
          </div>

          {/* Real-time Agent Status Dot / Badge */}
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/95 backdrop-blur-md border border-slate-200/80 shadow-md">
            <span className={`w-2 h-2 rounded-full ${agentStatus === 'idle' ? 'bg-emerald-500' : 'bg-cyan-500 animate-pulse'}`} />
            <span className="text-[10px] font-semibold text-slate-800 tracking-tight whitespace-nowrap font-mono">
              {agentStatus === 'idle' ? 'AUREXO' : 'AI ACTIVE'}
            </span>
          </div>

          {/* Quick HUD Open Badge */}
          <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-cyan-600 text-white flex items-center justify-center shadow-md border-2 border-white text-xs group-hover:scale-110 transition-transform">
            <Sparkles className="w-3 h-3 text-cyan-100" />
          </div>
        </div>

        {/* Dynamic Hover Tooltip / Status Bubble */}
        {(isHovered || agentStatus !== 'idle') && (
          <div
            className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-3.5 px-3 py-1.5 rounded-xl bg-white/95 backdrop-blur-md border border-slate-200/80 shadow-xl pointer-events-none whitespace-nowrap transition-all duration-200 ${
              isHovered ? 'opacity-100 translate-y-0' : 'opacity-90'
            }`}
          >
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-cyan-500 animate-ping" />
              <div>
                <p className="text-[11px] font-bold text-slate-800 font-display flex items-center gap-1">
                  Aurexo Sea Turtle Sentinel
                  {verification && <ShieldCheck className="w-3 h-3 text-emerald-600 inline" />}
                </p>
                <p className="text-[10px] text-slate-500 font-mono">
                  {status.label} {activeTool ? `• ${activeTool}` : ''}
                </p>
              </div>
            </div>
            {/* Arrow */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-[1px] border-4 border-transparent border-t-white" />
          </div>
        )}

      </div>
    </div>
  );
};
