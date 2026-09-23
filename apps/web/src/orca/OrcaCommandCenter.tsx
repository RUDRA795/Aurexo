import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

type AgentState = 'idle' | 'processing' | 'complete'

const timeline = [
  ['01', 'Request received', 'complete'],
  ['02', 'Planning analysis', 'complete'],
  ['03', 'Querying PFZ data', 'active'],
  ['04', 'Retrieving SST', 'queued'],
  ['05', 'Checking weather', 'queued'],
]

const mapNodes = [
  { x: '29%', y: '34%', label: 'PFZ-07', tone: 'gold' },
  { x: '56%', y: '48%', label: 'PFZ-12', tone: 'cyan' },
  { x: '70%', y: '26%', label: 'SST', tone: 'violet' },
  { x: '42%', y: '67%', label: 'NOAA', tone: 'cyan' },
]

function createOcean(canvas: HTMLCanvasElement) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100)
  camera.position.set(0, 1.8, 5)

  const geometry = new THREE.PlaneGeometry(12, 8, 180, 120)
  const material = new THREE.ShaderMaterial({
    transparent: true,
    uniforms: { uTime: { value: 0 } },
    vertexShader: `
      uniform float uTime;
      varying float vWave;
      void main() {
        vec3 p = position;
        float wave = sin(p.x * 1.1 + uTime * 0.8) * 0.08
                   + sin(p.y * 1.7 + uTime * 1.1) * 0.04;
        p.z += wave;
        vWave = wave;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }
    `,
    fragmentShader: `
      varying float vWave;
      void main() {
        float fresnel = 0.5 + 0.5 * abs(vWave);
        gl_FragColor = vec4(0.03, 0.22 + fresnel * 0.08, 0.35 + fresnel * 0.18, 0.72);
      }
    `,
    side: THREE.DoubleSide,
  })
  const ocean = new THREE.Mesh(geometry, material)
  ocean.rotation.x = -Math.PI / 2.45
  scene.add(ocean)

  function resize() {
    const w = canvas.clientWidth || canvas.parentElement?.clientWidth || 1
    const h = canvas.clientHeight || canvas.parentElement?.clientHeight || 1
    renderer.setSize(w, h, false)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
  }

  let raf = 0
  const clock = new THREE.Clock()
  const render = () => {
    material.uniforms.uTime.value = clock.getElapsedTime()
    renderer.render(scene, camera)
    raf = requestAnimationFrame(render)
  }
  window.addEventListener('resize', resize)
  resize()
  render()

  return () => {
    cancelAnimationFrame(raf)
    window.removeEventListener('resize', resize)
    geometry.dispose()
    material.dispose()
    renderer.dispose()
  }
}

export function OrcaCommandCenter() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [agentState, setAgentState] = useState<AgentState>('idle')
  const [query, setQuery] = useState('')
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    if (!canvasRef.current) return
    return createOcean(canvasRef.current)
  }, [])

  const submitQuery = () => {
    if (!query.trim()) return
    setAgentState('processing')
    window.setTimeout(() => setAgentState('complete'), 2200)
  }

  return (
    <main className={`orca-shell state-${agentState}`}>
      <canvas ref={canvasRef} className="ocean-canvas" aria-hidden="true" />
      <div className="horizon" />
      <div className="grain" aria-hidden="true" />
      <header className="topbar glass-panel">
        <div className="brand"><div className="orca-mark">◒</div><div><div className="eyebrow">MARINE ECOSYSTEM REASONING</div><h1>ORCA <small>COMMAND CENTER</small></h1></div></div>
        <nav aria-label="Primary navigation"><button className="nav-active">Overview</button><button>Data layers</button><button>Provenance</button></nav>
        <div className="system-status"><span className="status-dot" /> <span>LIVE SYSTEM</span><i>UTC 14:32:08</i></div>
      </header>

      <section className="map-stage glass-panel" aria-label="Marine intelligence map">
        <div className="map-header"><div><div className="eyebrow">LIVE OCEAN INTELLIGENCE</div><h2>Arabian Sea / Western Shelf</h2></div><div className="map-tools"><button>⌖</button><button>＋</button><button>−</button></div></div>
        <div className="map-grid" />
        <div className="coastline coastline-one" /><div className="coastline coastline-two" />
        <div className="current current-one" /><div className="current current-two" />
        {mapNodes.map((node) => <div className={`map-node node-${node.tone}`} style={{ left: node.x, top: node.y }} key={node.label}><span /><label>{node.label}</label></div>)}
        <div className="map-legend"><span><i className="legend-gold" />Potential fishing zone</span><span><i className="legend-cyan" />Current vector</span><span><i className="legend-violet" />Satellite layer</span></div>
        <div className="coordinates">18° 42&apos; N&nbsp;&nbsp; 65° 18&apos; E <span>•</span> ZOOM 5.2</div>
      </section>

      <aside className="left-rail glass-panel"><div className="rail-title"><span className="pulse-ring" /> ORCA ACTIVE</div><div className="query-summary"><div className="eyebrow">CURRENT REQUEST</div><p>{query || 'Find suitable fishing zones near the western shelf.'}</p></div><div className="timeline">{timeline.map(([number, label, status]) => <div className={`timeline-row ${status}`} key={number}><b>{number}</b><span className="timeline-icon">{status === 'complete' ? '✓' : status === 'active' ? '◉' : '○'}</span><span>{label}</span></div>)}</div><div className="rail-footer"><span className="live-line" /> 3 agents connected</div></aside>

      <section className="command-panel glass-panel"><div className="eyebrow">COMMAND CONSOLE / 01</div><h2>Ask the ocean.</h2><p>Translate a question into verified marine intelligence.</p><div className="query-form"><input aria-label="Ask ORCA" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.nativeEvent.isComposing) submitQuery() }} placeholder="Ask about fishing zones, SST, weather..." /><button aria-label="Submit query" onClick={submitQuery}>↗</button></div><div className="trace"><span>⌁ INCOIS PFZ</span><span>⌁ SST / CHL</span><span>⌁ WEATHER</span></div></section>

      <aside className="metrics glass-panel"><div className="eyebrow">MARINE SIGNALS</div><div className="metric"><span>SST</span><strong>28.4°</strong><small>+0.8° <em>↑</em></small></div><div className="metric"><span>CHLOROPHYLL</span><strong>0.42</strong><small>mg/m³</small></div><div className="metric"><span>WIND</span><strong>12.6</strong><small>knots NE</small></div></aside>

      <button className={`avatar ${agentState}`} aria-label={chatOpen ? 'Close ORCA chat' : 'Open ORCA chat'} onClick={() => setChatOpen(!chatOpen)}><span className="avatar-core">◓</span><span className="avatar-label">ORCA AI</span></button>
      {chatOpen && <section className="chat-hud glass-panel"><header><div><div className="eyebrow">ORCA AI / ONLINE</div><strong>Marine intelligence assistant</strong></div><button aria-label="Close chat" onClick={() => setChatOpen(false)}>×</button></header><div className="chat-body"><div className="message orca-message">Hello. I&apos;m monitoring the Arabian Sea. What should we investigate?</div>{agentState !== 'idle' && <div className="message user-message">{query || 'Analyze the current fishing zones.'}</div>}{agentState === 'processing' && <div className="typing"><i /><i /><i /> Processing marine signals</div>}{agentState === 'complete' && <div className="message orca-message">Analysis complete. I found 3 candidate zones and verified the active satellite layers.</div>}</div><div className="chat-input"><input placeholder="Ask ORCA..." onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.nativeEvent.isComposing) submitQuery() }} /><button onClick={submitQuery}>↗</button></div></section>}
    </main>
  )
}
