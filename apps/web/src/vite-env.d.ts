/// <reference types="vite/client" />
declare module '*.css'
declare module 'maplibre-gl/dist/maplibre-gl.css'
declare module 'three' {
  export const WebGLRenderer: any
  export const Scene: any
  export const PerspectiveCamera: any
  export const PlaneGeometry: any
  export const ShaderMaterial: any
  export const Mesh: any
  export const Clock: any
  export const DoubleSide: any
}
