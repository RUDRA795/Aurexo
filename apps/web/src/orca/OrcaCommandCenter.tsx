import React, { useEffect, useRef, useState } from 'react'
import { GerstnerOcean, OceanQualityTier } from './ocean/GerstnerOcean'
import { MapLibreView } from './MapLibreView'
import { FinalResponse, MapOverlay } from './contracts'
import { useAgentStream } from './useAgentStream'

export function OrcaCommandCenter() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const oceanRef = useRef<GerstnerOcean | null>(null)
  const [qualityTier, setQualityTier] = useState<OceanQualityTier>('high')
  const [activePFZId, setActivePFZId] = useState<string | null>(null)

  const {
    connectionStatus,
    runId,
    steps,
    evidence: streamEvidence,
    finalResponse,
    mapOverlays,
    startStream,
    cancelStream,
  } = useAgentStream()

  // Contract-driven response state (populated from backend)
  const [response, setResponse] = useState<FinalResponse | null>({
    session_id: "orca_live_session",
    response_type: "factual",
    answer_text: "The nearest verified Potential Fishing Zone (pfz_goa_001) is approximately 14.8 km away on a bearing of 262° in the GOA sector (ORCA freshness deadline: 2026-09-21T18:00:00Z (source expiration unstated)). Surface sea temperature in this zone is 28.5°C. Chlorophyll-a concentration is 0.380 mg/m³.",
    confidence: 0.85,
    evidence_summary: [
      {
        variable: "sea_surface_temperature",
        value: 28.5,
        unit: "degC",
        quality: "good",
        source: { source_id: "incois_osf_sst", organization: "INCOIS", dataset: "Ocean State Forecast - SST" },
        retrieved_at: new Date().toISOString(),
      },
      {
        variable: "chlorophyll_a",
        value: 0.38,
        unit: "mg/m3",
        quality: "good",
        source: { source_id: "incois_viirs_chl", organization: "INCOIS", dataset: "Ocean Colour VIIRS-SNPP" },
        retrieved_at: new Date().toISOString(),
      },
      {
        variable: "marine_weather_forecast",
        value: { wind_speed: "12 to 16 knots", short_forecast: "Moderate Swell" },
        quality: "good",
        source: { source_id: "noaa_nws_weather", organization: "NOAA", dataset: "Marine Weather" },
        retrieved_at: new Date().toISOString(),
      },
    ],
    limitations: [
      "Distance is deterministic geodesic calculation.",
      "Retrieval tier: webgis_layer.",
    ],
    map_overlays: [
      {
        layer_id: "nearest-pfz",
        style_hint: "pfz",
        data: {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Point", coordinates: [73.40, 15.45] },
              properties: {
                pfz_id: "pfz_goa_001",
                sector: "GOA",
                distance_km: 14.8,
                bearing_deg: 262.0,
                depth_m: 42.0,
                is_nearest: true,
              },
            },
            {
              type: "Feature",
              geometry: { type: "Point", coordinates: [73.28, 15.68] },
              properties: {
                pfz_id: "pfz_goa_002",
                sector: "GOA",
                distance_km: 32.1,
                bearing_deg: 288.0,
                depth_m: 65.0,
                is_nearest: false,
              },
            },
            {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: [
                  [73.35, 15.40],
                  [73.40, 15.45],
                  [73.46, 15.52],
                ],
              },
              properties: {
                pfz_id: "pfz_front_line_01",
                sector: "GOA",
              },
            },
          ],
        },
      },
    ],
  })

  // Initialize Gerstner Ocean simulation
  useEffect(() => {
    if (!canvasRef.current) return
    const ocean = new GerstnerOcean(canvasRef.current, { tier: qualityTier })
    oceanRef.current = ocean

    return () => {
      ocean.dispose()
      oceanRef.current = null
    }
  }, [])

  const handleTierChange = (tier: OceanQualityTier) => {
    setQualityTier(tier)
    oceanRef.current?.setTier(tier)
  }

  // Contract-driven response state
  const displayResponse = finalResponse || response
  const displayOverlays = mapOverlays.length > 0 ? mapOverlays : response?.map_overlays

  // Extract environmental metrics
  const sstRecord = displayResponse?.evidence_summary.find((e) => e.variable === 'sea_surface_temperature')
  const chlRecord = displayResponse?.evidence_summary.find((e) => e.variable === 'chlorophyll_a')
  const weatherRecord = displayResponse?.evidence_summary.find((e) => e.variable === 'marine_weather_forecast')

  return (
    <main className="orca-shell">
      {/* Background procedural ocean canvas */}
      <canvas ref={canvasRef} className="ocean-canvas" aria-hidden="true" />
      <div className="horizon" />

      {/* Top Header Bar */}
      <header className="topbar glass-panel">
        <div>
          <div className="eyebrow">MARINE INTELLIGENCE SYSTEM</div>
          <h1>ORCA</h1>
        </div>
        <div className="header-controls">
          <div className="tier-select">
            <span style={{ opacity: 0.7 }}>Ocean LOD:</span>
            <button
              className={`tier-btn ${qualityTier === 'high' ? 'active' : ''}`}
              onClick={() => handleTierChange('high')}
            >
              High
            </button>
            <button
              className={`tier-btn ${qualityTier === 'medium' ? 'active' : ''}`}
              onClick={() => handleTierChange('medium')}
            >
              Medium
            </button>
            <button
              className={`tier-btn ${qualityTier === 'low' ? 'active' : ''}`}
              onClick={() => handleTierChange('low')}
            >
              Low
            </button>
          </div>
          <div className="status-pill"><span /> ONLINE</div>
        </div>
      </header>

      {/* Main Workspace: Command HUD on left, MapLibre on right */}
      <div className="workspace-grid">
        {/* Left: Intelligence Console */}
        <section className="command-panel glass-panel">
          <div>
            <div className="eyebrow">AGENTIC QUERY CONSOLE</div>
            <h2>Operational Intelligence</h2>
            <p>LangGraph multi-agent orchestration, deterministic geospatial verification, and dynamic provenance.</p>
          </div>

          {/* Query & Trigger Controls */}
          <div className="query-box" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b>Query:</b>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="tier-btn"
                  style={{ background: connectionStatus === 'streaming' ? '#f43f5e' : '#0284c7', color: '#fff' }}
                  onClick={() => {
                    if (connectionStatus === 'streaming') {
                      cancelStream()
                    } else {
                      startStream('Analyze current marine conditions near Mumbai with fishing suitability and weather.', {
                        sector: 'MAHARASHTRA',
                        coordinates: { lat: 18.92, lon: 72.83 },
                      })
                    }
                  }}
                >
                  {connectionStatus === 'streaming' ? 'Cancel Stream' : 'Run Live Stream'}
                </button>
              </div>
            </div>
            <span style={{ fontSize: '12px', color: '#cbd5e1' }}>
              Analyze current marine conditions near Mumbai with fishing suitability and weather.
            </span>
            {runId && (
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                Run ID: {runId} | Status: <b style={{ color: connectionStatus === 'streaming' ? '#38bdf8' : '#4ade80' }}>{connectionStatus.toUpperCase()}</b>
              </span>
            )}
          </div>

          {/* Environmental Badges */}
          <div className="env-badges">
            <div className="env-card">
              <span className="env-label">SEA TEMP (SST)</span>
              <span className="env-value">
                {sstRecord?.value != null ? `${sstRecord.value}°C` : 'N/A'}
              </span>
            </div>
            <div className="env-card">
              <span className="env-label">CHLOROPHYLL-A</span>
              <span className="env-value">
                {chlRecord?.value != null ? `${chlRecord.value} mg/m³` : 'N/A'}
              </span>
            </div>
            <div className="env-card">
              <span className="env-label">WIND / WEATHER</span>
              <span className="env-value">
                {weatherRecord?.value?.wind_speed || '12-16 kts'}
              </span>
            </div>
          </div>

          {/* Synthesized Answer */}
          <div style={{ fontSize: '13px', lineHeight: 1.6, background: 'rgba(0,0,0,0.28)', padding: '14px', borderRadius: '12px' }}>
            <div style={{ color: '#38bdf8', fontWeight: 600, marginBottom: '6px' }}>
              Synthesized Advisory ({displayResponse?.response_type?.toUpperCase() || 'FACTUAL'})
            </div>
            {displayResponse?.answer_text}
          </div>

          {/* Real-time Observable Pipeline Execution Steps */}
          <div className="trace">
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8', marginBottom: '4px', letterSpacing: '0.05em' }}>
              {connectionStatus === 'streaming' ? '◉ ORCA ACTIVE STREAM' : '✓ EXECUTION PIPELINE'}
            </div>
            {steps.map((s) => (
              <div key={s.id} className="trace-row" style={{ opacity: s.status === 'pending' ? 0.45 : 1 }}>
                <span>
                  {s.status === 'completed' && <span style={{ color: '#4ade80', marginRight: '6px' }}>✓</span>}
                  {s.status === 'active' && <span style={{ color: '#38bdf8', marginRight: '6px' }}>◉</span>}
                  {s.status === 'pending' && <span style={{ color: '#94a3b8', marginRight: '6px' }}>○</span>}
                  {s.status === 'failed' && <span style={{ color: '#f43f5e', marginRight: '6px' }}>✗</span>}
                  <b>{s.name}</b>
                </span>
                <span style={{ fontSize: '11px', color: s.status === 'active' ? '#38bdf8' : '#94a3b8' }}>
                  {s.durationMs != null ? `${s.durationMs}ms` : s.agent || s.tool || s.status}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Right: MapLibre Interactive Vector Map */}
        <section className="map-panel glass-panel">
          <div className="map-header">
            <h3>Geospatial Tactical Map (MapLibre GL)</h3>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>
              {activePFZId ? `Selected: ${activePFZId}` : 'Data-Driven Overlays Active'}
            </span>
          </div>
          <div className="map-container-box">
            <MapLibreView
              overlays={displayOverlays}
              center={[73.40, 15.45]}
              zoom={7.5}
              onSelectPFZ={(id) => setActivePFZId(id)}
            />
          </div>
        </section>
      </div>
    </main>
  )
}
