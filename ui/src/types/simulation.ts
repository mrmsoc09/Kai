export type SimulationMode = 'graph_only' | 'tool_mock' | 'replay';

export interface SimulationRequest {
  workflow_id: string;
  program_id: string;
  mission_name?: string;
  mode: SimulationMode;
  scenario_pack?: string;
  targets: string[];
}

export interface SimulationResult {
  mission_id: string;
  mode: SimulationMode;
  status: string;
  is_live_blocked: boolean;
}

export interface SimulationScenariosResponse {
  scenarios: string[];
}

export interface SimulationCompareRequest {
  baseline_mission_id: string;
  variant_mission_id: string;
  metrics: string[];
}

export interface SimulationCompareResponse {
  comparison_id: string;
  baseline: Record<string, unknown>;
  variant: Record<string, unknown>;
  delta: string;
}
