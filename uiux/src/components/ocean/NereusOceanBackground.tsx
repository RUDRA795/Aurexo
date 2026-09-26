import React, { useEffect, useRef } from 'react';

interface Particle {
  x: number;
  y: number;
  size: number;
  speedY: number;
  speedX: number;
  opacity: number;
}

interface Bubble {
  x: number;
  y: number;
  radius: number;
  speed: number;
  opacity: number;
  wobble: number;
}

interface Fish {
  x: number;
  y: number;
  size: number;
  speed: number;
  direction: number;
  depthLayer: number;
  opacity: number;
}

export const NereusOceanBackground: React.FC<{ opacity?: number }> = ({ opacity = 0.85 }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef<{ x: number; y: number }>({ x: -1000, y: -1000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isMobile = width < 768;

    // Glowing plankton particles
    const particleCount = prefersReducedMotion ? 0 : isMobile ? 18 : 40;
    const particles: Particle[] = Array.from({ length: particleCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 2.5 + 1,
      speedY: Math.random() * 0.25 + 0.08,
      speedX: (Math.random() - 0.5) * 0.15,
      opacity: Math.random() * 0.4 + 0.15,
    }));

    // Soft rising ocean bubbles
    const bubbleCount = prefersReducedMotion ? 0 : isMobile ? 8 : 18;
    const bubbles: Bubble[] = Array.from({ length: bubbleCount }, () => ({
      x: Math.random() * width,
      y: height + Math.random() * 100,
      radius: Math.random() * 3.5 + 1.2,
      speed: Math.random() * 0.6 + 0.35,
      opacity: Math.random() * 0.3 + 0.1,
      wobble: Math.random() * Math.PI * 2,
    }));

    // Soft pelagic silhouettes (mackerel, tuna, rays)
    const fishCount = prefersReducedMotion ? 0 : isMobile ? 2 : 5;
    const fishList: Fish[] = Array.from({ length: fishCount }, () => ({
      x: Math.random() * width,
      y: Math.random() * (height * 0.75) + height * 0.12,
      size: Math.random() * 12 + 9,
      speed: Math.random() * 0.45 + 0.25,
      direction: Math.random() > 0.5 ? 1 : -1,
      depthLayer: Math.floor(Math.random() * 2) + 1,
      opacity: Math.random() * 0.14 + 0.06,
    }));

    let waveOffset = 0;

    const drawFish = (f: Fish) => {
      ctx.save();
      ctx.translate(f.x, f.y);
      if (f.direction < 0) ctx.scale(-1, 1);

      ctx.fillStyle = `rgba(8, 126, 164, ${f.opacity})`;
      ctx.beginPath();
      ctx.ellipse(0, 0, f.size, f.size * 0.35, 0, 0, Math.PI * 2);
      ctx.moveTo(-f.size * 0.8, 0);
      ctx.lineTo(-f.size * 1.3, -f.size * 0.4);
      ctx.lineTo(-f.size * 1.1, 0);
      ctx.lineTo(-f.size * 1.3, f.size * 0.4);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    };

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // 1. Shimmering Sunlit Caustics Rays
      waveOffset += 0.004;
      ctx.save();
      for (let i = 0; i < 4; i++) {
        const rayX = (width / 5) * (i + 1) + Math.sin(waveOffset + i * 1.5) * 35;
        const rayGrad = ctx.createLinearGradient(rayX, 0, rayX + 60, height * 0.65);
        rayGrad.addColorStop(0, 'rgba(6, 182, 212, 0.07)');
        rayGrad.addColorStop(0.5, 'rgba(34, 211, 238, 0.03)');
        rayGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');

        ctx.fillStyle = rayGrad;
        ctx.beginPath();
        ctx.moveTo(rayX - 40, 0);
        ctx.lineTo(rayX + 40, 0);
        ctx.lineTo(rayX + 110, height * 0.65);
        ctx.lineTo(rayX - 20, height * 0.65);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();

      // 2. Bioluminescent Micro-Particles
      particles.forEach((p) => {
        p.y -= p.speedY;
        p.x += p.speedX;
        if (p.y < 0) {
          p.y = height + 10;
          p.x = Math.random() * width;
        }

        ctx.fillStyle = `rgba(6, 182, 212, ${p.opacity})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      // 3. Ambient Rising Bubbles
      bubbles.forEach((b) => {
        b.y -= b.speed;
        b.wobble += 0.025;
        b.x += Math.sin(b.wobble) * 0.35;

        if (b.y < -20) {
          b.y = height + Math.random() * 50;
          b.x = Math.random() * width;
        }

        ctx.strokeStyle = `rgba(34, 211, 238, ${b.opacity * 1.2})`;
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.radius, 0, Math.PI * 2);
        ctx.stroke();

        // Inner bubble specular highlight
        ctx.fillStyle = `rgba(255, 255, 255, ${b.opacity * 0.7})`;
        ctx.beginPath();
        ctx.arc(b.x - b.radius * 0.3, b.y - b.radius * 0.3, b.radius * 0.25, 0, Math.PI * 2);
        ctx.fill();
      });

      // 4. Background Marine Silhouettes
      fishList.forEach((f) => {
        f.x += f.speed * f.direction;
        if (f.direction > 0 && f.x > width + 100) f.x = -100;
        if (f.direction < 0 && f.x < -100) f.x = width + 100;
        drawFish(f);
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 transition-opacity duration-1000"
      style={{ opacity }}
    />
  );
};
