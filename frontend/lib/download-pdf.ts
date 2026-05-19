"use client";

const A4_WIDTH_PX = 794;

/**
 * HTML içeriğini html2canvas + jsPDF ile otomatik PDF dosyası olarak indirir.
 */
export async function downloadHtmlAsPdf(html: string, filename: string): Promise<void> {
  if (typeof document === "undefined") {
    throw new Error("PDF indirme yalnızca tarayıcıda kullanılabilir.");
  }

  const parsed = new DOMParser().parseFromString(html, "text/html");
  const host = document.createElement("div");
  host.setAttribute("aria-hidden", "true");
  host.style.cssText = [
    "position:fixed",
    "left:0",
    "top:0",
    `width:${A4_WIDTH_PX}px`,
    "background:#fff",
    "z-index:-1",
    "opacity:0",
    "pointer-events:none",
    "overflow:visible",
  ].join(";");

  Array.from(parsed.querySelectorAll("style")).forEach((styleEl) => {
    host.appendChild(styleEl.cloneNode(true));
  });

  const content = document.createElement("div");
  content.style.width = `${A4_WIDTH_PX}px`;
  while (parsed.body.firstChild) {
    content.appendChild(parsed.body.firstChild);
  }
  host.appendChild(content);
  document.body.appendChild(host);

  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
  await new Promise((resolve) => setTimeout(resolve, 150));

  try {
    const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
      import("html2canvas"),
      import("jspdf"),
    ]);

    const captureHeight = Math.max(content.scrollHeight, content.offsetHeight, 1);
    const canvas = await html2canvas(content, {
      scale: 2,
      useCORS: true,
      backgroundColor: "#ffffff",
      logging: false,
      width: A4_WIDTH_PX,
      height: captureHeight,
      windowWidth: A4_WIDTH_PX,
      windowHeight: captureHeight,
    });

    if (canvas.width === 0 || canvas.height === 0) {
      throw new Error("PDF önizleme boş — tekrar deneyin.");
    }

    const pdf = new jsPDF({ orientation: "p", unit: "mm", format: "a4" });
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const imgWidth = pageWidth;
    const imgHeight = (canvas.height * pageWidth) / canvas.width;
    const imgData = canvas.toDataURL("image/jpeg", 0.92);

    let heightLeft = imgHeight;
    let position = 0;

    pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
    heightLeft -= pageHeight;

    while (heightLeft > 0) {
      position = heightLeft - imgHeight;
      pdf.addPage();
      pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
    }

    pdf.save(filename.endsWith(".pdf") ? filename : `${filename}.pdf`);
  } finally {
    document.body.removeChild(host);
  }
}

/** html2canvas başarısız olursa yazdırma penceresi açar. */
export function openPrintFallback(html: string): void {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  if (!win) {
    throw new Error("Pop-up engellendi — tarayıcıda pop-up izni verin.");
  }
}
