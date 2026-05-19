"use client";

import { useState } from "react";

import type { FixSuggestion } from "@/lib/api-client";

type FixRecipePanelProps = {
  fix: FixSuggestion;
  disabled?: boolean;
  disabledMessage?: string;
};

export function FixRecipePanel({
  fix,
  disabled = false,
  disabledMessage,
}: FixRecipePanelProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (disabled) {
    return (
      <p className="text-xs text-muted mt-3 italic flex items-center gap-1.5">
        <svg className="h-3.5 w-3.5 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {disabledMessage ??
          "Çözüm reçetesi bu modda devre dışı — Hibrit veya Derin modu deneyin."}
      </p>
    );
  }

  const copyRecipe = () => {
    navigator.clipboard
      .writeText(fix.fix_instruction_tr)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => undefined);
  };

  const riskColor =
    fix.risk_level >= 4
      ? "text-bad"
      : fix.risk_level >= 3
      ? "text-warn"
      : "text-good";

  const riskDots = Array.from({ length: 5 }, (_, i) => i < fix.risk_level);

  return (
    <div className="mt-4 pt-4 border-t border-[var(--panel-border)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left text-sm font-semibold text-accent hover:text-[var(--accent-dim)] transition-colors no-print group"
      >
        <span className="flex items-center gap-2">
          <span className="text-base">℞</span>
          <span>Dr. Cerrah&apos;ın Çözüm Reçetesi</span>
        </span>
        <svg
          className={`h-4 w-4 transition-transform duration-200 text-muted group-hover:text-accent ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <div className={`mt-3 space-y-3 ${open ? "block" : "hidden print:block"}`}>
        {/* Meta info bar */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Risk level dots */}
          <div className="flex items-center gap-1">
            <span className="text-muted font-medium">Risk:</span>
            <div className="flex gap-0.5">
              {riskDots.map((active, i) => (
                <span
                  key={i}
                  className={`inline-block h-1.5 w-1.5 rounded-full transition ${
                    active ? riskColor : "bg-[var(--panel-border)]"
                  }`}
                  style={active ? { backgroundColor: fix.risk_level >= 4 ? "var(--bad)" : fix.risk_level >= 3 ? "var(--warn)" : "var(--good)" } : {}}
                />
              ))}
            </div>
            <span className={`${riskColor} font-medium`}>{fix.risk_level}/5</span>
          </div>

          <span className="text-[var(--panel-border)]">·</span>

          <span className="text-muted">
            <span className="text-good font-medium">↑</span> {fix.improvement_estimate}
          </span>

          {!fix.recipe_valid && (
            <>
              <span className="text-[var(--panel-border)]">·</span>
              <span className="text-warn flex items-center gap-1">
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                reçete kısmi/geçersiz
              </span>
            </>
          )}

          <button
            type="button"
            onClick={copyRecipe}
            className="ml-auto text-accent hover:text-[var(--accent-dim)] transition-colors flex items-center gap-1 no-print"
          >
            {copied ? (
              <>
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span>Kopyalandı</span>
              </>
            ) : (
              <>
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <span>Reçeteyi kopyala</span>
              </>
            )}
          </button>
        </div>

        {/* Test suggestion */}
        {fix.test_suggestion && (
          <p className="text-xs text-muted flex items-start gap-2">
            <span className="text-good font-semibold mt-0.5">🧪</span>
            <span><span className="font-medium text-good">Test:</span> {fix.test_suggestion}</span>
          </p>
        )}

        {/* Prescription Paper — The Doctor's Note */}
        <div className="prescription-paper whitespace-pre-line">
          {fix.fix_instruction_tr}
        </div>
      </div>
    </div>
  );
}
