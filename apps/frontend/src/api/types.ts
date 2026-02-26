
export type LoopStep = { name: string; ts?: string };
export type LoopState = { strategic: LoopStep; tactical: LoopStep };
export type SystemState = { loop: LoopState; autonomy_tier: number; confidence: number };
export type MissionState = { id: string; name: string; status: string; agents: string[] };
export type AgentState = { id: string; name: string; role: string; status: string };
export type Evidence = { id: string; name: string; path: string; hash?: string; finalized: boolean; metadata?: Record<string,string> };

export type ScopeType = "narrow"|"standard"|"broad";
export type IntensityType = "low"|"medium"|"high";
export type ModeType = "plan"|"recon"|"validate";
export type MissionConfig = { id: string; name: string; scope: ScopeType; intensity: IntensityType; mode: ModeType; autonomy_tier: number; autonomous: boolean }
export type Recommendation = { id: string; title: string; rationale: string; tier: number; severity: 'blue'|'amber'|'red'; requires_approval: boolean; status: 'pending'|'approved'|'executed'|'blocked' }

export type RiskColor = 'green'|'amber'|'red'|'blue'|'gray'
export type EdgeKind = 'proven'|'hypothesis'|'active'
export type GraphNode = { id: string; label?: string; type?: string; risk: RiskColor; importance: number; role?: string }
export type GraphEdge = { id: string; source: string; target: string; kind: EdgeKind }
export type GraphSnapshot = { nodes: GraphNode[]; edges: GraphEdge[]; center_id?: string }

export type Severity = 'low'|'medium'|'high'|'critical';
export type Stage = 'discovered'|'validated'|'exploited'|'mitigated';
export type Status = 'open'|'in_progress'|'closed';
export type ChainPotential = 'low'|'medium'|'high';
export type Finding = { id:string; title:string; severity:Severity; type:string; target_asset:string; chain_value:number; chain_potential:ChainPotential; stage:Stage; status:Status; evidence_completeness:number };
export type MCPStatus = 'online'|'degraded'|'offline'|'blocked';
export type MCPServer = { id:string; name:string; status:MCPStatus; uptime_seconds:number; purpose:string };

export type Maturity = 'seed'|'growing'|'mature';
export type Plan = 'internal'|'rental'|'subscription';
export type Persona = { id:string; role:string; knowledge_count:number; last_training_update:string; confidence_trend:number[]; memory_source:'obsidian'; ingestion_policy:'distilled'; maturity:Maturity; rentable:boolean; plan:Plan };

export type LogCategory = 'plan'|'execution'|'evidence'|'governance'|'audit'|'metrics'|'learning';
export type LogType = 'decision_trace'|'reasoning_summary'|'evidence_links'|'knowledge_delta';
export type DecisionTraceEntry = { id:string; ts:string; gpee_step:'goal'|'plan'|'execute'|'evaluate'; ooda_step:'observe'|'orient'|'decide'|'act'; action:string; score:Record<string,any>; outcome:string; category:LogCategory; tags:string[] };
export type ReasoningSummary = { run_id:string; ts:string; title:string; bullets:string[]; categories:LogCategory[]; tags:string[] };
export type EvidenceLink = { id:string; ts:string; label:string; path:string; artifact_type:string; category:LogCategory; tags:string[] };
export type KnowledgeDeltaEntry = { id:string; ts:string; summary:string; impact_score:number; applies_to:string[]; category:LogCategory; tags:string[] };
export type LogIndex = { run_id:string; available:LogType[]; counts:Record<string,number> };
