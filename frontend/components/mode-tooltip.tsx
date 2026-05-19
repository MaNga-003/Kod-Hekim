"use client";

import type { Mode } from "@/lib/api-client";

export type ModeTooltipMeta = {
  value: Mode;
  label: string;
  hint: string;
  summary: string;
  speed: string;
  token: string;
  scope: string;
  accuracy: string;
  icon: string;
};

export const MODE_TOOLTIPS: ModeTooltipMeta[] = [
  {
    value: "static",
    label: "Statik",
    hint: "Hızlı · LLM yok",
    icon: "⚡",
    summary:
      "Yalnızca kural motoru. En hızlı yol; LLM token tüketimi sıfır. CI/CD ve hızlı tarama için ideal.",
    speed: "⚡⚡⚡ (< 5 sn / ~50 dosya)",
    token: "0",
    scope: "23 statik örüntü · Python, JS, TS",
    accuracy: "Orta — beklenmedik örüntüleri kaçırabilir",
  },
  {
    value: "hybrid",
    label: "Hibrit",
    hint: "Önerilen · kural + LLM",
    icon: "🎯",
    summary:
      "Kural motoru aday bulguları üretir; LLM doğrulama ve etki analizi yapar. Dengeli hız ve doğruluk.",
    speed: "⚡⚡ (~30–90 sn)",
    token: "~80K",
    scope: "Statik kurallar + LLM confirm · 3 ajan",
    accuracy: "Yüksek — genel kullanım için önerilen varsayılan",
  },
  {
    value: "deep",
    label: "Derin",
    hint: "LLM-Direct · ağır",
    icon: "🔬",
    summary:
      "Kaynak kod ve AST doğrudan LLM'e gider. En geniş kapsam; en yavaş ve en pahalı mod.",
    speed: "⚡ (1–3 dk, repo boyutuna bağlı)",
    token: "~500K–900K",
    scope: "Tam kod + AST · beklenmedik örüntü avı",
    accuracy: "En yüksek bağlam — küçük-orta repolar için",
  },
];

type ModeOptionProps = {
  mode: ModeTooltipMeta;
  selected: boolean;
  disabled?: boolean;
  onSelect: (value: Mode) => void;
};

export function ModeOption({ mode, selected, disabled, onSelect }: ModeOptionProps) {
  const tooltipId = `mode-tooltip-${mode.value}`;

  return (
    <div className="relative flex-1 group/mode">
      <button
        type="button"
        onClick={() => onSelect(mode.value)}
        disabled={disabled}
        aria-describedby={tooltipId}
        id={`mode-btn-${mode.value}`}
        className={`mode-pill w-full text-left ${selected ? "active" : ""}`}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{mode.icon}</span>
          <div>
            <div className="font-semibold text-sm">{mode.label}</div>
            <div className="text-xs text-muted mt-0.5">{mode.hint}</div>
          </div>
        </div>
        {selected && (
          <div className="absolute top-2 right-2">
            <span className="inline-flex h-2 w-2 rounded-full bg-[var(--accent)]">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--accent)] opacity-75" />
            </span>
          </div>
        )}
      </button>

      {/* Glassmorphic Tooltip Micro-Card */}
      <div
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none absolute bottom-[calc(100%+0.75rem)] left-1/2 z-50 w-[min(20rem,calc(100vw-2rem))] -translate-x-1/2 tooltip-glass text-left opacity-0 invisible translate-y-2 transition-all duration-200 ease-out group-hover/mode:opacity-100 group-hover/mode:visible group-hover/mode:translate-y-0 group-focus-within/mode:opacity-100 group-focus-within/mode:visible group-focus-within/mode:translate-y-0"
      >
        {/* Accent top border glow */}
        <div className="absolute top-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent opacity-60" />

        <p className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-2">
          <span>{mode.icon}</span>
          <span>{mode.label} Analiz</span>
        </p>
        <p className="mt-2 text-xs text-muted-light leading-relaxed">{mode.summary}</p>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[11px]">
          <dt className="text-muted font-medium">Hız</dt>
          <dd className="text-[var(--foreground)]">{mode.speed}</dd>
          <dt className="text-muted font-medium">Token</dt>
          <dd className="mono text-[var(--accent)]">{mode.token}</dd>
          <dt className="text-muted font-medium">Kapsam</dt>
          <dd className="text-[var(--foreground)]">{mode.scope}</dd>
          <dt className="text-muted font-medium">Doğruluk</dt>
          <dd className="text-[var(--foreground)]">{mode.accuracy}</dd>
        </div>

        {/* Tooltip arrow */}
        <span
          aria-hidden
          className="absolute left-1/2 top-full -translate-x-1/2 border-8 border-transparent"
          style={{ borderTopColor: 'rgba(22, 31, 48, 0.92)' }}
        />
      </div>
    </div>
  );
}
