/**
 * ORCA — Marine EcOsystem Reasoning with Collaborative Agents
 * TypeScript Contract Definitions matching OpenAPI and SSE Specs
 */

export type AgentStatus = 
  | 'idle'
  | 'listening'
  | 'planning'
  | 'querying_pfz'
  | 'retrieving_sst'
  | 'checking_weather'
  | 'retrieving_chlorophyll'
  | 'searching_advisories'
  | 'geofencing'
  | 'routing'
  | 'verifying'
  | 'synthesizing'
  | 'complete'
  | 'error';

export type BackendEventType = 
  // Authoritative Backend Events
  | 'RUN_STARTED'
  | 'RUN_COMPLETED'
  | 'RUN_FAILED'
  | 'RUN_CANCELLED'
  | 'PLAN_CREATED'
  | 'AGENT_STARTED'
  | 'AGENT_COMPLETED'
  | 'TOOL_STARTED'
  | 'TOOL_COMPLETED'
  | 'RETRY'
  | 'FALLBACK'
  | 'EVIDENCE_ADDED'
  | 'EVIDENCE_CHECK'
  | 'SYNTHESIS_STARTED'
  | 'SYNTHESIS_COMPLETED'
  | 'MAP_OVERLAY_UPDATED'
  | 'HEARTBEAT'
  // Real-time Web Search & Deep Research Events
  | 'RESEARCH_STARTED'
  | 'SEARCH_QUERY'
  | 'SEARCH_RESULT'
  | 'SOURCE_OPENED'
  | 'SOURCE_ADDED'
  | 'DATA_SOURCE_STARTED'
  | 'DATA_SOURCE_COMPLETED'
  | 'EVIDENCE_MERGED'
  | 'EVIDENCE_CONFLICT'
  | 'RESEARCH_PROGRESS'
  | 'RESEARCH_COMPLETED'
  | 'CITATION_ADDED'
  // Simulation / Backward compatibility
  | 'TOOL_CALL'
  | 'EVIDENCE'
  | 'RUN_COMPLETE';

export interface PlanStepItem {
  id: string;
  name: string;
  agent?: string;
  tool?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed';
}

export interface MapOverlayPayload {
  overlay_id?: string;
  layer_type?: string;
  type?: string;
  source_id?: string;
  source?: string;
  feature_count?: number;
  count?: number;
  selected_id?: string;
  coordinates?: [number, number]; // [lon, lat]
  center?: { lat: number; lng: number };
  distance_km?: number;
  bearing_deg?: number;
  restricted?: boolean;
  hazard_level?: 'low' | 'moderate' | 'high' | 'severe';
  route_waypoints?: Array<{ lat: number; lng: number; label?: string }>;
  boundaries?: Array<{ name: string; type: string; coordinates: Array<[number, number]>; distance_nm?: number; alert?: boolean }>;
  alerts?: string[];
  features?: any[];
  [key: string]: any;
}


export interface ToolCallPayload {
  tool: string;
  input: Record<string, any>;
  output?: Record<string, any>;
  status: 'running' | 'completed' | 'failed';
  timestamp: string;
  durationMs?: number;
}

export interface CitationItem {
  title: string;
  url: string;
  domain: string;
  badge?: 'WEB SEARCH' | 'MARINE DATA' | 'SCIENTIFIC SOURCE' | 'OFFICIAL ADVISORY' | string;
  published_date?: string;
  retrieved_at?: string;
  snippet?: string;
  freshness?: 'LIVE' | 'RECENT' | 'STALE' | 'OLD' | 'FORECAST' | 'HISTORICAL' | string;
}

export interface EvidenceItem {
  id: string;
  source: string;
  sourceType: 'INCOIS_PFZ' | 'INCOIS_SST' | 'NOAA_GFS' | 'MODIS_AQUA' | 'COAST_GUARD' | 'MET_OCEAN' | 'OPEN_METEO' | 'COPERNICUS' | 'NOAA_NDBC' | 'WEB_GROUNDING' | string;
  title: string;
  timestamp: string;
  coordinates?: { lat: number; lng: number; name?: string };
  confidence: number; // 0 to 1
  verified: boolean;
  content: string;
  url?: string;
  domain?: string;
  provider?: string;
  badge?: string;
  freshness?: string;
  conflict?: {
    isConflict: boolean;
    spreadSummary?: string;
    resolution?: string;
    preferredSource?: string;
  };
  provenance: {
    agentId: string;
    tool: string;
    rawRecordId?: string;
  };
}

export interface VerificationResult {
  status: 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'CONFLICT_DETECTED' | 'UNVERIFIED' | 'FAILED';
  confidenceScore: number; // 0-100
  validationRings: {
    name: string;
    passed: boolean;
    detail: string;
  }[];
  consistencyNote: string;
  lastVerifiedAt: string;
}

export interface ProvenanceNode {
  id: string;
  label: string;
  type: 'query' | 'agent' | 'tool' | 'source' | 'fusion' | 'verification' | 'response';
  status: 'pending' | 'active' | 'completed' | 'failed';
  meta?: Record<string, any>;
}

export interface ProvenanceEdge {
  from: string;
  to: string;
  label?: string;
}

export interface MarineDataTelemetry {
  sst: {
    current: number; // e.g. 28.4 C
    unit: string;
    trend: string;
    anomaly: number;
    depthMeters: number;
  };
  chlorophyll: {
    value: number; // e.g. 0.84 mg/m3
    status: 'Optimal' | 'Moderate' | 'Low' | 'High';
  };
  pfz: {
    activeZonesCount: number;
    nearestZoneDistanceKm: number;
    bearingDegrees: number;
    targetSpecies: string[];
    validUntil: string;
  };
  weather: {
    windSpeedKnots: number;
    windDirection: string;
    waveHeightMeters: number;
    swellPeriodSeconds: number;
    seaCondition: 'Calm' | 'Moderate' | 'Rough' | 'Severe';
  };
  surveillance: {
    aerialDrone: {
      callsign: string;
      status: 'PATROLLING' | 'SCANNING' | 'TRANSIT';
      battery: number;
      altitudeMeters: number;
      speedKnots: number;
      coordinates: [number, number];
    };
    underwaterAuv: {
      callsign: string;
      status: 'DIVING' | 'ACOUSTIC_SURVEY' | 'IDLE';
      depthMeters: number;
      acousticTelemetryDb: number;
      coordinates: [number, number];
    };
  };
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'orca' | 'system';
  content: string;
  timestamp: string;
  toolCalls?: ToolCallPayload[];
  evidenceIds?: string[];
  verification?: VerificationResult;
  isStreaming?: boolean;
  citations?: CitationItem[];
  conflictNotices?: Array<{
    variable: string;
    spread_summary: string;
    resolution: string;
  }>;
  agreementNotices?: Array<{
    variable: string;
    source_1: string;
    value_1: any;
    source_2: string;
    value_2: any;
    preferred_source: string;
  }>;
  researchStatus?: {
    mode?: 'FAST' | 'DEEP_RESEARCH';
    topic?: string;
    step?: string;
    sourcesCount?: number;
    reportTitle?: string;
  };
}

export interface OrcaBackendEvent {
  event: BackendEventType;
  run_id: string;
  timestamp: string;
  event_id?: string;
  sequence?: number;
  node?: string;
  agent?: string;
  tool?: string;
  status?: string;
  duration_ms?: number;
  error_code?: string;
  progress?: number;
  payload?: Record<string, any>;
  data: {
    query?: string;
    tool?: string;
    agent?: string;
    node?: string;
    status?: string;
    input?: Record<string, any>;
    output?: Record<string, any>;
    evidence?: EvidenceItem;
    verification?: VerificationResult;
    response?: string;
    answer_text?: string;
    error?: string;
    plan?: PlanStepItem[];
    overlay?: MapOverlayPayload;
    payload?: Record<string, any>;
    [key: string]: any;
  };
}
