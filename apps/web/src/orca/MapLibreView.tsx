import React, { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { Feature, Point } from 'geojson'
import { MapOverlay } from './contracts'

export interface MapLibreViewProps {
  overlays?: MapOverlay[]
  center?: [number, number] // [lon, lat]
  zoom?: number
  onSelectPFZ?: (pfzId: string) => void
}

const DEFAULT_MAP_STYLE = {
  version: 8 as const,
  sources: {
    'osm-tiles': {
      type: 'raster' as const,
      tiles: [
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: 'osm-tiles-layer',
      type: 'raster' as const,
      source: 'osm-tiles',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
}

export const MapLibreView: React.FC<MapLibreViewProps> = ({
  overlays = [],
  center = [73.5, 15.2], // West Coast India / Goa default
  zoom = 6.5,
  onSelectPFZ,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!mapContainerRef.current) return

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DEFAULT_MAP_STYLE,
      center: center,
      zoom: zoom,
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

    map.on('load', () => {
      // Setup GeoJSON Source
      map.addSource('orca-pfz-source', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      })

      // Add Line Layer (for PFZ line fronts / boundaries)
      map.addLayer({
        id: 'orca-pfz-lines',
        type: 'line',
        source: 'orca-pfz-source',
        filter: ['==', '$type', 'LineString'],
        paint: {
          'line-color': '#38bdf8',
          'line-width': 3,
          'line-opacity': 0.85,
        },
      })

      // Add Point Layer (for PFZ advisory coordinates)
      map.addLayer({
        id: 'orca-pfz-points',
        type: 'circle',
        source: 'orca-pfz-source',
        filter: ['==', '$type', 'Point'],
        paint: {
          'circle-radius': [
            'case',
            ['boolean', ['get', 'is_nearest'], false],
            9,
            6,
          ],
          'circle-color': [
            'case',
            ['boolean', ['get', 'is_nearest'], false],
            '#f59e0b', // Amber/Gold for nearest verified PFZ
            '#0284c7', // Cyan for other candidates
          ],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.95,
        },
      })

      // Click Interaction for Details
      map.on('click', 'orca-pfz-points', (e: maplibregl.MapLayerMouseEvent) => {
        if (!e.features || !e.features[0]) return
        const feature = e.features[0]
        const geom = feature.geometry
        if (geom.type !== 'Point') return

        const coords = geom.coordinates.slice() as [number, number]
        const props = (feature.properties || {}) as Record<string, any>

        new maplibregl.Popup({ offset: 12 })
          .setLngLat(coords)
          .setHTML(`
            <div style="font-family: sans-serif; font-size: 12px; color: #0f172a; padding: 4px;">
              <div style="font-weight: bold; color: #0369a1; margin-bottom: 2px;">
                PFZ: ${props.pfz_id || 'Unknown'}
              </div>
              <div><b>Sector:</b> ${props.sector || 'N/A'}</div>
              <div><b>Distance:</b> ${props.distance_km ? props.distance_km + ' km' : 'N/A'}</div>
              <div><b>Bearing:</b> ${props.bearing_deg ? props.bearing_deg + '°' : 'N/A'}</div>
              ${props.depth_m ? `<div><b>Depth:</b> ${props.depth_m} m</div>` : ''}
              ${props.is_nearest ? '<div style="color: #b45309; font-weight: bold; margin-top: 2px;">★ Nearest Verified Zone</div>' : ''}
            </div>
          `)
          .addTo(map)

        if (onSelectPFZ && props.pfz_id) {
          onSelectPFZ(props.pfz_id)
        }
      })

      // Cursor pointer styling on hover
      map.on('mouseenter', 'orca-pfz-points', () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'orca-pfz-points', () => {
        map.getCanvas().style.cursor = ''
      })

      mapInstanceRef.current = map
    })

    return () => {
      map.remove()
      mapInstanceRef.current = null
    }
  }, [])

  // Sync Data Overlays
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !map.isStyleLoaded()) return

    const source = map.getSource('orca-pfz-source') as maplibregl.GeoJSONSource
    if (!source) return

    const combinedFeatures: Feature[] = []
    for (const overlay of overlays) {
      if (overlay.data && overlay.data.features) {
        combinedFeatures.push(...overlay.data.features)
      }
    }

    source.setData({
      type: 'FeatureCollection',
      features: combinedFeatures,
    })

    // If features exist, zoom to fit bounds
    if (combinedFeatures.length > 0) {
      const bounds = new maplibregl.LngLatBounds()
      combinedFeatures.forEach((feat) => {
        if (feat.geometry.type === 'Point') {
          bounds.extend(feat.geometry.coordinates as [number, number])
        }
      })
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 40, maxZoom: 9, duration: 1000 })
      }
    }
  }, [overlays])

  return (
    <div
      ref={mapContainerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
    />
  )
}
