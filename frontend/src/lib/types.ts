/// Shared API types
export interface Region {
  id: string;
  name: string;
  kind: "country" | "state" | "city" | "pilot";
  center: { lon: number; lat: number };
  description: string;
}

export interface User {
  id: number;
  email: string;
  username: string;
  full_name: string;
  role: "admin" | "surveyor" | "viewer";
}

export interface Parcel {
  id: string;
  state_code: string;
  district_code: string;
  locality: string;
  footprint_geojson: { type: string; coordinates: number[][][] };
  centroid: { lon: number; lat: number };
  area_m2: number;
  bbox: number[] | null;
  source_type: string;
  status: string;
  property_count?: number;
  properties?: Property[];
}

export interface Property {
  id: string;
  ulpin: string | null;
  property_type: string;
  name: string;
  parcel_id: string | null;
  parent_id: string | null;
  footprint_geojson: { type: string; coordinates: number[][][] };
  zmin: number | null;
  zmax: number | null;
  height_m: number | null;
  area_m2: number;
  volume_m3: number | null;
  centroid: { lon: number; lat: number };
  status: string;
  source_type: string;
  source_name: string;
  model_name: string | null;
  model_version: string | null;
  confidence: number | null;
  verified: boolean;
  verification_time: string | null;
  version: number;
  created_at: string | null;
  updated_at: string | null;
  children?: Property[];
  child_count?: number | null;
}

export interface ValidationIssue {
  code: string;
  message: string;
  state: "PASS" | "WARNING" | "CONFLICT" | "ERROR";
  object_ids: string[];
  detail: Record<string, unknown>;
}

export interface ValidationSummary {
  state: string;
  counts: { PASS: number; WARNING: number; CONFLICT: number; ERROR: number };
  issue_count: number;
}

export interface ValidationRun {
  scope: string;
  summary: ValidationSummary;
  issues: ValidationIssue[];
}

export interface AiCandidate {
  ref_key: string;
  name: string;
  confidence: number | null;
  status: string;
  needs_verification: boolean;
}

export interface AiAnalysis {
  scope: string;
  summary: {
    objects_analysed: number;
    buildings: number;
    ai_candidates: number;
    anomalies: number;
  };
  anomalies: { type: string; severity: string; message: string }[];
  ai_candidates: AiCandidate[];
  recommended_verification: string[];
  disclaimer: string;
}

export interface AssistantAnswer {
  message: string;
  tool: string;
  tool_result: { tool: string; items: unknown[] };
  answer: string;
  offline: boolean;
  tools_available: string[];
  notice: string;
}
