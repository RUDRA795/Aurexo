import { useEffect, useRef } from 'react'
import * as THREE from 'three'

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

  useEffect(() => {
    if (!canvasRef.current) return
    return createOcean(canvasRef.current)
  }, [])

  return (
    <main className="orca-shell">
      <canvas ref={canvasRef} className="ocean-canvas" aria-hidden="true" />
      <div className="horizon" />
      <header className="topbar glass-panel">
        <div>
          <div className="eyebrow">MARINE INTELLIGENCE SYSTEM</div>
          <h1>ORCA</h1>
        </div>
        <div className="status-pill"><span /> ONLINE</div>
      </header>
      <section className="command-panel glass-panel">
        <div className="eyebrow">COMMAND CONSOLE</div>
        <h2>Ask the ocean.</h2>
        <p>Real data, agentic reasoning, deterministic geospatial analysis.</p>
        <div className="query-box">Where is the nearest Potential Fishing Zone today?</div>
        <div className="trace">
          <div className="trace-row"><b>SUPERVISOR</b><span>ready</span></div>
          <div className="trace-row"><b>PFZ</b><span>awaiting live adapter</span></div>
          <div className="trace-row"><b>GEOSPATIAL</b><span>deterministic</span></div>
        </div>
      </section>
    </main>
  )
}
