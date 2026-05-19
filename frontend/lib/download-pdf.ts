"use client";

import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

const A4_WIDTH_PX = 794;

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeFilename(filename: string): string {
  return filename.endsWith(".pdf") ? filename : `${filename}.pdf`;
}

async function waitForLayout(): Promise<void> {
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
  await wait(200);
}

function addCanvasToPdf(canvas: HTMLCanvasElement, pdf: jsPDF): void {
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const imgData = canvas.toDataURL("image/png");
  const imgProps = pdf.getImageProperties(imgData);
  const imgHeight = (imgProps.height * pageWidth) / imgProps.width;

  let heightLeft = imgHeight;
  let position = 0;

  pdf.addImage(imgData, "PNG", 0, position, pageWidth, imgHeight);
  heightLeft -= pageHeight;

  while (heightLeft > 0) {
    position = heightLeft - imgHeight;
    pdf.addPage();
    pdf.addImage(imgData, "PNG", 0, position, pageWidth, imgHeight);
    heightLeft -= pageHeight;
  }
}

async function captureElement(element: HTMLElement, height: number, scale: number): Promise<HTMLCanvasElement> {
  const canvas = await html2canvas(element, {
    scale,
    useCORS: true,
    allowTaint: true,
    backgroundColor: "#ffffff",
    logging: false,
    width: A4_WIDTH_PX,
    height,
    windowWidth: A4_WIDTH_PX,
    windowHeight: height,
    scrollX: 0,
    scrollY: 0,
    x: 0,
    y: 0,
    foreignObjectRendering: false,
  });

  if (!canvas.width || !canvas.height) {
    throw new Error("PDF önizleme boş oluştu.");
  }

  return canvas;
}

/** iframe içinde tam HTML belgesi render edip yakalar. */
async function renderInIframe(html: string): Promise<{ element: HTMLElement; cleanup: () => void }> {
  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.cssText = `position:fixed;left:-12000px;top:0;width:${A4_WIDTH_PX}px;border:0;`;
  document.body.appendChild(iframe);

  const iDoc = iframe.contentDocument;
  if (!iDoc) {
    document.body.removeChild(iframe);
    throw new Error("PDF oluşturulamadı.");
  }

  iDoc.open();
  iDoc.write(html);
  iDoc.close();

  await waitForLayout();

  const body = iDoc.body;
  const height = Math.max(body.scrollHeight, body.offsetHeight, iDoc.documentElement.scrollHeight, 600);
  iframe.style.height = `${height}px`;
  body.style.width = `${A4_WIDTH_PX}px`;
  body.style.background = "#ffffff";

  await waitForLayout();

  return {
    element: body,
    cleanup: () => {
      if (iframe.parentNode) document.body.removeChild(iframe);
    },
  };
}

/** iframe başarısız olursa gizli div ile dener (opacity kullanılmaz). */
async function renderInDiv(html: string): Promise<{ element: HTMLElement; cleanup: () => void }> {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const host = document.createElement("div");
  host.setAttribute("aria-hidden", "true");
  host.style.cssText = `position:fixed;left:-12000px;top:0;width:${A4_WIDTH_PX}px;background:#fff;`;

  Array.from(parsed.querySelectorAll("style")).forEach((styleEl) => {
    host.appendChild(styleEl.cloneNode(true));
  });

  const content = document.createElement("div");
  content.style.width = `${A4_WIDTH_PX}px`;
  content.style.background = "#ffffff";
  while (parsed.body.firstChild) {
    content.appendChild(parsed.body.firstChild);
  }
  host.appendChild(content);
  document.body.appendChild(host);

  await waitForLayout();

  return {
    element: content,
    cleanup: () => {
      if (host.parentNode) document.body.removeChild(host);
    },
  };
}

async function captureHtml(html: string, scale: number): Promise<HTMLCanvasElement> {
  let lastError: Error | null = null;

  for (const render of [renderInIframe, renderInDiv]) {
    let cleanup: (() => void) | null = null;
    try {
      const { element, cleanup: remove } = await render(html);
      cleanup = remove;
      const height = Math.max(element.scrollHeight, element.offsetHeight, 600);
      return await captureElement(element, height, scale);
    } catch (err) {
      lastError = err as Error;
    } finally {
      cleanup?.();
    }
  }

  throw lastError ?? new Error("PDF oluşturulamadı.");
}

/**
 * HTML içeriğini html2canvas + jsPDF ile otomatik PDF dosyası olarak indirir.
 */
export async function downloadHtmlAsPdf(html: string, filename: string): Promise<void> {
  if (typeof document === "undefined") {
    throw new Error("PDF indirme yalnızca tarayıcıda kullanılabilir.");
  }

  let canvas: HTMLCanvasElement | null = null;
  let lastError: Error | null = null;

  for (const scale of [1.25, 1]) {
    try {
      canvas = await captureHtml(html, scale);
      break;
    } catch (err) {
      lastError = err as Error;
    }
  }

  if (!canvas) {
    throw lastError ?? new Error("PDF oluşturulamadı.");
  }

  const pdf = new jsPDF({ orientation: "p", unit: "mm", format: "a4", compress: true });
  addCanvasToPdf(canvas, pdf);
  pdf.save(normalizeFilename(filename));
}
