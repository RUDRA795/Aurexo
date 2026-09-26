---
name: orca-webgl-shaders
description: Guides procedural GLSL shader authoring, WebGL scene configuration, and glTF 3D model loading for ORCA's ocean and aircraft visualization. Use when working on rendering/, apps/web/src/components/3d/, or shader files.
---

# ORCA WebGL & Ocean Shader Development

## 1. Core Mandate
> **Proxy videos, GIFs, and static imagery placeholders are prohibited.**
All maritime rendering must be rendered live via Three.js with real-time GLSL vertex and fragment shaders.

## 2. Ocean Shader Pipeline (Gerstner Waves)
- **Vertex Shader**: Computes multi-octave Gerstner wave displacement:
  - Displaces vertices horizontally and vertically based on wave steepness, wavelength, speed, and direction.
  - Computes dynamic analytical normals on the displaced surface for accurate lighting.
- **Fragment Shader**:
  - Blends deep ocean color, shallow water scatter, and peak foam masks.
  - Implements Fresnel approximation (`pow(1.0 - dot(normal, viewDir), 4.0)`) for realistic reflection and transparency.
  - Uses PBR-compatible specular highlights.

## 3. 3D Model Loading (glTF / GLB)
- Models are loaded via `GLTFLoader` (and `DRACOLoader` for compressed meshes).
- Aircraft models must support real-time coordinate and attitude updates (pitch, roll, yaw, altitude).
- Memory management: Dispose of geometries and materials on unmount.
