import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "KodHekim — AI Kod Sağlığı Tanı Sistemi",
  description:
    "Çoklu AI ajan ekibiyle repo'nuzu kazıyıp performans, RAM, güvenlik ve kalite sorunlarını tespit eden tanı sistemi. Dr. Müfettiş · Dr. Ölçücü · Dr. Cerrah · Dr. Hekimbaşı — 4 AI ajanı · 23 örüntü.",
  keywords: ["KodHekim", "AI", "kod analizi", "kod sağlığı", "tanı", "SaaS"],
  authors: [{ name: "MaNga-003 Team" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" className="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        {/* Tema titremesini önlemek için inline script */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('kodhekim-theme');if(t==='light'){document.documentElement.classList.remove('dark');document.documentElement.classList.add('light')}}catch(e){}})()`,
          }}
        />
      </head>
      <body className="antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
