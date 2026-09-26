import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useOrcaStore } from '../../lib/state/orca-store';

export const OceanCanvas: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { agentStatus, dayNightMode, focusedTarget } = useOrcaStore();

  const stateRef = useRef({
    agentStatus,
    dayNightMode,
    focusedTarget,
  });

  useEffect(() => {
    stateRef.current = { agentStatus, dayNightMode, focusedTarget };
  }, [agentStatus, dayNightMode, focusedTarget]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Renderer setup
    const renderer = new THREE.WebGLRenderer({
      powerPreference: 'high-performance',
      antialias: true,
      alpha: true,
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();

    // Camera
    const camera = new THREE.PerspectiveCamera(
      55,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 16, 28);
    camera.lookAt(0, 2, 0);

    // Fog
    const fogColorNight = new THREE.Color(0x020712);
    const fogColorDay = new THREE.Color(0xdbeafe);
    scene.fog = new THREE.FogExp2(fogColorDay, 0.015);

    // Ocean Wave Shader Material
    const oceanUniforms = {
      uTime: { value: 0 },
      uSpeed: { value: 0.8 },
      uTurbulence: { value: 1.0 },
      uDayNight: { value: 1.0 }, // 1.0 = day default
      uDeepColor: { value: new THREE.Color(0x044e6d) },
      uShallowColor: { value: new THREE.Color(0x0ea5e9) },
      uCrestColor: { value: new THREE.Color(0xe0f2fe) },
      uSpotlightPos: { value: new THREE.Vector3(0, 12, 0) },
    };

    const oceanVertexShader = `
      uniform float uTime;
      uniform float uSpeed;
      uniform float uTurbulence;
      varying vec3 vWorldPosition;
      varying vec3 vNormal;
      varying float vWaveHeight;

      // Procedural Gerstner-like Wave calculation
      float calculateWave(vec2 p) {
        float t = uTime * uSpeed;
        float w1 = sin(p.x * 0.18 + t * 1.2) * cos(p.y * 0.15 + t * 0.9) * 1.4;
        float w2 = sin(p.x * 0.35 - t * 1.5 + p.y * 0.25) * 0.7;
        float w3 = cos(p.x * 0.65 + p.y * 0.55 + t * 2.0) * 0.35;
        return (w1 + w2 + w3) * uTurbulence;
      }

      void main() {
        vec3 pos = position;
        float wave = calculateWave(pos.xy);
        pos.z += wave;
        vWaveHeight = wave;

        // Normal estimation
        float delta = 0.15;
        float waveX = calculateWave(pos.xy + vec2(delta, 0.0));
        float waveY = calculateWave(pos.xy + vec2(0.0, delta));
        vec3 normal = normalize(vec3(
          (wave - waveX) / delta,
          (wave - waveY) / delta,
          1.0
        ));
        vNormal = normalMatrix * normal;

        vec4 worldPos = modelMatrix * vec4(pos, 1.0);
        vWorldPosition = worldPos.xyz;
        gl_Position = projectionMatrix * viewMatrix * worldPos;
      }
    `;

    const oceanFragmentShader = `
      uniform vec3 uDeepColor;
      uniform vec3 uShallowColor;
      uniform vec3 uCrestColor;
      uniform float uDayNight;
      uniform vec3 uSpotlightPos;
      varying vec3 vWorldPosition;
      varying vec3 vNormal;
      varying float vWaveHeight;

      void main() {
        vec3 viewDir = normalize(cameraPosition - vWorldPosition);
        vec3 normal = normalize(vNormal);

        // Fresnel effect
        float fresnel = pow(1.0 - max(dot(viewDir, normal), 0.0), 3.5);

        // Depth & Height based color blend
        float heightFactor = smoothstep(-1.5, 2.0, vWaveHeight);
        
        vec3 nightColor = mix(uDeepColor, uShallowColor, heightFactor);
        nightColor = mix(nightColor, uCrestColor, smoothstep(1.3, 2.2, vWaveHeight) * 0.6);

        // Day palette
        vec3 dayDeep = vec3(0.03, 0.45, 0.62);
        vec3 dayShallow = vec3(0.14, 0.72, 0.82);
        vec3 dayCrest = vec3(0.95, 0.99, 1.0);
        vec3 dayColor = mix(dayDeep, dayShallow, heightFactor);
        dayColor = mix(dayColor, dayCrest, smoothstep(1.0, 1.8, vWaveHeight) * 0.85);

        vec3 baseColor = mix(nightColor, dayColor, uDayNight);

        // Volumetric Drone Spotlight Reflection
        float spotDist = length(vWorldPosition.xz - uSpotlightPos.xz);
        float spotlightIntensity = smoothstep(12.0, 1.0, spotDist) * (1.0 - uDayNight * 0.5);
        vec3 spotColor = vec3(0.15, 0.75, 1.0) * spotlightIntensity * 1.5;

        // Specular highlight
        vec3 lightDir = normalize(vec3(0.4, 0.8, 0.5));
        vec3 reflectDir = reflect(-lightDir, normal);
        float spec = pow(max(dot(viewDir, reflectDir), 0.0), 32.0);

        vec3 finalColor = baseColor + (uCrestColor * fresnel * 0.6) + spotColor + (vec3(spec) * 0.5);

        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    const oceanGeometry = new THREE.PlaneGeometry(160, 160, 128, 128);
    oceanGeometry.rotateX(-Math.PI / 2);

    const oceanMaterial = new THREE.ShaderMaterial({
      vertexShader: oceanVertexShader,
      fragmentShader: oceanFragmentShader,
      uniforms: oceanUniforms,
      wireframe: false,
    });

    const oceanMesh = new THREE.Mesh(oceanGeometry, oceanMaterial);
    oceanMesh.position.y = -2;
    scene.add(oceanMesh);

    // Drone Spotlight Cone (from Reference Video 2)
    const coneGeometry = new THREE.ConeGeometry(8, 24, 32, 1, true);
    coneGeometry.translate(0, -12, 0);
    const coneMaterial = new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.18,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const spotCone = new THREE.Mesh(coneGeometry, coneMaterial);
    spotCone.position.set(0, 18, 0);
    scene.add(spotCone);

    // Aerial Drone Model Mockup in 3D Space
    const droneGroup = new THREE.Group();
    const droneBody = new THREE.Mesh(
      new THREE.BoxGeometry(2.4, 0.3, 1.4),
      new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.85, roughness: 0.25 })
    );
    const droneWings = new THREE.Mesh(
      new THREE.BoxGeometry(6.5, 0.08, 0.9),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.9, roughness: 0.2 })
    );
    const droneBeacon = new THREE.Mesh(
      new THREE.SphereGeometry(0.15, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0x06b6d4 })
    );
    droneBeacon.position.set(0, -0.2, 0.4);
    droneGroup.add(droneBody);
    droneGroup.add(droneWings);
    droneGroup.add(droneBeacon);
    droneGroup.position.set(0, 18, 0);
    scene.add(droneGroup);

    // Atmospheric Marine Bioluminescent Particles
    const particleCount = 2000;
    const particleGeo = new THREE.BufferGeometry();
    const particlePos = new Float32Array(particleCount * 3);
    const particleScales = new Float32Array(particleCount);
    const particlePhases = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      particlePos[i * 3] = (Math.random() - 0.5) * 120;
      particlePos[i * 3 + 1] = Math.random() * 25 - 2;
      particlePos[i * 3 + 2] = (Math.random() - 0.5) * 120;
      particleScales[i] = Math.random() * 2.5 + 1.0;
      particlePhases[i] = Math.random() * Math.PI * 2;
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
    particleGeo.setAttribute('aScale', new THREE.BufferAttribute(particleScales, 1));
    particleGeo.setAttribute('aPhase', new THREE.BufferAttribute(particlePhases, 1));

    const particleMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(0x38bdf8) },
      },
      vertexShader: `
        uniform float uTime;
        attribute float aScale;
        attribute float aPhase;
        varying float vAlpha;
        void main() {
          vec3 p = position;
          // slow marine drift
          p.x += sin(uTime * 0.4 + aPhase) * 1.5;
          p.y += cos(uTime * 0.3 + aPhase) * 0.8;
          p.z += sin(uTime * 0.2 + aPhase) * 1.2;

          vAlpha = 0.35 + 0.45 * sin(uTime * 1.5 + aPhase);
          vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
          gl_PointSize = aScale * (120.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying float vAlpha;
        void main() {
          float dist = length(gl_PointCoord - vec2(0.5));
          if (dist > 0.5) discard;
          float strength = 1.0 - smoothstep(0.0, 0.5, dist);
          gl_FragColor = vec4(uColor, strength * vAlpha);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // Energy Current Splines (Data flows across ocean)
    const curvePoints: THREE.Vector3[][] = [
      [
        new THREE.Vector3(-35, -0.5, -20),
        new THREE.Vector3(-15, 0.5, -5),
        new THREE.Vector3(5, -0.2, 10),
        new THREE.Vector3(30, 0.8, 25),
      ],
      [
        new THREE.Vector3(30, -0.8, -25),
        new THREE.Vector3(12, 0.3, -8),
        new THREE.Vector3(-8, -0.3, 8),
        new THREE.Vector3(-32, 0.4, 20),
      ]
    ];

    const splineMeshes: THREE.Mesh[] = [];
    curvePoints.forEach((pts) => {
      const curve = new THREE.CatmullRomCurve3(pts);
      const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.12, 8, false);
      const tubeMat = new THREE.MeshBasicMaterial({
        color: 0x06b6d4,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending,
      });
      const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
      scene.add(tubeMesh);
      splineMeshes.push(tubeMesh);
    });

    // Ambient & Directional Lights
    const ambientLight = new THREE.AmbientLight(0x0c2540, 1.5);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0x38bdf8, 1.8);
    dirLight.position.set(20, 40, 20);
    scene.add(dirLight);

    // Mouse Tracking for Parallax
    let mouseX = 0;
    let mouseY = 0;
    const handleMouseMove = (e: MouseEvent) => {
      mouseX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener('mousemove', handleMouseMove);

    // Resize Handler
    const handleResize = () => {
      if (!container) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    window.addEventListener('resize', handleResize);

    // Animation Loop
    let animationFrameId: number;
    const startTime = performance.now();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      const elapsedTime = (performance.now() - startTime) * 0.001;
      const { agentStatus: currentStatus, dayNightMode: currentDayNight, focusedTarget: currentFocus } = stateRef.current;

      // Speed & turbulence multiplier based on agent status
      let targetSpeed = 0.8;
      let targetTurbulence = 1.0;
      let targetSpotIntensity = 0.18;

      if (currentStatus === 'planning' || currentStatus === 'querying_pfz' || currentStatus === 'retrieving_sst') {
        targetSpeed = 1.4;
        targetTurbulence = 1.35;
        targetSpotIntensity = 0.35;
      } else if (currentStatus === 'verifying') {
        targetSpeed = 1.8;
        targetTurbulence = 1.6;
        targetSpotIntensity = 0.45;
      }

      oceanUniforms.uTime.value = elapsedTime;
      oceanUniforms.uSpeed.value = targetSpeed;
      oceanUniforms.uTurbulence.value = targetTurbulence;
      particleMat.uniforms.uTime.value = elapsedTime;

      // Day / Night transition
      const targetDayVal = currentDayNight === 'day' ? 1.0 : 0.0;
      oceanUniforms.uDayNight.value += (targetDayVal - oceanUniforms.uDayNight.value) * 0.05;
      scene.fog?.color.lerp(currentDayNight === 'day' ? fogColorDay : fogColorNight, 0.05);

      // Drone flight & spotlight scanning motion (from Video 2)
      const droneOrbitRadius = 14;
      const droneAngle = elapsedTime * 0.35;
      const droneX = Math.cos(droneAngle) * droneOrbitRadius;
      const droneZ = Math.sin(droneAngle) * (droneOrbitRadius * 0.65) - 4;
      const droneY = 16 + Math.sin(elapsedTime * 0.8) * 0.8;

      droneGroup.position.set(droneX, droneY, droneZ);
      droneGroup.rotation.y = -droneAngle + Math.PI / 2;
      droneGroup.rotation.z = Math.sin(elapsedTime * 1.2) * 0.08;

      // Spotlight tracking
      spotCone.position.set(droneX, droneY - 0.4, droneZ);
      spotCone.rotation.z = Math.sin(elapsedTime * 0.7) * 0.15;
      spotCone.rotation.x = Math.cos(elapsedTime * 0.6) * 0.12;
      coneMaterial.opacity = targetSpotIntensity;

      // Ocean spotlight reflection pos
      oceanUniforms.uSpotlightPos.value.set(droneX, 0, droneZ);

      // Camera choreography based on focus target
      let targetCamX = mouseX * 2.5;
      let targetCamY = 16 + mouseY * 1.5;
      let targetCamZ = 28;

      if (currentFocus === 'drone') {
        targetCamX = droneX + 6;
        targetCamY = droneY + 4;
        targetCamZ = droneZ + 12;
      } else if (currentFocus === 'auv') {
        targetCamX = 0;
        targetCamY = 5;
        targetCamZ = 16;
      }

      camera.position.x += (targetCamX - camera.position.x) * 0.04;
      camera.position.y += (targetCamY - camera.position.y) * 0.04;
      camera.position.z += (targetCamZ - camera.position.z) * 0.04;

      if (currentFocus === 'drone') {
        camera.lookAt(droneGroup.position);
      } else {
        camera.lookAt(0, 2, 0);
      }

      // Spline pulse
      splineMeshes.forEach((mesh, idx) => {
        const mat = mesh.material as THREE.MeshBasicMaterial;
        mat.opacity = 0.3 + 0.35 * Math.sin(elapsedTime * 2.5 + idx * 1.8);
      });

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      oceanGeometry.dispose();
      oceanMaterial.dispose();
      coneGeometry.dispose();
      coneMaterial.dispose();
      particleGeo.dispose();
      particleMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 pointer-events-none z-0 overflow-hidden"
      style={{ opacity: 0.95 }}
    />
  );
};
