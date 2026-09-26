import React, { useState, useRef, useEffect } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  X,
  Send,
  Sparkles,
  ShieldCheck,
  Activity,
  Terminal,
  RefreshCw,
  ExternalLink,
  ChevronDown,
  Volume2,
  Waves,
  Radio,
  FileCheck,
  AlertTriangle,
  CheckCircle2,
  Search,
  BookOpen,
  Compass,
  Globe2,
  Database,
  Clock,
} from 'lucide-react';
import seaTurtleImg from '../../assets/images/sea_turtle_avatar_1790254462691.jpg';

export const AurexoChatHud: React.FC = () => {
  const {
    isChatOpen,
    setIsChatOpen,
    chatMessages,
    submitQuery,
    isRunning,
    agentStatus,
    activeTool,
    activePlan,
    toolCalls,
    evidence,
    verification,
    selectedLanguage,
    setSelectedLanguage,
    clearChat,
    researchState,
    activeConflicts,
    activeAgreements,
    activeCitations,
  } = useOrcaStore();

  const [inputPrompt, setInputPrompt] = useState('');
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const canonicalDemos = [
    {
      label: '🏆 Golden Demo (PFZ + Safety + IMBL + Route)',
      prompt: 'I am fishing near Malim. Find the nearest verified PFZ, check whether it is safe to go tomorrow morning, avoid restricted maritime zones, and show me the safest route.',
    },
    {
      label: '🔬 Deep Research (Arabian Sea 5-Year Trends)',
      prompt: 'Why has fish productivity declined in the Arabian Sea over the past 5 years? Research satellite chlorophyll, SST trends, and compare scientific literature.',
    },
    {
      label: '🌊 Cross-Source SST (INCOIS vs Copernicus)',
      prompt: 'Compare SST and wave height between INCOIS and Copernicus for Mumbai offshore.',
    },
    {
      label: '🇮🇳 தமிழ் (Tamil IMBL Safety)',
      prompt: 'ராமேஸ்வரம் அருகே மீன்பிடிக்க செல்வது பாதுகாப்பானதா?',
    },
    {
      label: '🇮🇳 हिन्दी (Goa PFZ & Weather)',
      prompt: 'गोवा के पास निकटतम मछली पकड़ने का क्षेत्र और मौसम कैसा है?',
    },
    {
      label: '🌪️ Cyclone & High Wave Warning',
      prompt: 'What are the latest INCOIS high wave alerts and IMD cyclone warnings for Odisha coast?',
    },
  ];

  const handleSpeak = (text: string, msgId: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    
    if (speakingMsgId === msgId) {
      window.speechSynthesis.cancel();
      setSpeakingMsgId(null);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onend = () => setSpeakingMsgId(null);
    utterance.onerror = () => setSpeakingMsgId(null);
    setSpeakingMsgId(msgId);
    window.speechSynthesis.speak(utterance);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, toolCalls, activePlan]);

  if (!isChatOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputPrompt.trim() || isRunning) return;
    submitQuery(inputPrompt);
    setInputPrompt('');
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[500px] z-50 flex flex-col bg-ocean-950/95 backdrop-blur-2xl border-l border-cyan-500/30 shadow-[0_20px_60px_-15px_rgba(5,17,26,0.9)] transition-all duration-300 text-white">
      
      {/* Header with Photorealistic Sea Turtle Avatar */}
      <div className="p-3.5 border-b border-cyan-500/20 bg-ocean-900/90 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative w-11 h-11 rounded-full overflow-hidden border-2 border-cyan-400 shadow-md ring-2 ring-cyan-500/30">
            <img
              src={seaTurtleImg}
              alt="Aurexo Sea Turtle"
              className="w-full h-full object-cover object-center animate-turtle"
            />
            <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-emerald-400 border-2 border-ocean-950" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h3 className="text-sm font-bold text-white font-display">Aurexo AI Reasoning</h3>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 font-mono font-bold border border-cyan-400/40">
                ISRO PS 26176
              </span>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
              <Waves className="w-3 h-3 text-cyan-400" />
              {agentStatus === 'idle' ? 'Ready for marine telemetry query' : `Status: ${agentStatus.toUpperCase()}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={clearChat}
            title="Reset Conversation"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-ocean-800/60 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsChatOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-ocean-800/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Indian Regional Language Selector */}
      <div className="px-3.5 py-1.5 bg-ocean-900/60 border-b border-cyan-500/20 flex items-center justify-between text-xs font-mono">
        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Language:</span>
        <div className="flex items-center gap-1">
          {[
            { code: 'en', label: 'EN' },
            { code: 'ta', label: 'தமிழ்' },
            { code: 'hi', label: 'हिन्दी' },
            { code: 'te', label: 'తెలుగు' },
            { code: 'ml', label: 'മലയാളം' },
          ].map((l) => (
            <button
              key={l.code}
              onClick={() => setSelectedLanguage(l.code)}
              className={`px-2 py-0.5 rounded text-[11px] font-bold transition-all cursor-pointer ${
                selectedLanguage === l.code
                  ? 'bg-cyan-500 text-ocean-950 shadow-xs'
                  : 'bg-ocean-900/80 text-slate-300 border border-cyan-500/30 hover:border-cyan-400'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Real-time Agent Reasoning Checklist */}
      {activePlan.length > 0 && isRunning && (
        <div className="p-3 mx-3 my-2 rounded-xl bg-ocean-900/80 border border-cyan-500/30 text-xs animate-in fade-in">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono font-bold text-cyan-200 uppercase tracking-wider flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
              Real Agent Execution Plan
            </span>
            <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 px-2 py-0.5 rounded-full font-bold border border-cyan-400/40">
              {activePlan.filter(s => s.status === 'completed').length}/{activePlan.length} Steps
            </span>
          </div>
          <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
            {activePlan.map((s) => (
              <div key={s.id} className="flex items-center justify-between text-[11px] font-mono py-0.5 border-b border-cyan-500/10 last:border-0">
                <span className={s.status === 'completed' ? 'text-emerald-400 font-semibold' : s.status === 'running' ? 'text-cyan-300 font-bold' : 'text-slate-400'}>
                  {s.status === 'completed' ? '✓' : s.status === 'running' ? '⏳' : '○'} {s.name}
                </span>
                <span className="text-[9px] text-slate-400 uppercase">{s.agent || s.tool}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Deep Research & Google Grounding Indicator */}
      {researchState && (
        <div className="p-3 mx-3 my-1.5 rounded-xl bg-ocean-900/80 border border-cyan-500/30 text-xs shadow-xs animate-in fade-in">
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-mono font-bold text-cyan-200 uppercase tracking-wider flex items-center gap-1.5">
              <Search className={`w-3.5 h-3.5 text-cyan-400 ${researchState.active ? 'animate-spin' : ''}`} />
              {researchState.mode === 'DEEP_RESEARCH' ? 'Deep Research Engine (Gemini 3.8 Flash)' : 'Web Search Grounding'}
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 font-bold border border-cyan-400/40">
              {researchState.active ? 'ACTIVE' : 'COMPLETED'}
            </span>
          </div>
          {researchState.topic && (
            <p className="text-[11px] text-slate-200 font-medium truncate mb-1">
              Topic: {researchState.topic}
            </p>
          )}
          {researchState.step && (
            <p className="text-[10px] font-mono text-cyan-300 flex items-center gap-1">
              <Compass className="w-3 h-3 text-cyan-400 animate-pulse" />
              {researchState.step}
            </p>
          )}
          {researchState.queries && researchState.queries.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {researchState.queries.slice(-2).map((q, idx) => (
                <span key={idx} className="text-[9px] font-mono bg-ocean-950/90 border border-cyan-500/30 text-cyan-300 px-1.5 py-0.5 rounded">
                  🔍 {q}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[92%] rounded-2xl p-3.5 text-sm leading-relaxed ${
                  isUser
                    ? 'bg-gradient-to-r from-cyan-500 to-teal-500 text-ocean-950 font-medium rounded-tr-none shadow-md shadow-cyan-500/20'
                    : 'glass-card-ocean border border-cyan-500/30 text-slate-100 rounded-tl-none shadow-xl'
                }`}
              >
                {!isUser && (
                  <div className="flex items-center justify-between mb-1.5 text-xs text-cyan-300 font-semibold border-b border-cyan-500/20 pb-1">
                    <div className="flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Aurexo Marine Intelligence</span>
                    </div>
                    <button
                      onClick={() => handleSpeak(msg.content, msg.id)}
                      title={speakingMsgId === msg.id ? 'Stop audio' : 'Read aloud'}
                      className="p-1 rounded hover:bg-ocean-800/60 text-cyan-300 transition-colors cursor-pointer"
                    >
                      <Volume2 className={`w-3.5 h-3.5 ${speakingMsgId === msg.id ? 'text-emerald-400 animate-pulse' : ''}`} />
                    </button>
                  </div>
                )}
                
                <p className="whitespace-pre-wrap">{msg.content}</p>

                {/* Cross-Source Conflict Notices */}
                {msg.conflictNotices && msg.conflictNotices.length > 0 && (
                  <div className="mt-2.5 p-2.5 rounded-xl bg-amber-950/60 border border-amber-500/40 text-xs font-mono space-y-1.5">
                    <div className="flex items-center gap-1.5 text-amber-300 font-bold">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <span>Cross-Source Spread Detected & Arbitrated</span>
                    </div>
                    {msg.conflictNotices.map((conf, ci) => (
                      <div key={ci} className="text-[11px] text-amber-200 bg-ocean-950/80 p-2 rounded-lg border border-amber-500/30">
                        <div className="font-semibold text-slate-300 uppercase text-[10px]">
                          Variable: {conf.variable.replace(/_/g, ' ')}
                        </div>
                        <div className="text-amber-300 my-0.5">{conf.spread_summary}</div>
                        <div className="text-emerald-400 font-bold text-[10px]">
                          Resolution: {conf.resolution}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Cross-Source Corroboration / Agreement Notices */}
                {msg.agreementNotices && msg.agreementNotices.length > 0 && (
                  <div className="mt-2.5 p-2 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-xs font-mono">
                    <div className="flex items-center gap-1.5 text-emerald-300 font-bold mb-1">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Multi-Source Corroboration</span>
                    </div>
                    {msg.agreementNotices.map((agr, ai) => (
                      <div key={ai} className="text-[10px] text-slate-300">
                        • {agr.source_1} ({typeof agr.value_1 === 'object' ? JSON.stringify(agr.value_1) : agr.value_1}) corroborated by {agr.source_2} ({typeof agr.value_2 === 'object' ? JSON.stringify(agr.value_2) : agr.value_2}). Preferred: {agr.preferred_source}
                      </div>
                    ))}
                  </div>
                )}

                {/* Authoritative Citations & Grounding */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-cyan-500/20">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-mono font-bold text-cyan-200 uppercase tracking-wider flex items-center gap-1">
                        <BookOpen className="w-3 h-3 text-cyan-400" /> Authoritative Sources ({msg.citations.length})
                      </span>
                      <span className="text-[9px] font-mono text-slate-400">GROUNDED INTELLIGENCE</span>
                    </div>
                    <div className="space-y-1.5">
                      {msg.citations.map((cit, ci) => {
                        const isLive = cit.freshness === 'LIVE';
                        const badgeColor =
                          cit.badge?.includes('WEB') ? 'bg-sky-950/80 text-sky-300 border-sky-500/40' :
                          cit.badge?.includes('SCIENTIFIC') ? 'bg-purple-950/80 text-purple-300 border-purple-500/40' :
                          cit.badge?.includes('ADVISORY') ? 'bg-amber-950/80 text-amber-300 border-amber-500/40' :
                          'bg-emerald-950/80 text-emerald-300 border-emerald-500/40';

                        return (
                          <div
                            key={ci}
                            className="p-2 rounded-xl bg-ocean-900/70 border border-cyan-500/20 hover:border-cyan-400 transition-all text-xs group"
                          >
                            <div className="flex items-center justify-between gap-1 mb-1">
                              <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${badgeColor}`}>
                                {cit.badge || 'GROUNDING'}
                              </span>
                              {cit.freshness && (
                                <span className="text-[9px] font-mono text-slate-400 flex items-center gap-1">
                                  {isLive && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                                  {cit.freshness}
                                </span>
                              )}
                            </div>
                            <a
                              href={cit.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs font-semibold text-white group-hover:text-cyan-300 flex items-center gap-1 transition-colors leading-snug"
                            >
                              <span className="truncate">{cit.title}</span>
                              <ExternalLink className="w-3 h-3 flex-shrink-0 text-slate-400 group-hover:text-cyan-300" />
                            </a>
                            <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mt-1 pt-1 border-t border-cyan-500/10">
                              <span className="flex items-center gap-1">
                                <Globe2 className="w-2.5 h-2.5" />
                                {cit.domain}
                              </span>
                              {cit.retrieved_at && (
                                <span>{new Date(cit.retrieved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} UTC</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Evidence verification within message */}
                {msg.verification && (
                  <div className="mt-3 pt-2.5 border-t border-cyan-500/20 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-1 text-emerald-400 font-semibold">
                      <ShieldCheck className="w-4 h-4" />
                      <span>Empirical Verification: {msg.verification.status === 'VERIFIED' ? 'PASSED (0-Hallucination)' : 'CORROBORATING'}</span>
                    </div>
                    <span className="text-[11px] text-cyan-300 font-bold">
                      {msg.verification.confidenceScore}%
                    </span>
                  </div>
                )}
              </div>

              <span className="text-[10px] text-slate-400 mt-1 px-1 font-mono">
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* Canonical SIH Demo Queries Bar */}
      <div className="px-3.5 py-2 bg-ocean-900/90 border-t border-cyan-500/20 overflow-x-auto">
        <div className="flex items-center gap-1.5 no-scrollbar whitespace-nowrap">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-cyan-400" /> SIH Demos:
          </span>
          {canonicalDemos.map((demo, idx) => (
            <button
              key={idx}
              onClick={() => submitQuery(demo.prompt)}
              disabled={isRunning}
              className="px-2.5 py-1 rounded-lg text-xs bg-ocean-950/80 text-cyan-200 border border-cyan-500/30 hover:border-cyan-400 hover:text-white transition-all shadow-xs disabled:opacity-50 font-medium cursor-pointer"
            >
              {demo.label}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div className="p-3 border-t border-cyan-500/20 bg-ocean-950">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <input
            type="text"
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            placeholder="Ask Aurexo about PFZ, SST, weather, IMBL geofence, or route..."
            disabled={isRunning}
            className="flex-1 px-4 py-2.5 rounded-xl bg-ocean-900/90 border border-cyan-500/30 text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-400/40 focus:border-cyan-400 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={!inputPrompt.trim() || isRunning}
            className="p-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-500 text-ocean-950 font-bold hover:from-cyan-400 hover:to-teal-400 transition-all shadow-md shadow-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

    </div>
  );
};
