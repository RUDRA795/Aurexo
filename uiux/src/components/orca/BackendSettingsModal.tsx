import React, { useState } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { X, Server, CheckCircle2, AlertCircle, RefreshCw, Cpu, ShieldCheck } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const BackendSettingsModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const {
    backendUrl,
    setBackendUrl,
    isConnected,
    connectionMessage,
    connectionMode,
    setConnectionMode,
    checkConnection,
  } = useOrcaStore();

  const [inputUrl, setInputUrl] = useState(backendUrl);
  const [isTesting, setIsTesting] = useState(false);

  if (!isOpen) return null;

  const handleTestAndSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsTesting(true);
    setBackendUrl(inputUrl);
    await checkConnection();
    setIsTesting(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ocean-950/80 backdrop-blur-md animate-in fade-in">
      <div className="w-full max-w-md glass-card-ocean rounded-2xl border border-cyan-500/30 p-6 shadow-2xl space-y-4 text-white">
        
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-cyan-400" />
            <h3 className="text-sm font-bold font-mono text-white tracking-wider uppercase">
              Aurexo Backend & Neural Engine
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-ocean-900/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Current Status Pill */}
        <div
          className={`p-3 rounded-xl border text-xs font-mono flex items-center justify-between ${
            isConnected
              ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
              : 'bg-cyan-950/60 border-cyan-500/40 text-cyan-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {isConnected ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 text-cyan-400 animate-pulse" />
            )}
            <span>{connectionMessage}</span>
          </div>
          <button
            onClick={checkConnection}
            className="p-1 rounded hover:bg-ocean-900 text-cyan-300 transition-colors cursor-pointer"
            title="Refresh Health Check"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Form to change URL */}
        <form onSubmit={handleTestAndSave} className="space-y-4 font-mono text-xs">
          <div>
            <label className="text-[11px] uppercase font-bold text-slate-300 block mb-1">
              FastAPI Endpoint URL
            </label>
            <input
              type="text"
              value={inputUrl}
              onChange={(e) => setInputUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
              className="w-full bg-ocean-900/90 border border-cyan-500/30 rounded-xl px-3.5 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/40 focus:border-cyan-400"
            />
            <p className="text-[10px] text-slate-400 mt-1">
              Connects to FastAPI SSE pipeline via <code className="text-cyan-300 font-bold">POST /v1/agent/stream</code>
            </p>
          </div>

          {/* Mode Selector */}
          <div>
            <label className="text-[11px] uppercase font-bold text-slate-300 block mb-1.5">
              Execution Architecture Mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setConnectionMode('backend')}
                className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                  connectionMode === 'backend'
                    ? 'bg-cyan-500 text-ocean-950 border-cyan-400 shadow-xs'
                    : 'bg-ocean-900/60 border-cyan-500/20 text-slate-300 hover:border-cyan-400'
                }`}
              >
                <span className="block font-bold text-xs">Real Backend API</span>
                <span className="text-[10px] opacity-80 block mt-0.5">FastAPI & SSE Streams</span>
              </button>

              <button
                type="button"
                onClick={() => setConnectionMode('simulation')}
                className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                  connectionMode === 'simulation'
                    ? 'bg-cyan-500 text-ocean-950 border-cyan-400 shadow-xs'
                    : 'bg-ocean-900/60 border-cyan-500/20 text-slate-300 hover:border-cyan-400'
                }`}
              >
                <span className="block font-bold text-xs">Simulated Engine</span>
                <span className="text-[10px] opacity-80 block mt-0.5">Local SIH Dataset</span>
              </button>
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-slate-400 hover:text-white hover:bg-ocean-900/60 transition-colors font-sans text-xs font-semibold cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isTesting}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-500 text-ocean-950 hover:from-cyan-400 hover:to-teal-400 font-sans text-xs font-bold transition-all shadow-md shadow-cyan-500/20 disabled:opacity-50 cursor-pointer"
            >
              {isTesting ? 'Verifying Link...' : 'Save & Reconnect'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};
