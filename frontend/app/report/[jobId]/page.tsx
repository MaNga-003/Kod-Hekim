"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError, type Category, type FixSuggestion, type ImpactBreakdown, type Issue,
  type Mode, type ModeComparisonResponse, type ReportPayload, type Severity,
  type SimulateResponse, getModeComparison, getReport, normalizeFix, simulateFixes,
} from "@/lib/api-client";
import { FixRecipePanel } from "@/components/fix-recipe-panel";
import { PrintButton } from "@/components/print-button";
import { CodeHealthHeatmap } from "@/components/report/code-heatmap";
import { KodHekimLogo } from "@/components/kodhekim-logo";
import { ThemeToggle } from "@/components/theme-provider";

const CATEGORY_LABELS: Record<Category, { tr: string; icon: string }> = {
  performance: { tr: "Performans", icon: "⚡" },
  memory: { tr: "RAM / Bellek", icon: "🧠" },
  reliability: { tr: "Güvenilirlik", icon: "🔗" },
  security: { tr: "Güvenlik", icon: "🔒" },
  quality: { tr: "Kalite", icon: "✦" },
};

const SEV_LABEL: Record<Severity, string> = { high: "Yüksek", medium: "Orta", low: "Düşük" };

export default function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const [data, setData] = useState<ReportPayload | null>(null);
  const [err, setErr] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [acceptedIssues, setAcceptedIssues] = useState<Set<string>>(new Set());
  const [simulated, setSimulated] = useState<SimulateResponse | null>(null);
  const [modeComp, setModeComp] = useState<ModeComparisonResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const poll = async () => {
      while (!cancelled && attempts < 40) {
        try {
          const rep = await getReport(jobId);
          if (cancelled) return;
          if (rep) { setData(rep); setLoading(false); return; }
        } catch (e) {
          if (e instanceof ApiError && e.status >= 500) {
            setErr((e.detail as { message?: string })?.message || "Analiz hata ile sonlandı.");
            setLoading(false); return;
          }
          setErr((e as Error).message); setLoading(false); return;
        }
        attempts += 1;
        await new Promise((r) => setTimeout(r, 1000));
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [jobId]);

  useEffect(() => { if (data?.report) getModeComparison(jobId).then(setModeComp).catch(() => undefined); }, [data, jobId]);

  useEffect(() => {
    if (!data?.report) return;
    const t = setTimeout(() => { simulateFixes(jobId, Array.from(acceptedIssues)).then(setSimulated).catch(() => undefined); }, 300);
    return () => clearTimeout(t);
  }, [jobId, data, acceptedIssues]);

  const toggleIssue = (id: string) => { setAcceptedIssues((prev) => { const n = new Set(prev); if (n.has(id)) { n.delete(id); } else { n.add(id); } return n; }); };
  const selectAllIssues = () => { if (data) setAcceptedIssues(new Set(data.issues.map((i) => i.id))); };
  const clearAllIssues = () => setAcceptedIssues(new Set());

  const issuesByCategory = useMemo<Record<Category, Issue[]>>(() => {
    const out: Record<Category, Issue[]> = { performance: [], memory: [], reliability: [], security: [], quality: [] };
    if (data) for (const i of data.issues) { if (i.category in out) out[i.category].push(i); }
    return out;
  }, [data]);

  const impactsById = useMemo(() => { const m: Record<string, ImpactBreakdown> = {}; if (data) for (const x of data.impacts) m[x.issue_id] = x; return m; }, [data]);

  const fixesById = useMemo(() => {
    const m: Record<string, FixSuggestion> = {};
    if (!data) return m;
    const rawFixes = [...(data.fixes ?? []), ...((data.report?.fixes as Record<string, unknown>[]) ?? [])];
    for (const raw of rawFixes) { const f = normalizeFix(raw as Record<string, unknown>); if (f.issue_id) m[f.issue_id] = f; }
    return m;
  }, [data]);

  if (loading) return (
    <main className="min-h-screen flex flex-col items-center justify-center hero-gradient">
      <KodHekimLogo size={56} className="mb-5" />
      <div className="flex items-center gap-2"><div className="h-2 w-2 rounded-full bg-[var(--accent)] pulse-dot" /><p className="text-muted-light">Rapor yükleniyor…</p></div>
    </main>
  );

  if (err) return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6 hero-gradient">
      <div className="panel rounded-2xl p-8 max-w-lg text-center">
        <p className="text-bad font-semibold text-lg mb-2">Rapor alınamadı</p>
        <p className="text-sm text-muted">{err}</p>
        <button onClick={() => router.push("/")} className="btn-ghost mt-5 text-sm">← Başa dön</button>
      </div>
    </main>
  );

  if (!data?.report) return (<main className="min-h-screen flex items-center justify-center hero-gradient"><p className="text-muted">Rapor verisi boş.</p></main>);

  const report = data.report;
  const securityIssues = issuesByCategory.security;

  return (
    <main className="min-h-screen px-6 py-8 print:py-0 print:px-0 hero-gradient">
      {/* Tema Değiştirme */}
      <div className="fixed top-5 right-5 z-50"><ThemeToggle /></div>

      <div className="relative z-10 max-w-5xl mx-auto print:max-w-none">

        {/* ─── Başlık ─── */}
        <header className="flex items-center justify-between mb-8 print:mb-4 print-section float-up">
          <div className="flex items-center gap-3">
            <KodHekimLogo size={36} className="no-print" />
            <div>
              <h1 className="text-2xl font-bold"><span className="text-accent">Kod</span>Hekim Tanı Raporu</h1>
              <p className="text-xs text-muted mt-0.5 mono">{data.repo_path} · {data.mode} · {data.provider}</p>
            </div>
          </div>
          <div className="flex gap-2 no-print">
            <button type="button" onClick={() => router.push("/")} className="btn-ghost text-xs px-3 py-2">← Yeni analiz</button>
            <PrintButton data={data} jobId={jobId} modeComp={modeComp} simulated={simulated} />
          </div>
        </header>

        {/* ─── Sağlık Skoru — Düzenli Grid ─── */}
        <section className="panel rounded-2xl p-6 mb-6 print-section float-up float-up-delay-1">
          <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-6 items-start">
            {/* Ana Skor */}
            <div className="flex flex-col items-center justify-center">
              <GaugeCircle value={simulated?.simulated_score.overall ?? report.health.overall} color={scoreColor(simulated?.simulated_score.overall ?? report.health.overall)} />
              {simulated && simulated.simulated_score.overall !== report.health.overall && (
                <div className="text-xs mt-1"><span className="text-muted line-through mono">{report.health.overall}</span> <span className="text-good">→ {simulated.simulated_score.overall}</span></div>
              )}
              <div className="text-xs text-muted mt-1 font-medium">Genel Skor</div>
            </div>

            {/* Alt Skorlar + İstatistikler */}
            <div className="space-y-4">
              {/* Alt skorlar düzenli grid */}
              <div className="grid grid-cols-3 gap-3">
                <ScoreCard label="Performans" icon="⚡" value={report.health.performance} simulated={simulated?.simulated_score.performance} />
                <ScoreCard label="Güvenlik" icon="🔒" value={report.health.security} simulated={simulated?.simulated_score.security} />
                <ScoreCard label="Kalite" icon="✦" value={report.health.quality} simulated={simulated?.simulated_score.quality} />
              </div>

              {/* Bulgu sayıları */}
              <div className="grid grid-cols-4 gap-2">
                <StatPill label="Toplam" value={report.issues_count} />
                <StatPill label="Yüksek" value={report.severity_breakdown.high} color="text-bad" />
                <StatPill label="Orta" value={report.severity_breakdown.medium} color="text-warn" />
                <StatPill label="Düşük" value={report.severity_breakdown.low} color="text-good" />
              </div>
            </div>
          </div>

          {/* Simülasyon bilgisi */}
          {acceptedIssues.size > 0 && simulated && (
            <div className="mt-4 rounded-xl border border-[var(--good)] bg-[color-mix(in_srgb,var(--good)_8%,transparent)] p-3 text-sm flex items-center justify-between">
              <span><span className="text-muted">{acceptedIssues.size} bulgu giderildi → </span><span className="text-good font-semibold">+{simulated.delta.overall} puan</span></span>
              <button onClick={clearAllIssues} className="text-xs text-accent hover:underline no-print">Temizle</button>
            </div>
          )}
          <div className="mt-2 flex justify-end no-print">
            <button onClick={selectAllIssues} className="text-xs text-accent hover:underline">Tüm bulguları seç</button>
          </div>
        </section>

        {/* ─── Isı Haritası ─── */}
        <section className="panel rounded-2xl p-6 mb-6 print-section heatmap-print float-up float-up-delay-2">
          <h2 className="text-sm font-semibold text-muted-light mb-4 flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--accent)]" />
            Kod Sağlığı Isı Haritası
          </h2>
          <CodeHealthHeatmap issues={data.issues} impacts={data.impacts} scannedFiles={data.scanned_files} />
        </section>

        {/* ─── Top 3 Öncelik ─── */}
        {report.top_priorities.length > 0 && (
          <section className="panel rounded-2xl p-6 mb-6">
            <h2 className="text-base font-bold mb-3">🏆 Top 3 Öncelik</h2>
            <ol className="space-y-2">
              {report.top_priorities.map((p, idx) => (
                <li key={p.issue_id} className="flex gap-3 items-center p-3 rounded-xl card-hover -mx-1">
                  <span className="text-xl font-black text-muted opacity-30 w-6 text-center">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <a href={`#${p.issue_id}`} className="font-medium text-accent hover:underline mono text-sm">{p.code}</a>
                    <p className="text-xs text-muted mt-0.5 truncate">{p.rationale}</p>
                  </div>
                  <span className="text-xs mono text-violet font-medium px-2 py-1 rounded-lg bg-[var(--violet-glow)] shrink-0">ROI {p.roi_score.toFixed(1)}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* ─── Yönetici Özeti ─── */}
        {report.executive_summary && (
          <section className="panel rounded-2xl p-6 mb-6">
            <h2 className="text-base font-bold mb-3">📋 Yönetici Özeti</h2>
            <div className="text-sm leading-relaxed whitespace-pre-line text-muted-light">{report.executive_summary}</div>
          </section>
        )}

        {/* ─── Güvenlik ─── */}
        {securityIssues.length > 0 && (
          <section className="panel rounded-2xl p-6 mb-6 border-l-4 border-l-[var(--bad)] print-section">
            <h2 className="text-base font-bold mb-3 text-bad">🔒 Güvenlik ({securityIssues.length})</h2>
            <div className="space-y-3">{securityIssues.map((i) => <IssueCard key={i.id} issue={i} impact={impactsById[i.id]} fix={fixesById[i.id]} mode={data.mode} accepted={acceptedIssues.has(i.id)} onToggle={() => toggleIssue(i.id)} />)}</div>
          </section>
        )}

        {/* ─── Diğer Kategoriler ─── */}
        {(["performance", "memory", "reliability", "quality"] as Category[]).map((cat) =>
          issuesByCategory[cat].length > 0 && (
            <section key={cat} className="panel rounded-2xl p-6 mb-6 print-section">
              <h2 className="text-base font-bold mb-3">{CATEGORY_LABELS[cat].icon} {CATEGORY_LABELS[cat].tr} ({issuesByCategory[cat].length})</h2>
              <div className="space-y-3">{issuesByCategory[cat].map((i) => <IssueCard key={i.id} issue={i} impact={impactsById[i.id]} fix={fixesById[i.id]} mode={data.mode} accepted={acceptedIssues.has(i.id)} onToggle={() => toggleIssue(i.id)} />)}</div>
            </section>
          ),
        )}

        {/* ─── Roadmap ─── */}
        {report.roadmap.length > 0 && (
          <section className="panel rounded-2xl p-6 mb-6">
            <h2 className="text-base font-bold mb-3">🗺️ Düzeltme Yol Haritası</h2>
            <ol className="space-y-2 list-decimal list-inside text-sm text-muted-light">{report.roadmap.map((s, i) => <li key={i} className="leading-relaxed">{s}</li>)}</ol>
          </section>
        )}

        {/* ─── Mod Karşılaştırması ─── */}
        {modeComp && (
          <section className="panel rounded-2xl p-6 mb-6">
            <h2 className="text-base font-bold mb-2">📊 Mod Karşılaştırması</h2>
            <p className="text-xs text-muted mb-3">{modeComp.file_count} dosya için maliyet-fayda</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-muted text-xs"><tr className="text-left border-b border-[var(--panel-border)]"><th className="py-2 font-medium">Mod</th><th className="py-2 font-medium">Süre</th><th className="py-2 font-medium">Token</th><th className="py-2 font-medium">Bulgu</th></tr></thead>
                <tbody>
                  {modeComp.modes.map((m) => (
                    <tr key={m.mode} className={`border-t border-[var(--panel-border)] ${m.is_actual ? "" : "text-muted"}`}>
                      <td className="py-2 capitalize font-medium">{m.mode}{m.is_actual && <span className="ml-1.5 text-[10px] text-good">●</span>}</td>
                      <td className="py-2 mono text-xs">{m.estimated_seconds < 60 ? `${m.estimated_seconds.toFixed(1)}s` : `${(m.estimated_seconds / 60).toFixed(1)}m`}</td>
                      <td className="py-2 mono text-xs">{m.estimated_tokens === 0 ? "0" : m.estimated_tokens >= 1000 ? `${Math.round(m.estimated_tokens / 1000)}K` : `${m.estimated_tokens}`}</td>
                      <td className="py-2 mono text-xs">{m.estimated_issues}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <footer className="text-center text-xs text-muted mt-10 pb-6">
          <div className="w-12 h-px bg-[var(--panel-border)] mx-auto mb-3" />
          KodHekim · {data.job_id} · {new Date().toLocaleString("tr-TR")}
        </footer>
      </div>

    </main>
  );
}

/* ─── Alt Bileşenler ─── */

function scoreColor(v: number) { return v >= 80 ? "var(--good)" : v >= 50 ? "var(--warn)" : "var(--bad)"; }

function GaugeCircle({ value, color }: { value: number; color: string }) {
  const r = 44, c = 2 * Math.PI * r, off = c - (value / 100) * c;
  return (
    <div className="relative">
      <svg width="120" height="120" className="-rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--panel-border)" strokeWidth="7" />
        <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="7" strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round" className="gauge-ring" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-3xl font-bold" style={{ color }}>{value}</span>
      </div>
    </div>
  );
}

function ScoreCard({ label, icon, value, simulated }: { label: string; icon: string; value: number; simulated?: number }) {
  const v = simulated ?? value;
  const color = v >= 80 ? "text-good" : v >= 50 ? "text-warn" : "text-bad";
  const changed = simulated !== undefined && simulated !== value;
  return (
    <div className="stat-pill">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted font-medium">{label}</span>
        <span className="text-xs">{icon}</span>
      </div>
      <div className={`text-2xl font-bold ${color}`}>{v}</div>
      {changed && <div className="text-[10px] text-muted mt-0.5"><span className="line-through">{value}</span> <span className="text-good">→ {simulated}</span></div>}
    </div>
  );
}

function StatPill({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--panel-2)] p-2.5 text-center">
      <div className={`text-lg font-bold ${color ?? ""}`}>{value}</div>
      <div className="text-[10px] text-muted">{label}</div>
    </div>
  );
}

function IssueCard({ issue, impact, fix, mode, accepted, onToggle }: { issue: Issue; impact?: ImpactBreakdown; fix?: FixSuggestion; mode: Mode; accepted: boolean; onToggle: () => void }) {
  const badge = issue.severity === "high" ? "badge-high" : issue.severity === "medium" ? "badge-medium" : "badge-low";
  return (
    <div id={issue.id} className={`issue-card ${accepted ? "accepted" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <label className="flex items-center gap-1 no-print cursor-pointer">
              <input type="checkbox" checked={accepted} onChange={onToggle} className="accent-[var(--good)] h-3.5 w-3.5" />
              <span className="text-[10px] text-muted">Giderildi</span>
            </label>
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md ${badge}`}>{SEV_LABEL[issue.severity]}</span>
            <span className="mono text-xs text-accent font-medium">{issue.code}</span>
            <span className="text-[10px] text-muted mono truncate">{issue.file}:{issue.line_start}{issue.line_end !== issue.line_start ? `-${issue.line_end}` : ""}</span>
          </div>
          <p className="text-sm mt-1.5 text-muted-light">{issue.explanation}</p>
          {impact?.explanation_tr && <p className="text-xs text-muted mt-1.5"><span className="text-violet font-medium">Etki:</span> {impact.explanation_tr}</p>}
        </div>
        {impact && <span className="text-[10px] mono text-muted shrink-0 px-2 py-1 rounded-lg bg-[var(--panel)] border border-[var(--panel-border)]">{impact.impact_score}/100</span>}
      </div>
      {issue.snippet && <pre className="mono text-xs rounded-lg p-3 mt-2 overflow-x-auto whitespace-pre-wrap bg-[var(--code-bg)] border border-[var(--panel-border)]">{issue.snippet}</pre>}
      {mode === "static" ? (
        <FixRecipePanel fix={{ issue_id: issue.id, fix_instruction_tr: "", risk_level: 0, test_suggestion: "", improvement_estimate: "", recipe_valid: false }} disabled disabledMessage="Reçete Statik modda devre dışı — Hibrit veya Derin modu deneyin." />
      ) : fix ? <FixRecipePanel fix={fix} /> : (
        <FixRecipePanel fix={{ issue_id: issue.id, fix_instruction_tr: "Reçete üretiliyor veya LLM kullanılamadı.", risk_level: 0, test_suggestion: "", improvement_estimate: "", recipe_valid: false }} />
      )}
    </div>
  );
}
