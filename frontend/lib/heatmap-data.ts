/** Isı haritası veri katmanı — client/server güvenli, React bağımsız. */

import type { Category, ImpactBreakdown, Issue, Severity } from "./api-client";

export type HeatStatus = "healthy" | "warning" | "critical";

export interface FileHeatCell {
  path: string;
  status: HeatStatus;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  issueCount: number;
  wasteSummary: string;
  extension: string;
  color: string;
}

/**
 * Cyber-Clinic Heatmap Colors
 * Deep Forest Emerald (healthy) → Cyber Amber (warning) → Neon Bio-Hazard Crimson (critical)
 */
export const GH_COLORS = {
  empty: "#0B0F19",       /* Deep Midnight Slate — matches background */
  healthy: "#05442A",     /* Deep Forest Emerald base */
  warn1: "#0F6B3A",       /* Emerald → transitioning */
  warn2: "#10B981",       /* Emerald bright glow */
  warn3: "#D97706",       /* Cyber Amber/Sulphur */
  critical: "#FF0055",    /* Neon Bio-Hazard Crimson intense */
} as const;

const CRITICAL_CODES = new Set([
  "UNBOUNDED_CACHE",
  "GLOBAL_ACCUMULATOR",
  "HARDCODED_SECRET",
  "N1_QUERY",
  "SYNC_IO_IN_ASYNC",
  "MEMORY_LEAK",
  "UNHANDLED_EXCEPTION",
  "DEAD_CODE",
  "MISSING_TIMEOUT",
  "SQL_INJECTION_RISK",
]);

const SOURCE_EXT = new Set([".py", ".js", ".jsx", ".ts", ".tsx"]);

function extOf(path: string): string {
  const i = path.lastIndexOf(".");
  return i >= 0 ? path.slice(i).toLowerCase() : "";
}

function classifyFile(issues: Issue[]): HeatStatus {
  if (issues.length === 0) return "healthy";
  const hasHigh = issues.some((i) => i.severity === "high");
  const hasCriticalCode = issues.some((i) => CRITICAL_CODES.has(i.code));
  const hasSecurity = issues.some((i) => i.category === "security");
  if (hasHigh || hasCriticalCode || hasSecurity) return "critical";
  return "warning";
}

function cellColor(status: HeatStatus, issueCount: number): string {
  if (status === "critical") return GH_COLORS.critical;
  if (status === "healthy") return GH_COLORS.healthy;
  if (issueCount >= 4) return GH_COLORS.warn3;
  if (issueCount >= 2) return GH_COLORS.warn2;
  return GH_COLORS.warn1;
}

function wasteLabel(category: Category): string {
  if (category === "memory") return "RAM İsrafı";
  if (category === "security") return "Güvenlik Riski";
  if (category === "performance") return "Performans Etkisi";
  if (category === "reliability") return "Güvenilirlik Riski";
  return "Kalite Etkisi";
}

function wasteLevel(severity: Severity, impactScore?: number): string {
  if (severity === "high" || (impactScore ?? 0) >= 70) return "Yüksek";
  if (severity === "medium" || (impactScore ?? 0) >= 40) return "Orta";
  return "Düşük";
}

export function buildHeatmapCells(
  issues: Issue[],
  impacts: ImpactBreakdown[],
  scannedFiles?: string[],
): FileHeatCell[] {
  const impactByIssue = new Map(impacts.map((x) => [x.issue_id, x]));
  const byFile = new Map<string, Issue[]>();

  for (const issue of issues) {
    const list = byFile.get(issue.file) ?? [];
    list.push(issue);
    byFile.set(issue.file, list);
  }

  const paths = new Set<string>();
  for (const p of scannedFiles ?? []) {
    if (SOURCE_EXT.has(extOf(p))) paths.add(p);
  }
  for (const p of Array.from(byFile.keys())) {
    if (SOURCE_EXT.has(extOf(p))) paths.add(p);
  }

  const sorted = Array.from(paths).sort((a, b) => a.localeCompare(b));

  return sorted.map((path) => {
    const fileIssues = byFile.get(path) ?? [];
    const highCount = fileIssues.filter((i) => i.severity === "high").length;
    const mediumCount = fileIssues.filter((i) => i.severity === "medium").length;
    const lowCount = fileIssues.filter((i) => i.severity === "low").length;
    const issueCount = fileIssues.length;
    const status = classifyFile(fileIssues);

    let topImpact: { label: string; level: string; score: number } | null = null;
    for (const issue of fileIssues) {
      const imp = impactByIssue.get(issue.id);
      const score = imp?.impact_score ?? 0;
      const label = wasteLabel(issue.category);
      const level = wasteLevel(issue.severity, score);
      if (!topImpact || score > topImpact.score) {
        topImpact = { label, level, score };
      }
    }

    let wasteSummary = "Temiz dosya — kaynak israfı tespit edilmedi";
    if (fileIssues.length > 0 && topImpact) {
      wasteSummary = `Tahmini ${topImpact.label}: ${topImpact.level}`;
    }

    return {
      path,
      status,
      highCount,
      mediumCount,
      lowCount,
      issueCount,
      wasteSummary,
      extension: extOf(path),
      color: cellColor(status, issueCount),
    };
  });
}
