/**
 * KodHekim backend API client.
 *
 * Backend kontratı: backend/api/*.py.
 * Base URL: `NEXT_PUBLIC_API_BASE` env'inden (default: http://localhost:8000).
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";

export type Mode = "static" | "hybrid" | "deep";
export type Provider = "cerebras" | "gemini";
export type Severity = "high" | "medium" | "low";
export type Category =
  | "performance"
  | "memory"
  | "reliability"
  | "security"
  | "quality";

export interface AnalyzeRequest {
  repo_url: string;
  mode: Mode;
  provider: Provider;
  model_overrides?: Record<string, string>;
}

export interface AnalyzeResponse {
  job_id: string;
  status: string;
}

export interface Issue {
  id: string;
  code: string;
  category: Category;
  severity: Severity;
  file: string;
  line_start: number;
  line_end: number;
  snippet: string;
  explanation: string;
  static_confidence: number;
  llm_confidence: number | null;
  extra: Record<string, unknown>;
}

export interface ImpactBreakdown {
  issue_id: string;
  impact_score: number;
  impact_dimensions: Record<string, unknown>;
  explanation_tr: string;
  remediation_effort_hours: number;
}

export interface FixSuggestion {
  issue_id: string;
  fix_instruction_tr: string;
  risk_level: number;
  test_suggestion: string;
  improvement_estimate: string;
  recipe_valid: boolean;
}

export interface HealthScore {
  overall: number;
  performance: number;
  security: number;
  quality: number;
}

export interface TopPriority {
  issue_id: string;
  code: string;
  rationale: string;
  roi_score: number;
}

export interface FinalReport {
  health: HealthScore;
  issues_count: number;
  severity_breakdown: { high: number; medium: number; low: number };
  top_priorities: TopPriority[];
  executive_summary: string;
  roadmap: string[];
  issues: unknown[];
  impacts: unknown[];
  fixes: unknown[];
}

export interface ReportPayload {
  job_id: string;
  repo_path: string;
  mode: Mode;
  provider: string;
  issues: Issue[];
  impacts: ImpactBreakdown[];
  fixes: FixSuggestion[];
  scanned_files?: string[];
  report: FinalReport | null;
  events: Array<{ type: string; data: Record<string, unknown>; timestamp: string }>;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "cloning" | "running" | "done" | "error";
  mode: Mode;
  provider: string;
  error_code: string | null;
  error: string | null;
}

export interface ModelsResponse {
  providers: {
    cerebras: { available: boolean; models: string[]; defaults: Record<string, string> };
    gemini: { available: boolean; models: string[]; defaults: Record<string, string> };
  };
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(res.status, `${path} → ${res.status}`, detail);
  }
  return (await res.json()) as T;
}

export async function startAnalysis(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  return jsonRequest<AnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return jsonRequest<JobStatus>(`/api/jobs/${jobId}/status`);
}

export async function getReport(jobId: string): Promise<ReportPayload | null> {
  const res = await fetch(`${API_BASE}/api/report/${jobId}`);
  if (res.status === 202) return null;
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(res.status, `report ${res.status}`, detail);
  }
  return (await res.json()) as ReportPayload;
}

export async function listModels(): Promise<ModelsResponse> {
  return jsonRequest<ModelsResponse>("/api/models");
}

export interface SimulateResponse {
  current_score: HealthScore;
  simulated_score: HealthScore;
  delta: HealthScore;
}

export async function simulateFixes(
  jobId: string,
  acceptedFixIds: string[],
): Promise<SimulateResponse> {
  return jsonRequest<SimulateResponse>(`/api/report/${jobId}/simulate`, {
    method: "POST",
    body: JSON.stringify({ accepted_fix_ids: acceptedFixIds }),
  });
}

export interface ModeMetric {
  mode: Mode;
  estimated_seconds: number;
  estimated_tokens: number;
  estimated_issues: number;
  is_actual: boolean;
}

export interface ModeComparisonResponse {
  actual_mode: Mode;
  file_count: number;
  modes: ModeMetric[];
}

export async function getModeComparison(
  jobId: string,
): Promise<ModeComparisonResponse> {
  return jsonRequest<ModeComparisonResponse>(
    `/api/report/${jobId}/mode-comparison`,
  );
}

export function apiBase(): string {
  return API_BASE;
}

export function normalizeFix(raw: Record<string, unknown>): FixSuggestion {
  const legacyDiff = typeof raw.diff === "string" ? raw.diff : "";
  const instruction =
    typeof raw.fix_instruction_tr === "string" && raw.fix_instruction_tr.trim()
      ? raw.fix_instruction_tr
      : legacyDiff;
  return {
    issue_id: String(raw.issue_id ?? ""),
    fix_instruction_tr: instruction,
    risk_level: Number(raw.risk_level ?? 3),
    test_suggestion: String(raw.test_suggestion ?? ""),
    improvement_estimate: String(raw.improvement_estimate ?? ""),
    recipe_valid: Boolean(raw.recipe_valid ?? raw.diff_valid ?? instruction.length >= 40),
  };
}
