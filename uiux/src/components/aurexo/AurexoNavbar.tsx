import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  Waves,
  Search,
  Sliders,
  Volume2,
  VolumeX,
  Radio,
  CheckCircle2,
  AlertCircle,
  Compass,
  Layers,
  Sparkles,
  ChevronDown,
  Film
} from 'lucide-react';
import seaTurtleImg from '../../assets/images/sea_turtle_avatar_1790254462691.jpg';

interface AurexoNavbarProps {
  onOpenSettings: () => void;
  activeSection: string;
  onNavigateSection: (sectionId: string) => void;
  onReplaySplash?: () => void;
}

export const AurexoNavbar: React.FC<AurexoNavbarProps> = ({
  onOpenSettings,
  activeSection,
  onNavigateSection,
  onReplaySplash,
}) => {
  const {
    isConnected,
    isAudioPlaying,
    toggleAudio,
    submitQuery,
    setIsChatOpen,
    isChatOpen,
  } = useOrcaStore();

  const [searchQuery, setSearchQuery] = useState('');

  const navLinks = [
    { id: 'hero', label: 'Home' },
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'ecosystem', label: 'Ecosystem' },
    { id: 'surveillance', label: 'Surveillance' },
    { id: 'evidence', label: 'Evidence & Verify' },
  ];

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      submitQuery(searchQuery);
      setIsChatOpen(true);
      setSearchQuery('');
    }
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-40 px-4 md:px-8 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-5 py-2.5 rounded-2xl glass-panel-ocean border border-cyan-500/30 shadow-2xl">
        
        {/* Brand Logo & Name */}
        <div
          onClick={() => onNavigateSection('hero')}
          className="flex items-center gap-3 cursor-pointer select-none group"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-teal-400 to-emerald-400 flex items-center justify-center shadow-lg shadow-cyan-500/30 group-hover:scale-105 transition-transform">
            <Waves className="w-6 h-6 text-ocean-950" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-lg font-black tracking-wider text-white font-display">
                AUREXO
              </span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 font-mono">
                SIH PS-176
              </span>
            </div>
            <p className="text-[10px] tracking-wide text-slate-300 font-mono">
              MARINE TWIN INTELLIGENCE
            </p>
          </div>
        </div>

        {/* Navigation Tabs (As seen in Reference Videos) */}
        <nav className="hidden md:flex items-center gap-1 bg-ocean-900/80 p-1 rounded-xl border border-cyan-500/20">
          {navLinks.map((item) => {
            const isActive = activeSection === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigateSection(item.id)}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                  isActive
                    ? 'bg-cyan-500 text-ocean-950 shadow-md font-bold'
                    : 'text-slate-300 hover:text-white hover:bg-ocean-800/60'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Right Action Tools: Search, Audio, Status & Settings */}
        <div className="flex items-center gap-2.5">
          
          {/* Quick Marine Search Input (Frosted pill from video) */}
          <form onSubmit={handleSearchSubmit} className="relative hidden lg:block">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search PFZ, SST, vessel..."
              className="w-48 xl:w-56 pl-8 pr-3 py-1.5 rounded-full text-xs bg-ocean-900/90 text-white placeholder-slate-400 border border-cyan-500/30 focus:outline-none focus:w-64 focus:ring-2 focus:ring-cyan-400/30 focus:border-cyan-400 transition-all font-mono"
            />
            <Search className="w-3.5 h-3.5 text-cyan-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          </form>

          {/* Replay Cinematic Splash Button */}
          {onReplaySplash && (
            <button
              onClick={onReplaySplash}
              title="Replay Cinematic Intro & Video Splash"
              className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-ocean-900/80 border border-cyan-500/30 text-xs font-mono text-cyan-300 hover:text-white hover:border-cyan-400 transition-all shadow-sm cursor-pointer"
            >
              <Film className="w-3.5 h-3.5 text-cyan-400" />
              <span>Intro</span>
            </button>
          )}

          {/* Oceanic Ambience Audio Toggle */}
          <button
            onClick={toggleAudio}
            title={isAudioPlaying ? 'Mute Ocean Breeze Audio' : 'Play Ocean Breeze & Sonar Ambience'}
            className={`p-2 rounded-xl border transition-all cursor-pointer ${
              isAudioPlaying
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-sm'
                : 'bg-ocean-900/80 border-cyan-500/30 text-slate-400 hover:text-white'
            }`}
          >
            {isAudioPlaying ? <Volume2 className="w-4 h-4 text-cyan-400 animate-pulse" /> : <VolumeX className="w-4 h-4" />}
          </button>

          {/* Backend Connection Status Pill */}
          <div
            onClick={onOpenSettings}
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-ocean-900/80 border border-cyan-500/30 text-xs text-cyan-200 cursor-pointer hover:border-cyan-400 transition-colors shadow-2xs"
            title="Click to configure backend API endpoint"
          >
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-cyan-400 animate-pulse'}`} />
            <span className="font-mono text-[11px] font-medium">
              {isConnected ? 'LIVE API' : 'SIM ENGINE'}
            </span>
          </div>

          {/* Chat HUD Trigger with Sea Turtle Thumbnail */}
          <button
            onClick={() => setIsChatOpen(!isChatOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-500 text-ocean-950 font-bold text-xs shadow-md shadow-cyan-500/20 hover:from-cyan-400 hover:to-teal-400 transition-all cursor-pointer"
          >
            <div className="w-5 h-5 rounded-full overflow-hidden border border-white/60">
              <img src={seaTurtleImg} alt="Sea Turtle" className="w-full h-full object-cover" />
            </div>
            <span className="hidden sm:inline">Aurexo AI</span>
          </button>

          {/* Settings Modal Button */}
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-xl bg-ocean-900/80 border border-cyan-500/30 text-cyan-300 hover:text-white hover:border-cyan-400 transition-colors cursor-pointer"
            title="Settings & System Architecture"
          >
            <Sliders className="w-4 h-4" />
          </button>

        </div>
      </div>
    </header>
  );
};
