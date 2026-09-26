import React, { useState, useEffect } from 'react';
import { OrcaStoreProvider, useOrcaStore } from './lib/state/orca-store';
import { NereusOceanBackground } from './components/ocean/NereusOceanBackground';
import { MarinePreloader } from './components/loader/MarinePreloader';
import { AurexoNavbar } from './components/aurexo/AurexoNavbar';
import { AurexoHeroSection } from './components/aurexo/AurexoHeroSection';
import { AurexoDashboardSection } from './components/aurexo/AurexoDashboardSection';
import { AurexoEcosystemSection } from './components/aurexo/AurexoEcosystemSection';
import { AurexoSurveillanceSection } from './components/aurexo/AurexoSurveillanceSection';
import { AurexoEvidenceSection } from './components/aurexo/AurexoEvidenceSection';
import { AurexoPlaybackBar } from './components/aurexo/AurexoPlaybackBar';
import { SeaTurtleAvatar } from './components/aurexo/SeaTurtleAvatar';
import { AurexoChatHud } from './components/aurexo/AurexoChatHud';
import { BackendSettingsModal } from './components/orca/BackendSettingsModal';
import { ScrollSection } from './components/scroll/ScrollEngine';

function AurexoMain() {
  const [activeSection, setActiveSection] = useState('hero');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [showPreloader, setShowPreloader] = useState(true);

  // Scroll spy to update active navigation tab based on viewport position
  useEffect(() => {
    const handleScroll = () => {
      const sections = ['hero', 'dashboard', 'ecosystem', 'surveillance', 'evidence'];
      const scrollY = window.scrollY + 200;

      for (const sectionId of sections) {
        const el = document.getElementById(sectionId);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollY >= top && scrollY < top + height) {
            setActiveSection(sectionId);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
      setActiveSection(sectionId);
    }
  };

  return (
    <div className="relative min-h-screen bg-ocean-950 text-white font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      
      {/* Love-inspired Animated SVG Stroke Preloader Splash Screen */}
      {showPreloader && (
        <MarinePreloader onComplete={() => setShowPreloader(false)} />
      )}

      {/* 60fps Nereus Bioluminescent 2D Canvas Ambient Background (Zero Lag) */}
      <NereusOceanBackground />

      {/* Frosted Glass Top Navigation Bar */}
      <AurexoNavbar
        onOpenSettings={() => setIsSettingsOpen(true)}
        activeSection={activeSection}
        onNavigateSection={scrollToSection}
        onReplaySplash={() => setShowPreloader(true)}
      />

      {/* Main Continuous Scrolling Sections with ScrollEngine Reveals */}
      <main className="relative z-10 flex flex-col">
        {/* Section 1: Hero Landing (Nereus ARGO Float, Living Ocean Vision, SIH Question Chips) */}
        <ScrollSection id="hero">
          <AurexoHeroSection onExplore={() => scrollToSection('dashboard')} />
        </ScrollSection>

        {/* Section 2: Command Center Dashboard (Nereus Interactive Leaflet Satellite & Bathymetry Map) */}
        <ScrollSection id="dashboard">
          <AurexoDashboardSection />
        </ScrollSection>

        {/* Section 3: Ecosystem & Submersible (Acoustic Telemetry, Benthic AUV) */}
        <ScrollSection id="ecosystem">
          <AurexoEcosystemSection />
        </ScrollSection>

        {/* Section 4: Multi-Domain Surveillance & 3D Globe */}
        <ScrollSection id="surveillance">
          <AurexoSurveillanceSection />
        </ScrollSection>

        {/* Section 5: SIH P0 Zero-Hallucination Verification Gate & Provenance DAG */}
        <ScrollSection id="evidence">
          <AurexoEvidenceSection />
        </ScrollSection>
      </main>

      {/* Floating Bottom Playback Pill */}
      <AurexoPlaybackBar />

      {/* Realistic Sea Turtle AI Avatar */}
      <SeaTurtleAvatar />

      {/* Aurexo Chat HUD (Expands on clicking turtle avatar or mission chips) */}
      <AurexoChatHud />

      {/* Settings Modal */}
      <BackendSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

    </div>
  );
}

export default function App() {
  return (
    <OrcaStoreProvider>
      <AurexoMain />
    </OrcaStoreProvider>
  );
}
