import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { useOrcaStore } from '../../lib/state/orca-store';
import { Eye, Layers, Compass, Maximize2, ShieldAlert } from 'lucide-react';

interface MarineZonePin {
  id: string;
  name: string;
  lat: number;
  lng: number;
  type: 'PFZ' | 'SST_FRONT' | 'BUOY' | 'AUV_SURVEY';
  sst: string;
  wave: string;
  status: string;
}

const MARINE_PINS: MarineZonePin[] = [
  {
    id: 'pin_goa',
    name: 'Goa-Ratnagiri Continental Break',
    lat: 15.42,
    lng: 73.41,
    type: 'PFZ',
    sst: '28.2°C',
    wave: '1.35m',
    status: 'ACTIVE PFZ VENDOR',
  },
  {
    id: 'pin_mumbai',
    name: 'Mumbai High Offshore Platform',
    lat: 18.92,
    lng: 72.83,
    type: 'BUOY',
    sst: '27.9°C',
    wave: '1.60m',
    status: 'MET-OCEAN BUOY 01',
  },
  {
    id: 'pin_kochi',
    name: 'Kochi Deep Ocean Shelf',
    lat: 9.94,
    lng: 75.85,
    type: 'AUV_SURVEY',
    sst: '28.8°C',
    wave: '1.10m',
    status: 'ACOUSTIC SURVEY REGION',
  },
  {
    id: 'pin_lakshadweep',
    name: 'Lakshadweep Coral Basin',
    lat: 10.57,
    lng: 72.64,
    type: 'SST_FRONT',
    sst: '29.1°C',
    wave: '0.95m',
    status: 'MARINE SANCTUARY CLEAR',
  }
];

export const MarineGlobe: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { mapLayers, toggleMapLayer, marineData, agentStatus, setFocusedTarget } = useOrcaStore();
  const [selectedPin, setSelectedPin] = useState<MarineZonePin | null>(MARINE_PINS[0]);
  const [isHovered, setIsHovered] = useState(false);

  const mapLayersRef = useRef(mapLayers);
  useEffect(() => {
    mapLayersRef.current = mapLayers;
  }, [mapLayers]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 2, 7.5);

    const globeGroup = new THREE.Group();
    scene.add(globeGroup);

    // Initial orientation focusing on the Indian Ocean basin (Lat 15 N, Long 75 E)
    globeGroup.rotation.y = -Math.PI / 1.75;
    globeGroup.rotation.x = 0.28;

    // 1. Globe Base Sphere with Oceanic Grid
    const radius = 2.4;
    const sphereGeo = new THREE.SphereGeometry(radius, 64, 64);

    const globeMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uDeepWater: { value: new THREE.Color(0x031124) },
        uShallowWater: { value: new THREE.Color(0x083358) },
        uGridColor: { value: new THREE.Color(0x0ea5e9) },
      },
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec2 vUv;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPosition = position;
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform float uTime;
        uniform vec3 uDeepWater;
        uniform vec3 uShallowWater;
        uniform vec3 uGridColor;
        varying vec3 vNormal;
        varying vec3 vPosition;
        varying vec2 vUv;

        void main() {
          // Latitude/Longitude Grid lines
          float latLines = step(0.97, sin(vUv.y * 3.14159 * 24.0));
          float lonLines = step(0.97, sin(vUv.x * 3.14159 * 48.0));
          float grid = max(latLines, lonLines) * 0.22;

          // Atmospheric rim glow
          float rim = 1.0 - max(dot(vNormal, vec3(0.0, 0.0, 1.0)), 0.0);
          rim = pow(rim, 2.5);

          vec3 baseColor = mix(uDeepWater, uShallowWater, vUv.y);
          vec3 finalColor = baseColor + (uGridColor * grid) + (vec3(0.05, 0.6, 0.9) * rim * 0.7);
          gl_FragColor = vec4(finalColor, 0.94);
        }
      `,
      transparent: true,
    });

    const globeMesh = new THREE.Mesh(sphereGeo, globeMat);
    globeGroup.add(globeMesh);

    // 2. Glowing Atmosphere Outer Halo
    const haloGeo = new THREE.SphereGeometry(radius * 1.15, 48, 48);
    const haloMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        void main() {
          float intensity = pow(0.65 - dot(vNormal, vec3(0, 0, 1.0)), 2.8);
          gl_FragColor = vec4(0.05, 0.75, 1.0, intensity * 0.6);
        }
      `,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      transparent: true,
    });
    const haloMesh = new THREE.Mesh(haloGeo, haloMat);
    globeGroup.add(haloMesh);

    // Utility: Convert Lat/Lng to 3D Sphere coordinates
    const latLngToVector3 = (lat: number, lng: number, r: number) => {
      const phi = (90 - lat) * (Math.PI / 180);
      const theta = (lng + 180) * (Math.PI / 180);
      const x = -(r * Math.sin(phi) * Math.cos(theta));
      const z = r * Math.sin(phi) * Math.sin(theta);
      const y = r * Math.cos(phi);
      return new THREE.Vector3(x, y, z);
    };

    // 3. Orbital Trajectories (INCOIS Satellite & Surveillance Drone Arcs)
    const orbitGroup = new THREE.Group();
    globeGroup.add(orbitGroup);

    const createArc = (startVec: THREE.Vector3, endVec: THREE.Vector3, color: number) => {
      const mid = startVec.clone().add(endVec).multiplyScalar(0.5);
      const distance = startVec.distanceTo(endVec);
      mid.normalize().multiplyScalar(radius + distance * 0.35);

      const curve = new THREE.QuadraticBezierCurve3(startVec, mid, endVec);
      const points = curve.getPoints(40);
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.7,
        blending: THREE.AdditiveBlending,
      });
      return new THREE.Line(geometry, material);
    };

    const satPos1 = latLngToVector3(25.0, 65.0, radius);
    const satPos2 = latLngToVector3(5.0, 85.0, radius);
    const satPos3 = latLngToVector3(18.0, 72.0, radius);
    const satPos4 = latLngToVector3(10.0, 76.0, radius);

    orbitGroup.add(createArc(satPos1, satPos3, 0x38bdf8));
    orbitGroup.add(createArc(satPos3, satPos4, 0x06b6d4));
    orbitGroup.add(createArc(satPos2, satPos4, 0x10b981));

    // 4. Pin Markers on Globe
    const pinGroup = new THREE.Group();
    globeGroup.add(pinGroup);

    MARINE_PINS.forEach((pin) => {
      const pos = latLngToVector3(pin.lat, pin.lng, radius * 1.01);
      
      // Ring
      const ringGeo = new THREE.RingGeometry(0.04, 0.08, 24);
      const ringMat = new THREE.MeshBasicMaterial({
        color: pin.type === 'PFZ' ? 0x10b981 : pin.type === 'SST_FRONT' ? 0xf59e0b : 0x06b6d4,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.9,
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.position.copy(pos);
      ringMesh.lookAt(pos.clone().multiplyScalar(2));
      pinGroup.add(ringMesh);

      // Core point
      const dotGeo = new THREE.SphereGeometry(0.035, 12, 12);
      const dotMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const dotMesh = new THREE.Mesh(dotGeo, dotMat);
      dotMesh.position.copy(pos);
      pinGroup.add(dotMesh);
    });

    // 5. Interactive Drag & Rotation
    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - previousMousePosition.x;
      const deltaY = e.clientY - previousMousePosition.y;

      globeGroup.rotation.y += deltaX * 0.005;
      globeGroup.rotation.x = Math.max(-0.9, Math.min(0.9, globeGroup.rotation.x + deltaY * 0.005));

      previousMousePosition = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    // Resize
    const onResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    // Animation Loop
    let animId: number;
    const startTime = performance.now();

    const render = () => {
      animId = requestAnimationFrame(render);
      const elapsed = (performance.now() - startTime) * 0.001;

      // Continuous gentle auto-spin when not interacting
      if (!isDragging) {
        globeGroup.rotation.y += 0.0018;
      }

      globeMat.uniforms.uTime.value = elapsed;

      // Pulse pin rings
      pinGroup.children.forEach((child, idx) => {
        if (child instanceof THREE.Mesh && child.geometry instanceof THREE.RingGeometry) {
          const s = 1.0 + 0.3 * Math.sin(elapsed * 3.0 + idx);
          child.scale.set(s, s, s);
        }
      });

      // Layer visibility update
      orbitGroup.visible = mapLayersRef.current.drones;
      pinGroup.visible = mapLayersRef.current.pfz;

      renderer.render(scene, camera);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      sphereGeo.dispose();
      globeMat.dispose();
      haloGeo.dispose();
      haloMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div 
      className="relative w-full h-full flex items-center justify-center overflow-hidden"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* 3D Canvas Container */}
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Top Map HUD Overlay with Layer Toggles */}
      <div className="absolute top-4 left-4 right-4 flex items-center justify-between pointer-events-none z-10">
        <div className="flex items-center gap-2 pointer-events-auto">
          <div className="glass-panel px-3 py-1.5 rounded-lg flex items-center gap-2 text-xs font-mono text-cyan-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span>GEO-REF: 15°25'N, 73°45'E</span>
            <span className="text-slate-500">|</span>
            <span>INDIAN OCEAN BASIN</span>
          </div>
        </div>

        {/* Quick Map Layer Pills */}
        <div className="flex items-center gap-1.5 glass-panel p-1 rounded-xl pointer-events-auto">
          <button
            onClick={() => toggleMapLayer('pfz')}
            className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              mapLayers.pfz ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            PFZ Vector
          </button>
          <button
            onClick={() => toggleMapLayer('sst')}
            className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              mapLayers.sst ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            SST Thermal
          </button>
          <button
            onClick={() => toggleMapLayer('weather')}
            className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              mapLayers.weather ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
            Met-Ocean Wind
          </button>
          <button
            onClick={() => toggleMapLayer('drones')}
            className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              mapLayers.drones ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
            Surveillance
          </button>
        </div>
      </div>

      {/* Floating Tactical Callout Box (from Video 1 and 2) */}
      <div className="absolute bottom-6 left-6 z-10 pointer-events-auto max-w-sm">
        {selectedPin && (
          <div className="glass-panel p-4 rounded-xl border border-cyan-500/30 shadow-2xl backdrop-blur-xl animate-float">
            <div className="flex items-center justify-between pb-2 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <h4 className="text-xs font-bold font-mono tracking-wider text-cyan-300 uppercase">
                  {selectedPin.type} TELEMETRY
                </h4>
              </div>
              <span className="text-[11px] font-mono text-slate-400">{selectedPin.status}</span>
            </div>

            <div className="mt-3">
              <h3 className="text-sm font-semibold text-white">{selectedPin.name}</h3>
              <p className="text-xs text-slate-400 mt-0.5 font-mono">
                {selectedPin.lat.toFixed(2)}° N, {selectedPin.lng.toFixed(2)}° E
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-3 text-xs font-mono">
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-700/40">
                <span className="text-[10px] text-slate-400 uppercase">Sea Temp (SST)</span>
                <p className="text-sm font-bold text-amber-300 mt-0.5">{selectedPin.sst}</p>
              </div>
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-700/40">
                <span className="text-[10px] text-slate-400 uppercase">Wave Swell</span>
                <p className="text-sm font-bold text-cyan-300 mt-0.5">{selectedPin.wave}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() => setFocusedTarget('drone')}
                className="flex-1 py-1.5 px-2 text-xs font-medium rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-500/30 transition-colors flex items-center justify-center gap-1.5"
              >
                <Eye className="w-3.5 h-3.5" />
                Track Aerial Drone
              </button>
              <button
                onClick={() => setFocusedTarget('auv')}
                className="flex-1 py-1.5 px-2 text-xs font-medium rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 border border-emerald-500/30 transition-colors flex items-center justify-center gap-1.5"
              >
                <Compass className="w-3.5 h-3.5" />
                Track Sub AUV
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Target Sector Switcher */}
      <div className="absolute bottom-6 right-6 z-10 pointer-events-auto flex flex-col gap-1.5">
        <span className="text-[10px] font-mono uppercase text-slate-400 px-1">Tactical Stations</span>
        {MARINE_PINS.map((pin) => (
          <button
            key={pin.id}
            onClick={() => setSelectedPin(pin)}
            className={`px-3 py-1.5 text-xs font-mono rounded-lg transition-all text-left flex items-center justify-between gap-3 ${
              selectedPin?.id === pin.id
                ? 'bg-cyan-500/25 text-white border border-cyan-400/50 shadow-[0_0_12px_rgba(6,182,212,0.25)]'
                : 'glass-panel text-slate-300 hover:text-white hover:border-slate-500/40'
            }`}
          >
            <span>{pin.name.split(' ')[0]} Sector</span>
            <span className="text-[10px] text-cyan-400 font-semibold">{pin.sst}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
