"use client";

import type {
  ModeComparisonResponse,
  ReportPayload,
  SimulateResponse,
} from "./api-client";
import { downloadHtmlAsPdf } from "./download-pdf";
import { buildPrintDocument, type PrintReportResult } from "./print-report";

/** Butona basıldığında PDF oluşturur ve otomatik indirir. */
export async function downloadReportPdf(
  data: ReportPayload,
  opts?: {
    modeComp?: ModeComparisonResponse | null;
    simulated?: SimulateResponse | null;
    jobId?: string;
  },
): Promise<PrintReportResult> {
  if (typeof document === "undefined") {
    return { ok: false, message: "PDF indirme yalnızca tarayıcıda kullanılabilir." };
  }
  if (!data.report) {
    return { ok: false, message: "Rapor verisi henüz hazır değil." };
  }

  const id = opts?.jobId || data.job_id;
  const filename = `KodHekim-Tani-${id}.pdf`;
  const html = buildPrintDocument(data, { ...opts, forExport: true });

  try {
    await downloadHtmlAsPdf(html, filename);
    return { ok: true, message: `${filename} indirildi.` };
  } catch (err) {
    const msg = (err as Error).message || "PDF oluşturulamadı.";
    return { ok: false, message: msg };
  }
}
