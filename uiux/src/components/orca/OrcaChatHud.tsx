import React, { useState, useRef, useEffect } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import {
  X,
  Send,
  Sparkles,
  Bot,
  User,
  ShieldCheck,
  RefreshCw,
  Compass,
  Thermometer,
  CloudRain,
  ChevronRight,
  Terminal,
} from 'lucide-react';

const SUGGESTED_QUERIES = [
  'Analyze Potential Fishing Zones (PFZ) off Goa-Ratnagiri shelf',
  'Check thermal SST anomalies and thermocline depth',
  'Verify coastal weather, wave swell, and artisanal safety',
  'Search marine conservation boundaries & navigation advisories',
];

export const OrcaChatHud: React.FC = () => {
  const {
    isChatOpen,
    setIsChatOpen,
    chatMessages,
    submitQuery,
    isRunning,
    agentStatus,
    activeTool,
    clearChat,
    avatarPosition,
    connectionMode,
    isConnected,
  } = useOrcaStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    if (isChatOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, isChatOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isChatOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isChatOpen]);

  if (!isChatOpen) return null;

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isRunning) return;
    submitQuery(input.trim());
    setInput('');
  };

  const handleSelectSuggestion = (query: string) => {
    if (isRunning) return;
    submitQuery(query);
  };

  // Compute responsive layout position near avatar without overflowing
  const hudWidth = 420;
  const hudHeight = 560;
  const padding = 20;

  let leftPos = avatarPosition.x - hudWidth + 60;
  let topPos = avatarPosition.y - hudHeight + 20;

  if (leftPos < padding) leftPos = padding;
  if (leftPos + hudWidth > window.innerWidth - padding) {
    leftPos = window.innerWidth - hudWidth - padding;
  }
  if (topPos < padding) topPos = padding;
  if (topPos + hudHeight > window.innerHeight - padding) {
    topPos = window.innerHeight - hudHeight - padding;
  }

  return (
    <div
      style={{
        left: `${leftPos}px`,
        top: `${topPos}px`,
        width: `${Math.min(hudWidth, window.innerWidth - 32)}px`,
        height: `${Math.min(hudHeight, window.innerHeight - 32)}px`,
      }}
      className="fixed z-40 flex flex-col glass-panel-active rounded-2xl border border-cyan-500/30 shadow-[0_20px_60px_rgba(0,0,0,0.85)] backdrop-blur-2xl overflow-hidden transition-all duration-200 animate-in fade-in zoom-in-95"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-cyan-500/20 bg-slate-950/60">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center">
            <Bot className="w-4 h-4 text-cyan-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-white font-mono tracking-wider">ORCA AI REASONING</h3>
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
            </div>
            <p className="text-[10px] text-slate-400 font-mono">
              {isConnected ? 'LIVE FASTAPI BACKEND' : 'SIMULATION ADAPTER READY'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={clearChat}
            title="Reset Chat Session"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsChatOpen(false)}
            title="Close Chat"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div className="flex items-center gap-1.5 mb-1 px-1">
              {msg.sender === 'user' ? (
                <>
                  <span className="text-[10px] font-mono text-slate-400">Commander</span>
                  <User className="w-3 h-3 text-cyan-400" />
                </>
              ) : (
                <>
                  <Bot className="w-3 h-3 text-cyan-400" />
                  <span className="text-[10px] font-mono text-cyan-300">ORCA Multi-Agent</span>
                </>
              )}
            </div>

            <div
              className={`p-3.5 rounded-xl text-xs leading-relaxed max-w-[92%] ${
                msg.sender === 'user'
                  ? 'bg-cyan-600/30 border border-cyan-400/40 text-slate-100 shadow-md'
                  : 'bg-slate-900/80 border border-slate-700/60 text-slate-200'
              }`}
            >
              {/* Message text with basic markdown formatting */}
              <div className="whitespace-pre-wrap font-sans">{msg.content}</div>

              {/* Streaming Indicator */}
              {msg.isStreaming && (
                <div className="mt-2 flex items-center gap-2 text-cyan-400 text-[11px] font-mono">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                  <span>
                    {activeTool ? `Executing ${activeTool.replace('_', ' ')}...` : 'Reasoning across marine datasets...'}
                  </span>
                </div>
              )}

              {/* Verification Badge */}
              {msg.verification && (
                <div className="mt-3 pt-2.5 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-emerald-300">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Cross-Agent Consensus: {msg.verification.confidenceScore}%</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                    {msg.verification.status}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Real-time Tool Activity Box when executing */}
        {isRunning && activeTool && (
          <div className="p-3 rounded-lg bg-slate-950/70 border border-cyan-500/30 text-xs font-mono space-y-1 text-cyan-300 animate-pulse">
            <div className="flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-cyan-400" />
              <span>ACTIVE TOOL: {activeTool.toUpperCase()}</span>
            </div>
            <p className="text-[10px] text-slate-400 pl-5">
              Normalizing INCOIS & met-ocean vectors...
            </p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Quick Queries */}
      <div className="px-3 py-2 border-t border-slate-800/80 bg-slate-950/40">
        <span className="text-[10px] font-mono uppercase text-slate-400 px-1">Mission Prompts</span>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {SUGGESTED_QUERIES.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSelectSuggestion(q)}
              disabled={isRunning}
              className="text-[10px] font-mono py-1 px-2 rounded-md bg-slate-800/60 hover:bg-cyan-500/20 hover:text-cyan-300 text-slate-300 border border-slate-700/50 transition-colors text-left truncate max-w-[200px]"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input Field */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-cyan-500/20 bg-slate-950/80 flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask ORCA marine intelligence..."
          disabled={isRunning}
          className="flex-1 bg-slate-900/90 border border-cyan-500/30 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 transition-colors"
        />
        <button
          type="submit"
          disabled={!input.trim() || isRunning}
          className="p-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-md"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};
