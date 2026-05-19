"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getModeComparison, getReport } from "@/lib/api-client";
import { downloadReportPdf } from "@/lib/download-report-pdf";

/**
 * Yedek PDF rotası — raporu yükler ve otomatik PDF indirir.
 */
export default function ReportPrintPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  const [err, setErr] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let cancelled = false;

    (async () => {
      try {
        let data = null;
        for (let i = 0; i < 40 && !cancelled; i++) {
          data = await getReport(jobId);
          if (data?.report) break;
          await new Promise((r) => setTimeout(r, 800));
        }
        if (cancelled) return;
        if (!data?.report) {
          setStatus("error");
          setErr("Rapor henüz hazır değil veya bulunamadı.");
          return;
        }

        const modeComp = await getModeComparison(jobId).catch(() => null);
        const result = await downloadReportPdf(data, { modeComp, jobId });

        if (!result.ok) {
          setStatus("error");
          setErr(result.message);
          return;
        }

        setStatus("done");
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setErr((e as Error).message || "Rapor yüklenemedi.");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (status === "error") {
    return (
      <main style={{ padding: 24, fontFamily: "system-ui", color: "#111", background: "#fff" }}>
        <h1>PDF hatası</h1>
        <p>{err}</p>
        <button type="button" onClick={() => window.close()}>
          Kapat
        </button>
      </main>
    );
  }

  return (
    <main style={{ padding: 24, fontFamily: "system-ui", color: "#111", background: "#fff" }}>
      <p>{status === "done" ? "PDF indirildi. Bu sekmeyi kapatabilirsiniz." : "PDF hazırlanıyor…"}</p>
      {status === "done" && (
        <button type="button" onClick={() => window.close()} style={{ marginTop: 12 }}>
          Kapat
        </button>
      )}
    </main>
  );
}
