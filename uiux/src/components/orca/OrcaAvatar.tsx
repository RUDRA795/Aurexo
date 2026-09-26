import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useOrcaStore } from '../../lib/state/orca-store';
import { Sparkles, Activity, CheckCircle, AlertTriangle, MessageSquare } from 'lucide-react';

export const OrcaAvatar: React.FC = () => {
  const {
    agentStatus,
    activeTool,
    isChatOpen,
    setIsChatOpen,
    avatarPosition,
    setAvatarPosition,
  } = useOrcaStore();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const avatarRef = useRef<HTMLDivElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ startX: number; startY: number; initialX: number; initialY: number; moved: boolean }>({
    startX: 0,
    startY: 0,
    initialX: 0,
    initialY: 0,
    moved: false,
  });

  // State-based glow color
  const getStatusColor = () => {
    switch (agentStatus) {
      case 'planning':
      case 'querying_pfz':
      case 'retrieving_sst':
      case 'checking_weather':
      case 'retrieving_chlorophyll':
        return '#06b6d4'; // Cyan active
      case 'searching_advisories':
        return '#8b5cf6'; // Purple RAG
      case 'verifying':
        return '#3b82f6'; // Deep blue verification
      case 'complete':
        return '#10b981'; // Emerald complete
      case 'error':
        return '#ef4444'; // Red error
      default:
        return '#38bdf8'; // Calm cyan-blue
    }
  };

  // Dragging logic
  const handlePointerDown = (e: React.PointerEvent) => {
    // Only drag with left click or touch
    if (e.button !== 0) return;
    
    setIsDragging(true);
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: avatarPosition.x,
      initialY: avatarPosition.y,
      moved: false,
    };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;

    const deltaX = e.clientX - dragStartRef.current.startX;
    const deltaY = e.clientY - dragStartRef.current.startY;

    if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
      dragStartRef.current.moved = true;
    }

    const newX = dragStartRef.current.initialX + deltaX;
    const newY = dragStartRef.current.initialY + deltaY;

    // Viewport bounds clamping
    const size = 90;
    const padding = 16;
    const clampedX = Math.max(padding, Math.min(window.innerWidth - size - padding, newX));
    const clampedY = Math.max(padding, Math.min(window.innerHeight - size - padding, newY));

    setAvatarPosition({ x: clampedX, y: clampedY });
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    setIsDragging(false);
    try {
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {}

    // If user clicked without dragging, toggle Chat HUD
    if (!dragStartRef.current.moved) {
      setIsChatOpen(!isChatOpen);
    } else {
      // Magnetic edge snapping if within 45px of screen borders
      const padding = 20;
      const size = 90;
      let finalX = avatarPosition.x;
      let finalY = avatarPosition.y;

      if (finalX < padding + 35) finalX = padding;
      else if (finalX > window.innerWidth - size - padding - 35) finalX = window.innerWidth - size - padding;

      if (finalY < padding + 35) finalY = padding;
      else if (finalY > window.innerHeight - size - padding - 35) finalY = window.innerHeight - size - padding;

      setAvatarPosition({ x: finalX, y: finalY });
    }
  };

  // Fluid Organic Canvas Orb Shader Animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let time = 0;

    const render = () => {
      time += 0.035;
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;

      ctx.clearRect(0, 0, width, height);

      // Speed & agitation depends on agent state
      let speedMult = 1.0;
      let amplitude = 6.0;
      if (agentStatus === 'planning' || agentStatus === 'querying_pfz' || agentStatus === 'retrieving_sst') {
        speedMult = 2.2;
        amplitude = 9.0;
      } else if (agentStatus === 'verifying') {
        speedMult = 2.8;
        amplitude = 11.0;
      }

      // 1. Outer Glow Aura
      const glowGrad = ctx.createRadialGradient(cx, cy, 18, cx, cy, 48);
      const color = getStatusColor();
      glowGrad.addColorStop(0, `${color}66`);
      glowGrad.addColorStop(0.7, `${color}22`);
      glowGrad.addColorStop(1, 'transparent');

      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, 48, 0, Math.PI * 2);
      ctx.fill();

      // 2. Fluid Deforming Organic Blob (similar to Reference Video 1 "Agentic AI" fluid shape)
      ctx.save();
      ctx.beginPath();
      const points = 12;
      const baseRadius = 26;

      for (let i = 0; i <= points; i++) {
        const angle = (i / points) * Math.PI * 2;
        const wave = 
          Math.sin(angle * 3 + time * speedMult) * amplitude * 0.4 +
          Math.cos(angle * 2 - time * speedMult * 1.2) * amplitude * 0.35 +
          Math.sin(angle * 5 + time * 0.8) * 2.0;

        const r = baseRadius + wave;
        const x = cx + Math.cos(angle) * r;
        const y = cy + Math.sin(angle) * r;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.closePath();

      // Iridescent Inner Gradient
      const orbGrad = ctx.createRadialGradient(cx - 6, cy - 8, 4, cx, cy, 32);
      orbGrad.addColorStop(0, '#ffffff');
      orbGrad.addColorStop(0.3, color);
      orbGrad.addColorStop(0.8, '#082f49');
      orbGrad.addColorStop(1, '#020b17');

      ctx.fillStyle = orbGrad;
      ctx.fill();

      ctx.strokeStyle = `${color}cc`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.restore();

      // 3. Nucleus Core Sparks
      ctx.save();
      const sparkRadius = 5 + Math.sin(time * 3) * 2;
      const sparkGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, sparkRadius);
      sparkGrad.addColorStop(0, '#ffffff');
      sparkGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = sparkGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, sparkRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // 4. Orbital Ring
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(cx, cy, 36, 14, time * 0.5, 0, Math.PI * 2);
      ctx.strokeStyle = `${color}55`;
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 6]);
      ctx.stroke();
      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animId);
  }, [agentStatus]);

  return (
    <div
      ref={avatarRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        left: `${avatarPosition.x}px`,
        top: `${avatarPosition.y}px`,
        touchAction: 'none',
      }}
      className={`fixed z-50 select-none cursor-grab active:cursor-grabbing transition-transform ${
        isDragging ? 'scale-110 shadow-2xl' : 'hover:scale-105'
      }`}
      title="ORCA Collaborative AI Assistant (Click to open chat, drag to reposition)"
    >
      <div className="relative w-24 h-24 flex items-center justify-center">
        {/* Radar Pulse when active */}
        {agentStatus !== 'idle' && (
          <span 
            className="absolute inset-0 rounded-full animate-ping opacity-30 pointer-events-none"
            style={{ backgroundColor: getStatusColor() }}
          />
        )}

        {/* Ambient Ring */}
        <div 
          className="absolute inset-1 rounded-full blur-md opacity-40 transition-colors pointer-events-none"
          style={{ backgroundColor: getStatusColor() }}
        />

        {/* Canvas Orb */}
        <canvas
          ref={canvasRef}
          width={100}
          height={100}
          className="w-full h-full pointer-events-none drop-shadow-[0_8px_20px_rgba(0,0,0,0.7)]"
        />

        {/* Status Micro-Badge */}
        <div className="absolute -bottom-1 flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-950/80 border border-white/10 text-[9px] font-mono tracking-wider text-cyan-300 backdrop-blur-sm pointer-events-none">
          {agentStatus === 'idle' ? (
            <>
              <Sparkles className="w-2.5 h-2.5 text-cyan-400" />
              <span>ORCA</span>
            </>
          ) : agentStatus === 'complete' ? (
            <>
              <CheckCircle className="w-2.5 h-2.5 text-emerald-400" />
              <span>SYNC</span>
            </>
          ) : (
            <>
              <Activity className="w-2.5 h-2.5 text-cyan-400 animate-spin" />
              <span className="uppercase">{agentStatus.replace('_', ' ').slice(0, 7)}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
