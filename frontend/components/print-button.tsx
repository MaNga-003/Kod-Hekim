"use client";

import { useState } from "react";

import type {
  ModeComparisonResponse,
  ReportPayload,
  SimulateResponse,
} from "@/lib/api-client";
import { downloadReportPdf } from "@/lib/download-report-pdf";

type PrintButtonProps = {
  data: ReportPayload;
  jobId: string;
  modeComp?: ModeComparisonResponse | null;
  simulated?: SimulateResponse | null;
  className?: string;
  variant?: "fab" | "inline";
};

export function PrintButton({
  data,
  jobId,
  modeComp,
  simulated,
  className,
  variant = "inline",
}: PrintButtonProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const handleClick = async () => {
    if (!data.report || busy) return;

    setBusy(true);
    setMessage("");

    const result = await downloadReportPdf(data, { modeComp, simulated, jobId });

    setBusy(false);

    if (!result.ok) {
      setMessage(result.message);
      return;
    }

    setMessage(result.message ?? "PDF indirildi.");
    window.setTimeout(() => setMessage(""), 4000);
  };

  if (variant === "fab") {
    return (
      <>
        <button
          type="button"
          id="print-fab-btn"
          className="print-fab no-print flex items-center gap-2"
          onClick={handleClick}
          disabled={busy || !data.report}
        >
          {busy ? (
            <>
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Hazırlanıyor…</span>
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
              </svg>
              <span>Yazdır</span>
            </>
          )}
        </button>
        {message && (
          <div className="fixed bottom-20 right-6 z-50 tooltip-glass text-xs text-muted no-print max-w-xs">
            {message}
          </div>
        )}
      </>
    );
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        type="button"
        id="print-inline-btn"
        className={
          className ??
          "no-print btn-primary px-4 py-2 text-sm flex items-center gap-2"
        }
        onClick={handleClick}
        disabled={busy || !data.report}
      >
        {busy ? (
          <>
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>PDF hazırlanıyor…</span>
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            <span>Yazdır</span>
          </>
        )}
      </button>
      {message && <p className="text-xs text-muted max-w-xs text-right">{message}</p>}
    </div>
  );
}
