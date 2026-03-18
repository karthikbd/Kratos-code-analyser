/** WebSocket event types streamed from FastAPI backend */

export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed' | 'skipped';

export interface AgentDef {
  id: string;
  name: string;
  layer: number;
  description: string;
  regulation: string;
  status: AgentStatus;
  findings: Finding[];
  finding_counts: Record<string, number>;
  duration_ms: number;
  error?: string;
}

export interface Finding {
  finding_id: string;
  title: string;
  description: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  status: string;
  layer: string;
  cfr_reference: string;
  it_guide_reference: string;
  remediation_recommendation: string;
  orc_type?: string;
  affected_accounts?: string[];
  expected_behavior?: string;
  observed_behavior?: string;
  evidence?: Record<string, string>;
  source_file?: string;
  line_number?: number;
  code_snippet?: string;
}

export interface PipelineSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  total_controls: number;
  controls_passed: number;
  controls_failed: number;
  verdict: 'PASS' | 'REVIEW' | 'FAIL';
}

/* ── Control Library Types ─────────────────────────────────────────────── */

export type ControlStatus = 'not_tested' | 'pass' | 'fail' | 'partial' | 'not_applicable';

export interface FDICControl {
  control_id: string;
  title: string;
  description: string;
  regulation: string;
  section: string;
  category: string;
  severity: string;
  layer: number;
  layer_name: string;
  status: ControlStatus;
  rag_validated: boolean;
  rag_citation: string;
  finding_ids: string[];
  analysis_status?: 'PASS' | 'FAIL' | 'NOT_RUN' | 'NOT_APPLICABLE';
  applicable?: boolean;
}

export interface ControlSummary {
  total_controls: number;
  by_regulation: Record<string, number>;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  by_layer: Record<string, number>;
  controls_passed?: number;
  controls_failed?: number;
  total_findings?: number;
  verdict?: string;
  analyzed_system?: string;
  analyzed_at?: string;
  capabilities?: { orc_types: string[]; features: string[] };
}

export interface ControlValidationResult {
  control_id: string;
  title: string;
  regulation: string;
  section: string;
  rag_validated: boolean;
  rag_citation: string;
  category: string;
  severity: string;
  layer: number;
}

export interface ControlValidationResponse {
  total: number;
  validated: number;
  coverage_pct: number;
  results: ControlValidationResult[];
  error?: string;
}

/* ── RAG Control Types ───────────────────────────────────────────────── */

export interface RagControl {
  section: string;
  title?: string;
  description?: string;
  severity: string;
  regulation: string;
  code_references: { file: string; line: number; text: string; match_type?: string; keywords?: string[] }[];
}

export interface RagComparisonData {
  /** Total FDIC sections extracted from regulatory documents */
  total_sections: number;
  /** Sections that are addressed / referenced in the source code */
  found_in_code: number;
  /** Sections with no meaningful reference in the source code */
  gaps_count: number;
  /** found_in_code / total_sections × 100 */
  code_coverage_pct: number;
  /** Sections missing from code — the gaps to fix */
  gap_sections: RagControl[];
  /** Sections found in code */
  found_sections: RagControl[];
  /** gaps_count broken down by severity */
  gaps_by_severity: Record<string, number>;
  note: string;
}

/* ── Operational System Types ────────────────────────────────────────── */

export interface OperationalSystem {
  id: string;
  name: string;
  path: string;
  description: string;
  file_count: number;
  files: string[];
}

/* ── WebSocket Events ──────────────────────────────────────────────────── */

export type WSEvent =
  | { type: 'pipeline_started'; run_id: string; institution: string; timestamp: string; agents: AgentDef[]; system_id?: string; source_files?: string[] }
  | { type: 'rag_status'; status: string; run_id: string; chunks?: number; error?: string }
  | { type: 'agent_started'; run_id: string; agent_id: string; layer: number; name: string; timestamp: string }
  | { type: 'finding'; run_id: string; agent_id: string; layer: number; finding_index: number; finding: Finding }
  | { type: 'agent_completed'; run_id: string; agent_id: string; layer: number; name: string; duration_ms: number; finding_counts: Record<string, number>; total_findings: number; timestamp: string }
  | { type: 'agent_failed'; run_id: string; agent_id: string; layer: number; error: string; timestamp: string }
  | { type: 'pipeline_completed'; run_id: string; timestamp: string; summary: PipelineSummary; agents: AgentDef[] }
  | { type: 'run_created'; run_id: string; system_id?: string }
  | { type: 'pong' };
