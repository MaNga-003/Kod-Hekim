"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { getJobStatus, type JobStatus } from "@/lib/api-client";
import { type SSEEvent, streamEvents } from "@/lib/sse-client";
import { KodHekimLogo } from "@/components/kodhekim-logo";
import { ThemeToggle } from "@/components/theme-provider";

type AgentName = "profiler" | "impact" | "surgeon" | "chief";
type AgentState = "pending" | "running" | "done";

const AGENTS: { name: AgentName; persona: string; icon: string; label: string; color: string }[] = [
  { name: "profiler", persona: "Dr. Müfettiş", icon: "🔍", label: "Kodun her köşesini tarıyor", color: "var(--accent)" },
  { name: "impact", persona: "Dr. Ölçücü", icon: "📊", label: "Sayısal etkiyi hesaplıyor", color: "var(--violet)" },
  { name: "surgeon", persona: "Dr. Cerrah", icon: "🩹", label: "Çözüm reçetesi yazıyor", color: "var(--good)" },
  { name: "chief", persona: "Dr. Hekimbaşı", icon: "⚕️", label: "Tanıyı raporluyor", color: "var(--warn)" },
];

interface LogLine {
  id: string;
  type: string;
  agent?: string;
  message: string;
  timestamp: string;
}

export default function AnalyzePage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const router = useRouter();

  const [agents, setAgents] = useState<Record<AgentName, AgentState>>({
    profiler: "pending", impact: "pending", surgeon: "pending", chief: "pending",
  });
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [issueCount, setIssueCount] = useState(0);
  const [error, setError] = useState<string>("");
  const [connectionWarning, setConnectionWarning] = useState<string>("");
  const [done, setDone] = useState(false);
  const [startTime] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);
  const logContainer = useRef<HTMLDivElement | null>(null);

  // Timer
  useEffect(() => {
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(tick);
  }, [startTime]);

  // SSE Stream
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;

    const stop = streamEvents(
      jobId,
      (ev: SSEEvent) => {
        if (cancelled) return;
        const agent = ev.data.agent as AgentName | undefined;

        if (ev.type === "agent_started" && agent && agent in agents) setAgents((s) => ({ ...s, [agent]: "running" }));
        if (ev.type === "agent_done" && agent && agent in agents) setAgents((s) => ({ ...s, [agent]: "done" }));
        if (ev.type === "issue_found") setIssueCount((c) => c + 1);
        if (ev.type === "error") setError((ev.data.message as string) ?? "bilinmeyen hata");
        
        if (ev.type !== "heartbeat") {
          setLogs((prev) => [
            ...prev.slice(-150),
            { id: Math.random().toString(36).slice(2), type: ev.type, agent, message: buildLogMessage(ev), timestamp: ev.timestamp },
          ]);
        }
        
        if (ev.type === "all_done") {
          setDone(true);
          setTimeout(() => router.push(`/report/${jobId}`), 1500);
        }
      },
      () => { if (!done && !cancelled) setConnectionWarning("Bağlantı koptu — yeniden deneniyor..."); }
    );

    return () => { cancelled = true; stop(); };
  }, [jobId, done, router]);

  // Fallback Polling
  useEffect(() => {
    if (done || error) return;
    const interval = setInterval(async () => {
      try {
        const s: JobStatus = await getJobStatus(jobId);
        if (s.status === "done") {
          setDone(true); setConnectionWarning("");
          setTimeout(() => router.push(`/report/${jobId}`), 600);
        } else if (s.status === "error") {
          setError(s.error || "analiz hata ile sonlandı");
        } else if (connectionWarning) {
          setConnectionWarning("");
        }
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [jobId, done, error, connectionWarning, router]);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainer.current) {
      logContainer.current.scrollTop = logContainer.current.scrollHeight;
    }
  }, [logs]);

  const elapsedStr = useMemo(() => {
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }, [elapsed]);

  const progressPercent = useMemo(() => {
    const values = Object.values(agents);
    const doneCount = values.filter((v) => v === "done").length;
    const runningCount = values.filter((v) => v === "running").length;
    return Math.min(100, Math.round(((doneCount * 100) + (runningCount * 50)) / 4));
  }, [agents]);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6 hero-gradient grid-pattern">
      <div className="fixed top-5 right-5 z-50"><ThemeToggle /></div>

      <div className="w-full max-w-5xl z-10">
        
        {/* ─── Üst Başlık ─── */}
        <header className="mb-10 text-center float-up">
          <div className="flex justify-center mb-6">
            <div className="relative">
              {/* Radar animasyon arkaplanı */}
              <div className="absolute inset-0 bg-[var(--accent)] opacity-20 rounded-full blur-2xl scale-[2.5] pulse-glow pointer-events-none" />
              <div className="relative bg-[var(--panel)] p-4 rounded-full border border-[var(--accent)] glow-accent">
                <KodHekimLogo size={64} />
              </div>
            </div>
          </div>
          <h1 className="text-3xl font-bold mb-2">Canlı Analiz Odası</h1>
          <div className="flex items-center justify-center gap-4 text-sm text-muted mono">
            <span>job: {jobId.split("-")[0]}</span>
            <span>•</span>
            <span className="text-accent">{progressPercent}%</span>
          </div>
        </header>

        {error ? (
          <div className="panel border-2 border-[var(--bad)] rounded-2xl p-8 mb-6 text-center glow-bad float-up">
            <div className="text-4xl mb-4">⚠️</div>
            <p className="text-xl font-bold text-bad">Operasyon Başarısız</p>
            <p className="text-muted mt-2">{error}</p>
            <button onClick={() => router.push("/")} className="btn-ghost mt-6">← Yeni Analiz Başlat</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            
            {/* ─── Sol: Ajanlar (Görev Dağılımı) ─── */}
            <div className="lg:col-span-5 space-y-4 float-up float-up-delay-1">
              <h2 className="text-sm font-semibold text-muted-light mb-2 flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-[var(--violet)] pulse-dot" />
                Teşhis Ekibi
              </h2>
              {AGENTS.map((a) => (
                <AgentCard key={a.name} agent={a} state={agents[a.name]} />
              ))}
              
              {/* Metrikler Kapsülü */}
              <div className="grid grid-cols-2 gap-4 mt-6">
                <div className="panel-2 rounded-xl p-4 border border-[var(--panel-border)] flex flex-col items-center justify-center">
                  <span className="text-xs text-muted mb-1">Geçen Süre</span>
                  <span className="text-2xl font-bold mono">{elapsedStr}</span>
                </div>
                <div className="panel-2 rounded-xl p-4 border border-[var(--panel-border)] flex flex-col items-center justify-center relative overflow-hidden">
                  <span className="text-xs text-muted mb-1">Bulunan Sorun</span>
                  <span className={`text-2xl font-bold mono ${issueCount > 0 ? 'text-warn glow-text-accent' : 'text-foreground'}`}>
                    {issueCount}
                  </span>
                  {issueCount > 0 && <div className="absolute inset-0 bg-[var(--warn)] opacity-5 pointer-events-none pulse-glow" />}
                </div>
              </div>
            </div>

            {/* ─── Sağ: Canlı Telemetri (Log) ─── */}
            <div className="lg:col-span-7 panel rounded-2xl h-[520px] flex flex-col border border-[var(--panel-border)] overflow-hidden float-up float-up-delay-2 relative">
              <div className="flex justify-between items-center bg-[var(--panel-2)] px-5 py-4 border-b border-[var(--panel-border)]">
                <h2 className="text-sm font-bold flex items-center gap-2">
                  <svg className="h-4 w-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  Canlı Telemetri
                </h2>
                {connectionWarning && <span className="text-xs font-semibold text-warn animate-pulse">⚠ {connectionWarning}</span>}
                {done && <span className="text-xs font-semibold text-good">✓ Tamamlandı</span>}
              </div>
              
              <div ref={logContainer} className="flex-1 overflow-y-auto p-5 font-mono text-[13px] leading-relaxed bg-[var(--background)]">
                {logs.length === 0 && <p className="text-muted italic flex items-center gap-2"><span className="animate-spin">⏳</span> Sistem dinleniyor...</p>}
                {logs.map((l) => (
                  <div key={l.id} className="flex items-start gap-3 mb-2 animate-[float-up_0.2s_ease-out]">
                    <span className="text-muted opacity-50 shrink-0 select-none">[{l.timestamp.slice(11, 19)}]</span>
                    <span className={`shrink-0 font-bold ${typeColor(l.type)}`}>
                      {l.agent ? `<${l.agent}>` : `[${l.type.replace('_', ' ').toUpperCase()}]`}
                    </span>
                    <span className="text-muted-light break-words">{l.message}</span>
                  </div>
                ))}
              </div>
              
              {/* Alt Fade Gölgesi */}
              <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-[var(--background)] to-transparent pointer-events-none" />
            </div>

          </div>
        )}

      </div>
    </main>
  );
}

/* ─── Alt Bileşenler ─── */

function AgentCard({ agent, state }: { agent: { name: string; persona: string; icon: string; label: string; color: string }; state: AgentState }) {
  const isRunning = state === "running";
  const isDone = state === "done";
  
  return (
    <div className={`relative panel-2 rounded-xl p-4 transition-all duration-500 overflow-hidden ${isRunning ? 'border-[var(--accent)] scale-[1.02] shadow-[0_0_20px_rgba(185,79,255,0.1)]' : 'border-[var(--panel-border)]'}`}>
      {/* Arkaplan Tarama Efekti */}
      {isRunning && (
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ background: `linear-gradient(90deg, transparent, ${agent.color}, transparent)`, backgroundSize: '200% 100%', animation: 'shimmer 2s infinite' }} />
      )}

      <div className="relative flex items-center gap-4 z-10">
        <div className={`flex items-center justify-center w-12 h-12 rounded-lg text-2xl bg-[var(--background)] border ${isDone ? 'border-[var(--good)]' : isRunning ? 'border-[var(--accent)]' : 'border-[var(--panel-border)]'}`}>
          {isDone ? <span className="text-good font-bold text-xl">✓</span> : agent.icon}
        </div>
        
        <div className="flex-1">
          <div className="font-bold text-sm text-foreground">{agent.persona}</div>
          <div className="text-xs text-muted mt-0.5">{agent.label}</div>
        </div>

        <div className="text-xs font-bold uppercase tracking-wider">
          {state === "pending" && <span className="text-muted opacity-50">Bekliyor</span>}
          {isRunning && <span className="text-accent flex items-center gap-2"><span className="pulse-dot">●</span> Çalışıyor</span>}
          {isDone && <span className="text-good">Tamam</span>}
        </div>
      </div>
      
      {/* Progress Bar Line */}
      <div className="absolute bottom-0 left-0 h-1 bg-[var(--panel-border)] w-full">
        <div className={`h-full transition-all duration-[2s] ${isDone ? 'w-full bg-[var(--good)]' : isRunning ? 'w-1/2 bg-[var(--accent)] shimmer' : 'w-0'}`} />
      </div>
    </div>
  );
}

function buildLogMessage(ev: SSEEvent): string {
  const d = ev.data;
  switch (ev.type) {
    case "clone_started": return `Repo çekiliyor: ${d.repo_url ?? ""}`;
    case "clone_done": return `Klonlama tamamlandı (${d.size_mb} MB, ${d.commit_sha})`;
    case "agent_started": return `Göreve başladı.`;
    case "agent_progress": return `${d.message ?? ""}`;
    case "agent_done": return `Görev tamamlandı${d.count !== undefined ? ` (İncelenen: ${d.count})` : ""}.`;
    case "issue_found": return `Kusur tespit edildi: ${d.code} (${d.severity}) — ${d.issue_id}`;
    case "impact_calculated": return `Etki ölçümü yapıldı: ${d.impact_score}/100`;
    case "fix_generated": return `Reçete oluşturuldu: (Risk seviyesi: ${d.risk_level}/5)${d.recipe_valid ? "" : " [DİKKAT: Kısmi Geçerlilik]"}`;
    case "all_done": return "Tüm analiz süreçleri başarıyla tamamlandı. Rapor derleniyor...";
    case "error": return `KRİTİK HATA: ${d.message ?? ""}`;
    default: return JSON.stringify(d).slice(0, 200);
  }
}

function typeColor(type: string): string {
  if (type === "error") return "text-bad";
  if (type === "all_done") return "text-good";
  if (type === "issue_found") return "text-warn";
  if (type === "fix_generated") return "text-violet";
  if (type === "agent_started" || type === "agent_done") return "text-accent";
  return "text-muted";
}
