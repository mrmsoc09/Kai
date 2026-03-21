export interface IntelligenceMemory {
  memory_id: string;
  memory_type: string;
  scope: string;
  domain: string;
  ip?: string | null;
  tech_stack: string[];
  services: string[];
  tags: string[];
  confidence_score: number;
  validation_status: string;
  source_mission_id: string;
  mission_phase?: string | null;
  created_at: string;
  relationships: string[];
}

export interface IntelligenceMemoryListResponse {
  total: number;
  offset: number;
  limit: number;
  items: IntelligenceMemory[];
}

export interface IntelligenceRelationshipEdge {
  source: string;
  target: string;
  relationship_type: string;
  confidence_score: number;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface IntelligenceRelationshipsResponse {
  memory_id: string;
  outbound: IntelligenceRelationshipEdge[];
  inbound: IntelligenceRelationshipEdge[];
}

export interface IntelligenceStatsResponse {
  memory: Record<string, unknown>;
  graph: Record<string, unknown>;
}
