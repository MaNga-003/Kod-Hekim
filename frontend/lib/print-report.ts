/**
 * Rapor HTML'i üretir (§6.3). PDF indirme: download-report-pdf.ts
 */
import type {
  Category,
  FixSuggestion,
  ImpactBreakdown,
  Issue,
  ModeComparisonResponse,
  ReportPayload,
  SimulateResponse,
} from "./api-client";
import { buildHeatmapCells } from "./heatmap-data";

const CAT_TR: Record<Category, string> = {
  performance: "Performans",
  memory: "RAM / Bellek",
  reliability: "Güvenilirlik",
  security: "Güvenlik",
  quality: "Kalite",
};

const SEV_TR = { high: "Yüksek", medium: "Orta", low: "Düşük" } as const;

export type PrintReportResult =
  | { ok: true; message?: string }
  | { ok: false; message: string };

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function heatmapHtml(issues: Issue[], impacts: ImpactBreakdown[], scannedFiles?: string[]): string {
  const cells = buildHeatmapCells(issues, impacts, scannedFiles);
  if (cells.length === 0) return "<p><em>Isı haritası verisi yok.</em></p>";

  const stats = { healthy: 0, warning: 0, critical: 0 };
  for (const c of cells) stats[c.status] += 1;

  const ROWS = 7;
  const cols = Math.max(26, Math.ceil(cells.length / ROWS));
  const grid: ({ color: string; path: string } | null)[][] = Array.from({ length: cols }, () =>
    Array.from({ length: ROWS }, () => null),
  );
  cells.forEach((cell, idx) => {
    const col = Math.floor(idx / ROWS);
    const row = idx % ROWS;
    if (col < cols) grid[col][row] = { color: cell.color, path: cell.path };
  });

  let squares = "";
  for (const column of grid) {
    squares += '<div style="display:flex;flex-direction:column;gap:2px">';
    for (const cell of column) {
      if (cell) {
        squares += `<div title="${esc(cell.path)}" style="width:10px;height:10px;border-radius:2px;background:${cell.color};border:1px solid #ccc"></div>`;
      } else {
        squares += `<div style="width:10px;height:10px;border-radius:2px;background:#eee"></div>`;
      }
    }
    squares += "</div>";
  }

  return `
    <p><strong>${cells.length} dosya</strong> · ${stats.healthy} sağlıklı · ${stats.warning} uyarı · ${stats.critical} kritik</p>
    <div style="display:flex;gap:2px;flex-wrap:nowrap;overflow:hidden;margin:8px 0">${squares}</div>
    <p style="font-size:10px;color:#666">Yeşil = sağlıklı · Sarı-yeşil = uyarı · Kırmızı = kritik</p>
  `;
}

function issueBlock(
  issue: Issue,
  impact: ImpactBreakdown | undefined,
  fix: FixSuggestion | undefined,
  mode: string,
): string {
  const sev = SEV_TR[issue.severity];
  let fixHtml = "";
  if (mode !== "static" && fix?.fix_instruction_tr?.trim()) {
    fixHtml = `
      <div style="margin-top:8px;padding:8px;background:#f9fafb;border:1px solid #ddd;border-radius:4px">
        <strong>🩺 Dr. Cerrah Reçetesi</strong>
        <p style="white-space:pre-wrap;margin:6px 0 0;font-size:11px">${esc(fix.fix_instruction_tr)}</p>
        ${fix.test_suggestion ? `<p style="font-size:10px;color:#555;margin-top:4px"><strong>Test:</strong> ${esc(fix.test_suggestion)}</p>` : ""}
      </div>`;
  }

  return `
    <div class="issue-card issue" style="border:1px solid #ddd;border-radius:6px;padding:12px;margin-bottom:10px;break-inside:avoid">
      <div style="font-size:11px;margin-bottom:4px">
        <span style="font-weight:700;color:${issue.severity === "high" ? "#b91c1c" : issue.severity === "medium" ? "#a16207" : "#15803d"}">${sev}</span>
        · <code>${esc(issue.code)}</code>
        · <span style="color:#555">${esc(issue.file)}:${issue.line_start}</span>
        ${impact ? ` · etki ${impact.impact_score}/100` : ""}
      </div>
      <p style="margin:4px 0;font-size:12px">${esc(issue.explanation)}</p>
      ${impact?.explanation_tr ? `<p style="font-size:11px;color:#444;margin:4px 0"><strong>Etki:</strong> ${esc(impact.explanation_tr)}</p>` : ""}
      ${issue.snippet ? `<pre style="font-size:10px;background:#f3f4f6;padding:8px;border-radius:4px;overflow-wrap:anywhere;white-space:pre-wrap">${esc(issue.snippet)}</pre>` : ""}
      ${fixHtml}
    </div>`;
}

export function buildPrintDocument(
  data: ReportPayload,
  opts?: {
    modeComp?: ModeComparisonResponse | null;
    simulated?: SimulateResponse | null;
    /** PDF indirme için araç çubuğu ve yazdırma script'i eklenmez. */
    forExport?: boolean;
  },
): string {
  const report = data.report!;
  const health = report.health;
  const impactsById: Record<string, ImpactBreakdown> = {};
  for (const x of data.impacts) impactsById[x.issue_id] = x;

  const fixesById: Record<string, FixSuggestion> = {};
  for (const f of data.fixes ?? []) fixesById[f.issue_id] = f;

  const byCat: Record<Category, Issue[]> = {
    performance: [],
    memory: [],
    reliability: [],
    security: [],
    quality: [],
  };
  for (const i of data.issues) {
    if (i.category in byCat) byCat[i.category].push(i);
  }

  const scoreDisplay = opts?.simulated?.simulated_score.overall ?? health.overall;

  let priorities = "";
  if (report.top_priorities.length > 0) {
    priorities = `<h2>🏆 Top 3 Öncelik</h2><ol>${report.top_priorities
      .map(
        (p) =>
          `<li><strong>[${esc(p.issue_id)}] ${esc(p.code)}</strong> — ${esc(p.rationale)} <em>(ROI ${p.roi_score.toFixed(1)})</em></li>`,
      )
      .join("")}</ol>`;
  }

  let summary = "";
  if (report.executive_summary) {
    summary = `<h2>📋 Yönetici Özeti</h2><div style="white-space:pre-line;font-size:12px;line-height:1.5">${esc(report.executive_summary)}</div>`;
  }

  let categories = "";
  for (const cat of ["security", "performance", "memory", "reliability", "quality"] as Category[]) {
    const list = byCat[cat];
    if (list.length === 0) continue;
    categories += `<h2>${CAT_TR[cat]} (${list.length})</h2>`;
    for (const issue of list) {
      categories += issueBlock(issue, impactsById[issue.id], fixesById[issue.id], data.mode);
    }
  }

  let roadmap = "";
  if (report.roadmap.length > 0) {
    roadmap = `<h2>🗺️ Düzeltme Roadmap'i</h2><ol>${report.roadmap.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>`;
  }

  let modeTable = "";
  if (opts?.modeComp) {
    const rows = opts.modeComp.modes
      .map(
        (m) =>
          `<tr><td>${esc(m.mode)}${m.is_actual ? " ●" : ""}</td><td>${m.estimated_seconds.toFixed(1)}s</td><td>${m.estimated_tokens}</td><td>${m.estimated_issues}</td></tr>`,
      )
      .join("");
    modeTable = `<h2>📊 Mod Karşılaştırması</h2><table><thead><tr><th>Mod</th><th>Süre</th><th>Token</th><th>Bulgu</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  const title = `KodHekim-Tani-${data.job_id}`;
  const forExport = opts?.forExport ?? false;

  const toolbar = forExport
    ? ""
    : `
  <div class="toolbar no-print">
    <strong>KodHekim PDF Önizleme</strong>
    <button type="button" onclick="window.print()">📄 PDF / Yazdır</button>
    <button type="button" class="secondary" onclick="window.close()">Kapat</button>
    <span style="font-size:11px;opacity:0.85">Hedef: PDF olarak kaydet · Arka plan grafikleri: açık</span>
  </div>
  <div class="hint no-print"><strong>PDF kaydetmek için:</strong> Üstteki <strong>PDF / Yazdır</strong> düğmesine basın. Hedef olarak <strong>「PDF olarak kaydet」</strong> seçin. Isı haritası renkleri için <strong>「Arka plan grafiklerini yazdır」</strong> işaretleyin.</div>`;

  const autoPrintScript = forExport
    ? ""
    : `
  <script>
    window.addEventListener("load", function () {
      window.setTimeout(function () { window.print(); }, 600);
    });
  </script>`;

  return `<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8"/>
  <title>${esc(title)}</title>
  <style>
    @page { size: A4; margin: 14mm; }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { font-family: "Segoe UI", system-ui, sans-serif; color: #111; background: #fff; margin: 0; padding: 16px; font-size: 12px; line-height: 1.45; }
    .toolbar { position: sticky; top: 0; z-index: 99; background: #1e293b; color: #f8fafc; padding: 12px 16px; margin: -16px -16px 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .toolbar button { background: #3b82f6; color: #fff; border: none; border-radius: 6px; padding: 8px 16px; font-size: 13px; cursor: pointer; font-weight: 600; }
    .toolbar button.secondary { background: #475569; }
    @media print { .no-print { display: none !important; } body { padding: 0; } .toolbar { display: none !important; } }
    h1 { font-size: 22px; margin: 0 0 4px; color: #111; }
    h2 { font-size: 15px; margin: 20px 0 8px; border-bottom: 1px solid #ccc; padding-bottom: 4px; page-break-after: avoid; color: #111; }
    .meta { color: #555; font-size: 11px; margin-bottom: 16px; }
    .scores { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
    .score-box { border: 1px solid #ccc; border-radius: 8px; padding: 12px 16px; text-align: center; min-width: 90px; background: #fff; }
    .score-box.main { border-width: 2px; border-color: #1d4ed8; }
    .score-box .val { font-size: 28px; font-weight: 700; color: #111; }
    .stats { display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0; }
    .stat { border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; text-align: center; background: #fff; }
    table { width: 100%; border-collapse: collapse; font-size: 11px; margin: 8px 0; }
    th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; color: #111; }
    th { background: #f3f4f6; }
    .section { break-inside: avoid; margin-bottom: 16px; }
    .hint { background: #eff6ff; border: 1px solid #93c5fd; padding: 10px; border-radius: 6px; font-size: 11px; margin-bottom: 16px; color: #111; }
    footer { margin-top: 24px; text-align: center; color: #888; font-size: 10px; border-top: 1px solid #eee; padding-top: 12px; }
    code { font-family: Consolas, monospace; font-size: 11px; }
    pre { font-family: Consolas, monospace; color: #111; }
  </style>
</head>
<body>
  ${toolbar}

  <h1>KodHekim Tanı Raporu</h1>
  <p class="meta">${esc(data.repo_path)} · mod: ${esc(data.mode)} · sağlayıcı: ${esc(data.provider)} · job: ${esc(data.job_id)}</p>

  <div class="section scores">
    <div class="score-box main"><div class="val">${scoreDisplay}</div><div>Genel / 100</div></div>
    <div class="score-box"><div class="val">${health.performance}</div><div>Performans</div></div>
    <div class="score-box"><div class="val">${health.security}</div><div>Güvenlik</div></div>
    <div class="score-box"><div class="val">${health.quality}</div><div>Kalite</div></div>
  </div>

  <div class="stats">
    <div class="stat"><strong>${report.issues_count}</strong><br/>Toplam Bulgu</div>
    <div class="stat"><strong style="color:#b91c1c">${report.severity_breakdown.high}</strong><br/>Yüksek</div>
    <div class="stat"><strong style="color:#a16207">${report.severity_breakdown.medium}</strong><br/>Orta</div>
    <div class="stat"><strong style="color:#15803d">${report.severity_breakdown.low}</strong><br/>Düşük</div>
  </div>

  <div class="section">
    <h2>Kod Sağlığı Isı Haritası</h2>
    ${heatmapHtml(data.issues, data.impacts, data.scanned_files)}
  </div>

  ${priorities}
  ${summary}
  ${categories}
  ${roadmap}
  ${modeTable}

  <footer>KodHekim · ${esc(new Date().toLocaleString("tr-TR"))}</footer>${autoPrintScript}
</body>
</html>`;
}
