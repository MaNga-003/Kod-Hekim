"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  type Mode,
  type ModelsResponse,
  type Provider,
  listModels,
  startAnalysis,
} from "@/lib/api-client";
import { MODE_TOOLTIPS, ModeOption } from "@/components/mode-tooltip";
import { SiteFooter } from "@/components/site-footer";
import { KodHekimLogo } from "@/components/kodhekim-logo";
import { ThemeToggle } from "@/components/theme-provider";

type ModelMap = {
  profiler?: string;
  impact?: string;
  surgeon?: string;
  chief?: string;
  deep?: string;
};

const PROVIDERS: { value: Provider; label: string; desc: string; icon: string }[] = [
  { value: "cerebras", label: "Cerebras", desc: "Ultra-hızlı çıkarım motoru", icon: "⚡" },
  { value: "gemini", label: "Gemini", desc: "Google DeepMind modeli", icon: "✦" },
];

export default function LandingPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<Mode>("hybrid");
  const [provider, setProvider] = useState<Provider>("cerebras");
  const [models, setModels] = useState<ModelsResponse | null>(null);
  const [overrides, setOverrides] = useState<ModelMap>({});
  const [advanced, setAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    listModels().then(setModels).catch(() => {});
  }, []);

  const onStart = async () => {
    setErr("");
    if (!url.trim()) { setErr("GitHub URL gerekli."); return; }
    setLoading(true);
    try {
      const cleanOverrides = Object.fromEntries(Object.entries(overrides).filter(([, v]) => Boolean(v)));
      const { job_id } = await startAnalysis({
        repo_url: url.trim(), mode, provider,
        model_overrides: Object.keys(cleanOverrides).length > 0 ? (cleanOverrides as Record<string, string>) : undefined,
      });
      router.push(`/analyze/${job_id}`);
    } catch (e) {
      if (e instanceof ApiError) { setErr(`Backend hatası (${e.status}): ${JSON.stringify(e.detail) || e.message}`); }
      else { setErr((e as Error)?.message || "Bilinmeyen hata"); }
      setLoading(false);
    }
  };

  const providerModels = models?.providers[provider]?.models ?? [];
  const providerDefaults = models?.providers[provider]?.defaults ?? {};
  const providerAvailable = models?.providers[provider]?.available ?? true;

  return (
    <main className="min-h-screen flex flex-col items-center hero-gradient grid-pattern">
      {/* Tema Değiştirme */}
      <div className="fixed top-5 right-5 z-50">
        <ThemeToggle />
      </div>

      <div className="relative z-10 w-full max-w-2xl px-6 py-16">

        {/* ─── Logo & Hero ─── */}
        <header className="mb-12 text-center float-up">
          {/* Büyük & Etkileyici Logo */}
          <div className="flex justify-center mb-5">
            <div className="relative p-4">
              <KodHekimLogo size={88} />
              <div className="absolute inset-0 bg-[var(--accent)] opacity-[0.08] rounded-full blur-2xl scale-[2] pointer-events-none" />
            </div>
          </div>

          <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
            <span className="text-accent glow-text-accent">Kod</span>
            <span>Hekim</span>
          </h1>

          <p className="mt-3 text-base text-muted-light max-w-sm mx-auto leading-relaxed">
            Repo&rsquo;nun kod sağlığını ölç. Sunucunu yoran örüntüleri bul.
          </p>

          {/* Ajan Rozetleri */}
          <div className="mt-4 flex flex-wrap justify-center gap-1.5">
            {[
              { name: "Dr. Müfettiş", color: "var(--accent)" },
              { name: "Dr. Ölçücü", color: "var(--violet)" },
              { name: "Dr. Cerrah", color: "var(--good)" },
              { name: "Dr. Hekimbaşı", color: "var(--warn)" },
            ].map((agent) => (
              <span
                key={agent.name}
                className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium"
                style={{
                  background: `color-mix(in srgb, ${agent.color} 10%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${agent.color} 20%, transparent)`,
                  color: agent.color,
                }}
              >
                <span className="inline-block h-1 w-1 rounded-full" style={{ background: agent.color }} />
                {agent.name}
              </span>
            ))}
          </div>

          <p className="mt-2 text-[11px] text-muted mono">
            4 AI ajanı · 23 örüntü · Python, JavaScript, TypeScript
          </p>
        </header>

        {/* ─── Ana Panel ─── */}
        <div className="panel rounded-2xl p-7 glow-accent float-up float-up-delay-1">

          {/* URL Girişi */}
          <label className="block text-sm font-medium text-muted-light mb-2" htmlFor="repo-url-input">
            GitHub Repo URL
          </label>
          <div className="relative">
            <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <input
              id="repo-url-input"
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onStart()}
              placeholder="https://github.com/kullanici/repo"
              className="input-glass w-full pl-10 mono text-sm"
              spellCheck={false}
              disabled={loading}
            />
          </div>

          {/* Analiz Modu */}
          <div className="mt-6 float-up float-up-delay-2">
            <label className="block text-sm font-medium text-muted-light mb-2">Analiz Modu</label>
            <div className="flex gap-2">
              {MODE_TOOLTIPS.map((m) => (
                <ModeOption key={m.value} mode={m} selected={mode === m.value} disabled={loading} onSelect={setMode} />
              ))}
            </div>
          </div>

          {/* LLM Sağlayıcısı — Dikey Kartlar */}
          <div className="mt-6 float-up float-up-delay-3">
            <label className="block text-sm font-medium text-muted-light mb-2">LLM Sağlayıcısı</label>
            <div className="flex flex-col gap-2">
              {PROVIDERS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  id={`provider-btn-${p.value}`}
                  onClick={() => setProvider(p.value)}
                  disabled={loading}
                  className={`provider-card ${provider === p.value ? "active" : ""}`}
                >
                  <div className="provider-radio" />
                  <div className="flex items-center gap-2 flex-1">
                    <span className="text-lg">{p.icon}</span>
                    <div>
                      <div className="font-medium text-sm">{p.label}</div>
                      <div className="text-[11px] text-muted">{p.desc}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
            {!providerAvailable && models && (
              <p className="text-xs text-warn mt-2 flex items-center gap-1">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                {provider.toUpperCase()}_API_KEY ayarlanmamış. Statik mod yine de çalışır.
              </p>
            )}
          </div>

          {/* Gelişmiş Ayarlar */}
          {mode !== "static" && (
            <div className="mt-5">
              <button
                type="button"
                onClick={() => setAdvanced((v) => !v)}
                className="text-xs text-accent hover:underline transition-colors flex items-center gap-1"
              >
                <svg className={`h-3 w-3 transition-transform duration-200 ${advanced ? "rotate-90" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                {advanced ? "Gelişmiş ayarları gizle" : "Gelişmiş: ajan başına model"}
              </button>
              {advanced && (
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl border border-[var(--panel-border)] bg-[var(--panel-2)]">
                  {(["profiler", "impact", "surgeon", "chief", "deep"] as const).map((agent) => (
                    <div key={agent}>
                      <label className="text-[11px] text-muted block mb-1 capitalize font-medium">{agent}</label>
                      <select
                        value={overrides[agent] ?? ""}
                        onChange={(e) => setOverrides({ ...overrides, [agent]: e.target.value })}
                        className="w-full bg-[var(--input-bg)] border border-[var(--panel-border)] rounded-lg px-3 py-2 text-sm mono text-[var(--foreground)] outline-none focus:border-[var(--accent)] transition"
                      >
                        <option value="">varsayılan ({providerDefaults[agent] ?? "?"})</option>
                        {providerModels.map((m) => (<option key={m} value={m}>{m}</option>))}
                      </select>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Hata */}
          {err && (
            <div className="mt-4 rounded-xl border border-[var(--bad)] bg-[var(--bad-glow)] p-3 text-sm text-bad flex items-start gap-2">
              <svg className="h-4 w-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{err}</span>
            </div>
          )}

          {/* Başlat Butonu */}
          <button
            type="button"
            id="start-analysis-btn"
            onClick={onStart}
            disabled={loading || !url.trim()}
            className="btn-primary mt-6 w-full py-3.5 text-sm flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Analiz Başlatılıyor…</span>
              </>
            ) : (
              <>
                <span>🩺</span>
                <span>Tanı Başlat</span>
              </>
            )}
          </button>
        </div>

        <SiteFooter />
      </div>
    </main>
  );
}
