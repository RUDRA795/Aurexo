import * as THREE from 'three'

export type OceanQualityTier = 'high' | 'medium' | 'low'

export interface OceanOptions {
  tier?: OceanQualityTier
}

/**
 * Procedural Gerstner-wave ocean background implemented with WebGL shaders in Three.js.
 * Strictly procedural without video or GIF proxies; features LOD quality tiers.
 */
export class GerstnerOcean {
  private renderer: THREE.WebGLRenderer
  private scene: THREE.Scene
  private camera: THREE.PerspectiveCamera
  private mesh: THREE.Mesh
  private material: THREE.ShaderMaterial
  private geometry: THREE.PlaneGeometry
  private clock: THREE.Clock
  private rafId: number = 0
  private canvas: HTMLCanvasElement
  private tier: OceanQualityTier

  constructor(canvas: HTMLCanvasElement, options: OceanOptions = {}) {
    this.canvas = canvas
    this.tier = options.tier || 'high'
    this.clock = new THREE.Clock()

    // 1. WebGL Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: this.tier !== 'low',
      alpha: true,
      powerPreference: this.tier === 'high' ? 'high-performance' : 'default',
    })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, this.tier === 'low' ? 1.0 : 2.0))

    // 2. Scene and Camera
    this.scene = new THREE.Scene()
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
    this.camera.position.set(0, 2.2, 5.5)
    this.camera.lookAt(0, 0, 0)

    // 3. Grid LOD segments
    const segments = this.tier === 'high' ? { x: 160, y: 100 } : this.tier === 'medium' ? { x: 80, y: 50 } : { x: 24, y: 16 }
    this.geometry = new THREE.PlaneGeometry(16, 12, segments.x, segments.y)

    // 4. Custom Gerstner Wave Shader Material
    this.material = new THREE.ShaderMaterial({
      transparent: true,
      uniforms: {
        uTime: { value: 0.0 },
        uQuality: { value: this.tier === 'high' ? 2.0 : this.tier === 'medium' ? 1.0 : 0.0 },
      },
      vertexShader: `
        uniform float uTime;
        uniform float uQuality;
        varying vec3 vWorldPos;
        varying vec3 vNormal;
        varying float vHeight;

        // Gerstner wave displacement function
        vec3 gerstnerWave(vec2 dir, float steepness, float wavelength, float speed, vec2 p, float time, inout vec3 tangent, inout vec3 binormal) {
          float k = 2.0 * 3.14159265 / wavelength;
          float c = sqrt(9.8 / k) * speed;
          vec2 d = normalize(dir);
          float f = k * (dot(d, p) - c * time);
          float a = steepness / k;

          tangent += vec3(
            -d.x * d.x * (steepness * sin(f)),
            d.x * (steepness * cos(f)),
            -d.x * d.y * (steepness * sin(f))
          );
          binormal += vec3(
            -d.x * d.y * (steepness * sin(f)),
            d.y * (steepness * cos(f)),
            -d.y * d.y * (steepness * sin(f))
          );

          return vec3(
            d.x * (a * cos(f)),
            a * sin(f),
            d.y * (a * cos(f))
          );
        }

        void main() {
          vec3 p = position;
          vec3 gridPoint = position;
          vec3 tangent = vec3(1.0, 0.0, 0.0);
          vec3 binormal = vec3(0.0, 0.0, 1.0);

          // Component Wave 1 (Primary swell)
          p += gerstnerWave(vec2(1.0, 0.2), 0.16, 3.8, 0.85, gridPoint.xy, uTime, tangent, binormal);

          // Component Wave 2 (Cross swell)
          if (uQuality >= 1.0) {
            p += gerstnerWave(vec2(0.6, 0.8), 0.10, 2.2, 1.10, gridPoint.xy, uTime, tangent, binormal);
          }

          // Component Wave 3 (High-frequency capillary wave)
          if (uQuality >= 2.0) {
            p += gerstnerWave(vec2(-0.4, 0.9), 0.06, 1.1, 1.40, gridPoint.xy, uTime, tangent, binormal);
            p += gerstnerWave(vec2(0.8, -0.3), 0.04, 0.7, 1.80, gridPoint.xy, uTime, tangent, binormal);
          }

          vec3 normal = normalize(cross(binormal, tangent));
          vNormal = normal;
          vHeight = p.z;
          vWorldPos = (modelMatrix * vec4(p, 1.0)).xyz;

          gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vWorldPos;
        varying vec3 vNormal;
        varying float vHeight;

        void main() {
          // Deep ocean palette
          vec3 deepColor = vec3(0.015, 0.08, 0.16);
          vec3 surfaceColor = vec3(0.03, 0.28, 0.42);
          vec3 foamColor = vec3(0.70, 0.88, 0.95);

          // Lighting and view vector
          vec3 viewDir = normalize(cameraPosition - vWorldPos);
          vec3 lightDir = normalize(vec3(0.3, 1.0, 0.5));

          // Fresnel reflection calculation
          float fresnel = pow(1.0 - max(dot(viewDir, vNormal), 0.0), 3.0);

          // Sun specular glint
          vec3 halfVector = normalize(lightDir + viewDir);
          float spec = pow(max(dot(vNormal, halfVector), 0.0), 64.0);

          // Blend water color based on wave height and Fresnel
          vec3 water = mix(deepColor, surfaceColor, smoothstep(-0.4, 0.4, vHeight));
          water += spec * 0.4;
          water = mix(water, foamColor, smoothstep(0.3, 0.5, vHeight) * 0.25);
          water += fresnel * 0.18;

          gl_FragColor = vec4(water, 0.85);
        }
      `,
      side: THREE.DoubleSide,
    })

    this.mesh = new THREE.Mesh(this.geometry, this.material)
    this.mesh.rotation.x = -Math.PI / 2.35
    this.scene.add(this.mesh)

    this.handleResize = this.handleResize.bind(this)
    window.addEventListener('resize', this.handleResize)
    this.handleResize()
    this.startAnimation()
  }

  private handleResize() {
    const w = this.canvas.clientWidth || this.canvas.parentElement?.clientWidth || window.innerWidth
    const h = this.canvas.clientHeight || this.canvas.parentElement?.clientHeight || window.innerHeight
    this.renderer.setSize(w, h, false)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  private startAnimation() {
    const loop = () => {
      this.material.uniforms.uTime.value = this.clock.getElapsedTime()
      this.renderer.render(this.scene, this.camera)
      this.rafId = requestAnimationFrame(loop)
    }
    loop()
  }

  public setTier(tier: OceanQualityTier) {
    this.tier = tier
    this.material.uniforms.uQuality.value = tier === 'high' ? 2.0 : tier === 'medium' ? 1.0 : 0.0
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, tier === 'low' ? 1.0 : 2.0))
  }

  public dispose() {
    cancelAnimationFrame(this.rafId)
    window.removeEventListener('resize', this.handleResize)
    this.geometry.dispose()
    this.material.dispose()
    this.renderer.dispose()
  }
}
