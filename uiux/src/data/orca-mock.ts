/**
 * Authentic Marine Datasets & Deterministic Event Stream for Testing
 * Strictly follows normalized OrcaBackendEvent shape matching OpenAPI specs.
 */

import { OrcaBackendEvent, MarineDataTelemetry } from '../types/orca';

export const INITIAL_TELEMETRY: MarineDataTelemetry = {
  sst: {
    current: 28.4,
    unit: '°C',
    trend: '+0.3°C / 24h',
    anomaly: +0.45,
    depthMeters: 1.0,
  },
  chlorophyll: {
    value: 0.82,
    status: 'Optimal',
  },
  pfz: {
    activeZonesCount: 4,
    nearestZoneDistanceKm: 24.8,
    bearingDegrees: 245,
    targetSpecies: ['Indian Mackerel (Rastrelliger kanagurta)', 'Sardinella longiceps', 'Yellowfin Tuna'],
    validUntil: '2026-09-25T18:00:00Z',
  },
  weather: {
    windSpeedKnots: 14.5,
    windDirection: 'WSW',
    waveHeightMeters: 1.4,
    swellPeriodSeconds: 8.2,
    seaCondition: 'Moderate',
  },
  surveillance: {
    aerialDrone: {
      callsign: 'ORCA-AERO-01',
      status: 'SCANNING',
      battery: 87,
      altitudeMeters: 450,
      speedKnots: 132,
      coordinates: [15.2993, 73.6245], // Off Goa
    },
    underwaterAuv: {
      callsign: 'ORCA-SUB-04',
      status: 'ACOUSTIC_SURVEY',
      depthMeters: 42.5,
      acousticTelemetryDb: 89.2,
      coordinates: [15.3412, 73.5821],
    },
  },
};

export interface MockScenario {
  id: string;
  title: string;
  query: string;
  description: string;
  region: string;
  events: OrcaBackendEvent[];
}

export const MOCK_SCENARIOS: MockScenario[] = [
  {
    id: 'pfz_goa_ratnagiri',
    title: 'PFZ Advisory & Thermal Front Analysis',
    query: 'Analyze Potential Fishing Zones (PFZ) and sea state safety off Ratnagiri - Goa coast for artisanal vessels',
    description: 'Autonomous multi-agent synthesis of INCOIS PFZ line vectors, MODIS chlorophyll concentration, and coastal wave hazards.',
    region: 'Central Arabian Sea (Goa-Konkan Shelf)',
    events: [
      {
        event: 'RUN_STARTED',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          query: 'Analyze Potential Fishing Zones (PFZ) and sea state safety off Ratnagiri - Goa coast for artisanal vessels',
        },
      },
      {
        event: 'TOOL_CALL',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          tool: 'query_pfz',
          input: { region: 'Goa-Ratnagiri', sector: 'Offshore 20-50nm', resolution: '1km' },
          output: {
            zonesFound: 2,
            coordinates: [
              { lat: 15.42, lng: 73.41, type: 'Thermal Front Boundary', depthM: 65 },
              { lat: 15.18, lng: 73.35, type: 'Chlorophyll Gradient Front', depthM: 78 }
            ],
            species: ['Pelagic Sardine', 'Carangids', 'Mackerel'],
            status: 'success'
          }
        },
      },
      {
        event: 'TOOL_CALL',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          tool: 'retrieve_sst',
          input: { source: 'INCOIS-AVHRR-OISST', coordinates: [15.3, 73.4] },
          output: {
            surfaceTempC: 28.2,
            gradientDeltaC: 1.1,
            anomaly: '+0.25 C',
            frontStrength: 'Pronounced Oceanic Front',
            status: 'success'
          }
        },
      },
      {
        event: 'TOOL_CALL',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          tool: 'check_weather',
          input: { source: 'IMD-INCOIS-WAVE-MODEL', coordinates: [15.3, 73.4] },
          output: {
            significantWaveHeightM: 1.35,
            swellPeriodSec: 7.8,
            windSpeedKn: 13.8,
            gustsKn: 17.2,
            safetyFlag: 'GREEN_SAFE_FOR_ALL_CRAFTS',
            status: 'success'
          }
        },
      },
      {
        event: 'TOOL_CALL',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          tool: 'search_advisories',
          input: { query: 'Ratnagiri Goa coastal navigation hazards & marine sanctuaries' },
          output: {
            advisories: [
              'No active severe weather warning in Konkan-Goa coastal zone.',
              'Netters advised to maintain 3nm clearance from Malvan Marine Sanctuary boundary.'
            ]
          }
        },
      },
      {
        event: 'EVIDENCE',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          evidence: {
            id: 'ev_pfz_771',
            source: 'INCOIS Marine Fishery Advisory System',
            sourceType: 'INCOIS_PFZ',
            title: 'Active Thermal & Ocean Color Intersection Vector',
            timestamp: new Date().toISOString(),
            coordinates: { lat: 15.38, lng: 73.38, name: 'Goa Coastal Shelf' },
            confidence: 0.94,
            verified: true,
            content: 'Synchronous thermal gradient (ΔT=1.1°C) and MODIS-Aqua chlorophyll plume (0.88 mg/m³) located 24.8 nautical miles west-southwest of Mormugao Port.',
            provenance: {
              agentId: 'agent_pfz_reasoner',
              tool: 'query_pfz',
              rawRecordId: 'INCOIS-PFZ-20260924-S04'
            }
          }
        },
      },
      {
        event: 'EVIDENCE',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          evidence: {
            id: 'ev_met_882',
            source: 'IMD Coastal Ocean Buoy Network (CB02)',
            sourceType: 'MET_OCEAN',
            title: 'In-Situ Sea State & Wave Telemetry',
            timestamp: new Date().toISOString(),
            coordinates: { lat: 15.4, lng: 73.5, name: 'Buoy CB02' },
            confidence: 0.98,
            verified: true,
            content: 'Significant wave height 1.35m with WSW swell 8.1s. Sea state scale 3 (Slight-Moderate). Favorable for 1-day artisanal and mechanized ventures.',
            provenance: {
              agentId: 'agent_hazard_evaluator',
              tool: 'check_weather',
              rawRecordId: 'BUOY-CB02-TELEM-0924'
            }
          }
        },
      },
      {
        event: 'RUN_COMPLETE',
        run_id: 'run_incois_pfz_01',
        timestamp: new Date().toISOString(),
        data: {
          verification: {
            status: 'VERIFIED',
            confidenceScore: 94,
            validationRings: [
              { name: 'Thermal Front Boundary Check', passed: true, detail: 'SST gradient confirmed across 3 consecutive satellite passes' },
              { name: 'Chlorophyll Bio-indicator Coincidence', passed: true, detail: 'MODIS chlorophyll plume aligns with thermal front within 2.4km' },
              { name: 'Met-Ocean Navigation Safety Gate', passed: true, detail: 'Swell height < 2.0m threshold; no gale force advisories' },
              { name: 'Marine Protected Area Exclusion', passed: true, detail: 'Zone is 14km seaward of protected marine conservation boundaries' }
            ],
            consistencyNote: 'High consensus between INCOIS PFZ telemetry and in-situ moored buoy validation.',
            lastVerifiedAt: new Date().toISOString()
          },
          response: `**ORCA Multi-Agent Synthesis Completed:**

1. **Recommended Potential Fishing Zone:**
   - **Primary Zone Coordinates:** 15°22.8' N, 73°22.8' E (24.8 nm WSW of Mormugao Harbor, Goa).
   - **Depth:** 65m - 78m along continental shelf break.
   - **Target Pelagic Species:** Indian Mackerel (*Rastrelliger kanagurta*) and Sardinella shoals.
   - **Confidence Score:** 94% (Verified via thermal SST gradient $\\Delta T = 1.1^\\circ\\text{C}$ and chlorophyll concentration $0.88\\,\\text{mg/m}^3$).

2. **Sea State & Navigational Clearance:**
   - **Significant Wave Height:** $1.35\\,\\text{m}$ (Moderate).
   - **Wind Vectors:** WSW at $13.8\\,\\text{knots}$, gusts under $18\\,\\text{knots}$.
   - **Safety Grade:** **SAFE TO DEPART**. Recommended return window prior to $18:00\\,\\text{IST}$ before tidal current slackening.

3. **Regulatory & Conservation Compliance:**
   - Vector path maintains a $>7.5\\,\\text{nm}$ buffer from designated coastal marine sanctuaries.`
        }
      }
    ]
  },
  {
    id: 'sst_thermal_anomaly',
    title: 'Offshore Thermal Anomaly & Upwelling Detection',
    query: 'Detect local upwelling signatures and thermocline depth shift along the coastal break',
    description: 'Deep-ocean sensory integration correlating underwater AUV acoustic telemetry with satellite SST anomalies.',
    region: 'Southwest Offshore Basin',
    events: [
      {
        event: 'RUN_STARTED',
        run_id: 'run_sst_upwell_02',
        timestamp: new Date().toISOString(),
        data: { query: 'Detect local upwelling signatures and thermocline depth shift along the coastal break' }
      },
      {
        event: 'TOOL_CALL',
        run_id: 'run_sst_upwell_02',
        timestamp: new Date().toISOString(),
        data: {
          tool: 'retrieve_sst',
          input: { highRes: true, layer: 'SST_ANOMALY' },
          output: { anomalyDetected: true, dropC: -1.4, location: [14.9, 73.1] }
        }
      },
      {
        event: 'TOOL_CALL',
        run_id: 'run_sst_upwell_02',
        timestamp: new Date().toISOString(),
        data: {
          tool: 'retrieve_chlorophyll',
          input: { sensor: 'OCEANSAT-3', spectralBand: '443-555nm' },
          output: { bioBloomIndex: 1.25, nutrientsEnriched: true }
        }
      },
      {
        event: 'EVIDENCE',
        run_id: 'run_sst_upwell_02',
        timestamp: new Date().toISOString(),
        data: {
          evidence: {
            id: 'ev_upwell_99',
            source: 'ORCA-SUB-04 In-Situ CTD Sensor',
            sourceType: 'INCOIS_SST',
            title: 'Thermocline Shoaling & Coastal Upwelling Front',
            timestamp: new Date().toISOString(),
            confidence: 0.96,
            verified: true,
            content: 'Rapid drop of 1.4°C detected at 35m depth accompanied by upward displacement of the mixed layer thermocline.',
            provenance: { agentId: 'agent_oceanography', tool: 'retrieve_sst' }
          }
        }
      },
      {
        event: 'RUN_COMPLETE',
        run_id: 'run_sst_upwell_02',
        timestamp: new Date().toISOString(),
        data: {
          verification: {
            status: 'VERIFIED',
            confidenceScore: 96,
            validationRings: [
              { name: 'Thermocline Depth Verification', passed: true, detail: 'In-situ AUV CTD matches Oceansat thermal profile' },
              { name: 'Nutrient Upwelling Index', passed: true, detail: 'Primary productivity surge confirmed' }
            ],
            consistencyNote: 'Active coastal upwelling confirmed. Biomass aggregation anticipated over next 36 hours.',
            lastVerifiedAt: new Date().toISOString()
          },
          response: `**Upwelling & Coastal Oceanography Brief:**
- Detected pronounced localized upwelling centered at **14°54' N, 73°06' E**.
- Surface temperature depression of **-1.4°C** with nutrient-rich thermocline shoaling to 32 meters.
- Marine biomass density projected to increase by 35% in adjacent sector within 24-48 hours.`
        }
      }
    ]
  }
];
