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
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    listModels().then(setModels).catch(() => {});
  }, []);

  const onStart = async () => {
    setErr("");
    if (!url.trim()) { setErr("GitHub URL gerekli."); return; }
    if (mode !== "static" && !providerAvailable) {
      setErr(`${provider.toUpperCase()}_API_KEY ayarlanmamış — backend .env dosyasını kontrol edin veya Statik mod seçin.`);
      return;
    }
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
  const providerAvailable = models?.providers[provider]?.available ?? false;
  const needsLlm = mode !== "static";
  const canStart = !needsLlm || providerAvailable;

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
            4 AI ajanı · 22 örüntü · Python, JavaScript, TypeScript
          </p>
        </header>

        {/* ─── KodHekim Nedir? ─── */}
        <section
          aria-label="KodHekim nedir"
          className="mb-6 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel)] p-6 shadow-lg float-up float-up-delay-1"
        >
          <h2 className="mb-3 text-lg font-semibold text-[var(--foreground)]">
            KodHekim Nedir?
          </h2>
          <p className="text-sm leading-relaxed text-[var(--muted-light)]">
            Bulut faturalarının yaklaşık dörtte biri (yılda küresel ölçekte{" "}
            <strong className="text-[var(--warn)]">183 milyar dolar</strong>)
            kötü yazılmış kod yüzünden boşa gidiyor; kimse bunu fark etmiyor,
            çünkü kimse ölçmüyor.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--muted-light)]">
            <strong className="text-[var(--foreground)]">KodHekim</strong> bu
            görünmez israfı 2 dakikada raporlayan ilk araç: hangi kod parçasının
            sunucuyu yorduğunu, faturayı şişirdiğini ve veri merkezinde
            litrelerce suyu boşa harcadığını tek tek söyler.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--foreground)]">
            Yani bizim ürünümüz şirketlere{" "}
            <em>&ldquo;bilinçsizce yaktıkları parayı&rdquo;</em> gösteriyor — bu,
            satılmayacak bir ürün değil;{" "}
            <strong>CTO&apos;ların her sabah açacağı dashboard.</strong>
          </p>
        </section>

        {/* ─── Piyasa Analizi ─── */}
        <section
          aria-label="Piyasa analizi"
          className="mb-10 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel)] p-6 shadow-lg float-up float-up-delay-2"
        >
          <h2 className="mb-3 text-lg font-semibold text-[var(--foreground)]">
            Piyasa Analizi
          </h2>
          <p className="text-sm leading-relaxed text-[var(--muted-light)]">
            <strong className="text-[var(--foreground)]">Gartner</strong>&apos;a
            göre 2024&apos;te global bulut bilişim harcaması{" "}
            <strong className="text-accent">679 milyar doları</strong> aştı.{" "}
            <strong className="text-[var(--foreground)]">
              Flexera State of the Cloud 2024
            </strong>{" "}
            raporu, bu harcamanın{" "}
            <strong className="text-[var(--warn)]">
              %27&apos;sinin boşa gittiğini
            </strong>{" "}
            (yılda yaklaşık{" "}
            <strong className="text-[var(--warn)]">183 milyar dolarlık</strong>{" "}
            kayıp) ortaya koyuyor. Sebep, çoğu zaman görünmez kalan kötü kod
            örüntüleridir.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--muted-light)]">
            Yalnızca Microsoft&apos;un veri merkezleri 2022&apos;de{" "}
            <strong className="text-[var(--foreground)]">
              6,4 milyar litre su
            </strong>{" "}
            tüketti; üç büyük bulut sağlayıcısının toplamı{" "}
            <strong className="text-[var(--foreground)]">
              20 milyar litreyi
            </strong>{" "}
            aşıyor. Bu israfın yalnızca <strong>%1&apos;inin</strong>{" "}
            kurtarılması bile küresel ölçekte yılda{" "}
            <strong className="text-accent">1,8 milyar dolar</strong> tasarruf
            ve{" "}
            <strong className="text-[var(--good)]">milyarlarca litre</strong>{" "}
            soğutma suyunun korunması anlamına gelir.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--foreground)]">
            Piyasanın talebi net:{" "}
            <em>
              bu görünmez israfı ölçülebilir, raporlanabilir hale getiren bir
              tanı aracı.
            </em>{" "}
            <strong>KodHekim tam olarak bunu yapar.</strong>
          </p>
        </section>

        {/* ─── Sistem Kısıtları ─── */}
        <section
          aria-label="Sistem kısıtları"
          className="mb-10 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel)] p-6 shadow-lg float-up float-up-delay-3"
        >
          <h2 className="mb-3 text-lg font-semibold text-[var(--foreground)]">
            Sistem Kısıtları{" "}
            <span className="text-sm font-normal text-muted">(demo için)</span>
          </h2>
          <ul className="space-y-4 text-sm text-[var(--muted-light)]">
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">•</span>
              <div className="flex-1">
                <div>
                  Sadece{" "}
                  <strong className="text-[var(--foreground)]">
                    public GitHub
                  </strong>{" "}
                  repoları analiz edilebilir
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Pro hedefi: private repo, GitLab, Bitbucket, Azure DevOps desteği
                </div>
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">•</span>
              <div className="flex-1">
                <div>
                  Maksimum repo boyutu:{" "}
                  <strong className="text-[var(--foreground)]">100 MB</strong>
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Pro hedefi: 5 GB&apos;a kadar (büyük monorepo desteği)
                </div>
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">•</span>
              <div className="flex-1">
                <div>
                  Tek seferde taranan dosya sayısı:{" "}
                  <strong className="text-[var(--foreground)]">200</strong>
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Pro hedefi: 50.000+ dosya (sınırsız akış işleme)
                </div>
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">•</span>
              <div className="flex-1">
                <div>
                  Desteklenen diller:{" "}
                  <strong className="text-[var(--foreground)]">
                    Python, JavaScript, TypeScript
                  </strong>
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Pro hedefi: Go, Java, Rust, C#, C++, PHP, Ruby (10+ dil)
                </div>
              </div>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent mt-0.5">•</span>
              <div className="flex-1">
                <div>
                  Ortalama analiz süresi:{" "}
                  <strong className="text-[var(--foreground)]">
                    30 sn – 3 dk
                  </strong>{" "}
                  (seçilen moda göre değişir)
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  Pro hedefi: büyük repolar için 5 – 15 dk, CI/CD entegrasyonu
                </div>
              </div>
            </li>
          </ul>
        </section>

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

          {/* Örnek Repolar */}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="text-muted">Örnek repolar:</span>
            {[
              {
                label: "sozlesme-risk-analizi",
                url: "https://github.com/burak-sisci/sozlesme-risk-analizi",
              },
              {
                label: "repo-arkeolog",
                url: "https://github.com/burak-sisci/repo-arkeolog",
              },
            ].map((repo) => (
              <button
                key={repo.url}
                type="button"
                onClick={() => setUrl(repo.url)}
                disabled={loading}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--panel-border)] bg-[var(--panel-2)] px-2.5 py-0.5 mono text-muted-light hover:border-[var(--accent)] hover:text-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label={`Örnek repo URL'sini yapıştır: ${repo.label}`}
              >
                <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                {repo.label}
              </button>
            ))}
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

          {/* Gelişmiş Ayarlar — daima görünür */}
          {mode !== "static" && (
            <div className="mt-5">
              <div className="mb-2 flex items-center gap-2 text-xs text-muted-light font-medium">
                <svg className="h-3.5 w-3.5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Gelişmiş: ajan başına model
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl border border-[var(--panel-border)] bg-[var(--panel-2)]">
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
            disabled={loading || !url.trim() || !canStart}
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

        {/* Jüri / ziyaretçi tanıtım bölümü */}
        <section
          aria-label="KodHekim hakkında"
          className="mt-12 grid gap-6 md:grid-cols-2"
        >
          <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--panel)] p-6 shadow-lg">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-lg">🚦</span>
              <h2 className="text-base font-semibold">Analiz Modları</h2>
            </div>
            <p className="mb-4 text-xs text-[var(--muted-light)] leading-relaxed">
              Repoya ne kadar derinlemesine bakılacağını siz seçersiniz. Üç mod,
              hız ile derinlik arasında farklı bir denge sunar.
            </p>
            <ul className="space-y-2.5 text-xs text-[var(--muted-light)]">
              <li>
                <strong className="text-[var(--foreground)]">⚡ Statik —</strong>{" "}
                yalnızca kural motoru çalışır, LLM tüketimi sıfırdır. CI/CD
                hattına entegre etmek için idealdir.
              </li>
              <li>
                <strong className="text-[var(--foreground)]">🎯 Hibrit (önerilen) —</strong>{" "}
                kural motoru bulguları AI ajanlarıyla doğrulanır, etkisi ölçülür
                ve düzeltme reçetesi yazılır. Günlük kullanım için en dengeli
                seçenek.
              </li>
              <li>
                <strong className="text-[var(--foreground)]">🔬 Derin —</strong>{" "}
                AST özeti ve kaynak kod doğrudan LLM&apos;e gönderilir,
                beklenmedik örüntüler tespit edilir. Küçük-orta repolar için
                önerilir.
              </li>
            </ul>
          </div>

          <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--panel)] p-6 shadow-lg">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-lg">🤖</span>
              <h2 className="text-base font-semibold">LLM Sağlayıcıları</h2>
            </div>
            <p className="mb-4 text-xs text-[var(--muted-light)] leading-relaxed">
              KodHekim iki büyük dil modeli sağlayıcısı ile çalışır. İstediğinizi
              seçebilir, ya da gelişmiş ayarlardan her ajan için ayrı model
              atayabilirsiniz.
            </p>
            <ul className="space-y-2.5 text-xs text-[var(--muted-light)]">
              <li>
                <strong className="text-[var(--foreground)]">⚡ Cerebras —</strong>{" "}
                Ultra hızlı çıkarım motoru (gpt-oss-120b, qwen, llama, glm-4.7).
                Pipeline&apos;ı saniyeler içinde tamamlar; canlı demo için
                önerilir.
              </li>
              <li>
                <strong className="text-[var(--foreground)]">✨ Gemini —</strong>{" "}
                Google DeepMind&apos;ın 2.5 Pro &amp; Flash modelleri. Daha uzun
                bağlam ve detaylı muhakeme; karmaşık repolarda tercih edilir.
              </li>
            </ul>
            <p className="mt-4 text-[11px] text-muted">
              Tüm LLM çağrılarında 90 sn timeout ve deterministik fallback
              vardır; sağlayıcı yanıtsız kalsa bile rapor üretilir.
            </p>
          </div>
        </section>

        <section
          aria-label="KodHekim 4 ajan ekibi"
          className="mt-6 rounded-xl border border-[var(--panel-border)] bg-[var(--panel)] p-6 shadow-lg"
        >
          <div className="mb-3 flex items-center gap-2">
            <span className="text-lg">👨‍⚕️</span>
            <h2 className="text-base font-semibold">4 Ajan Ekibi</h2>
          </div>
          <p className="mb-4 text-xs text-[var(--muted-light)] leading-relaxed">
            Hibrit ve Derin modlarda dört uzman ajan birbirinin çıktısı üzerine
            çalışır. Her ajan kendi alanında uzmanlaşmıştır.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-xs text-[var(--muted-light)]">
            <div className="rounded-lg border border-[var(--panel-border)] p-3">
              <div className="mb-1 font-semibold text-[var(--foreground)]">
                🔍 Dr. Müfettiş
              </div>
              <div>22 örüntüyü tespit eder, statik kuralı LLM ile doğrular.</div>
            </div>
            <div className="rounded-lg border border-[var(--panel-border)] p-3">
              <div className="mb-1 font-semibold text-[var(--foreground)]">
                📊 Dr. Ölçücü
              </div>
              <div>Sorunların teknik etkisini sayısallaştırır (sorgu, RAM, latency).</div>
            </div>
            <div className="rounded-lg border border-[var(--panel-border)] p-3">
              <div className="mb-1 font-semibold text-[var(--foreground)]">
                🩹 Dr. Cerrah
              </div>
              <div>Her bulguya sözel düzeltme reçetesi, risk ve test önerisi yazar.</div>
            </div>
            <div className="rounded-lg border border-[var(--panel-border)] p-3">
              <div className="mb-1 font-semibold text-[var(--foreground)]">
                ⚕️ Dr. Hekimbaşı
              </div>
              <div>Sağlık skoru hesaplar, yönetici özeti hazırlar.</div>
            </div>
          </div>
          <p className="mt-4 text-[11px] text-muted">
            BTK Akademi Hackathon 2026 — Finans Teması • Açık kaynak, MIT
            lisanslı, Türkçe arayüz.
          </p>
        </section>

        <SiteFooter />
      </div>
    </main>
  );
}
