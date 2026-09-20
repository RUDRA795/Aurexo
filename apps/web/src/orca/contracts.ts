import type { FeatureCollection } from 'geojson';

export interface Geometry {
  lat: number;
  lon: number;
}

export interface PFZPointProperties {
  pfz_id: string;
  sector: string;
  distance_km: number;
  bearing_deg: number;
  depth_m?: number;
  is_nearest?: boolean;
}

export interface MapOverlay {
  layer_id: string;
  data: FeatureCollection;
  style_hint: string;
}

export interface EvidenceRecord {
  variable: string;
  value: any;
  unit?: string;
  quality: string;
  source: {
    source_id: string;
    organization: string;
    dataset: string;
  };
  retrieved_at: string;
}

export interface FinalResponse {
  session_id: string;
  response_type: "factual" | "refusal" | "error" | "unavailable";
  answer_text: string;
  confidence: number;
  evidence_summary: EvidenceRecord[];
  limitations: string[];
  map_overlays: MapOverlay[];
}
