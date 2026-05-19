"use client";

/**
 * KodHekim Marka Logosu — V2
 *
 * Konsept: GitHub (Kod/Düğümler) + Doktor (Tıbbi Haç/EKG) + Finans (Yükselen Trend)
 * Hexagon taban içinde sol alttan sağ üste giden EKG formunda bir büyüme grafiği.
 * Merkezdeki kesişim tıbbi bir haç oluşturuyor.
 * Parlak Mor ve Turkuaz-Mor gradientleri.
 */
export function KodHekimLogo({ size = 48, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="KodHekim Logosu"
    >
      <title>KodHekim</title>
      <defs>
        <linearGradient id="kh-logo-grad" x1="8" y1="56" x2="56" y2="8" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#7C3AED" />
          <stop offset="50%" stopColor="#B94FFF" />
          <stop offset="100%" stopColor="#00F2FE" />
        </linearGradient>
        <linearGradient id="kh-logo-bg" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="rgba(185, 79, 255, 0.15)" />
          <stop offset="100%" stopColor="rgba(124, 58, 237, 0.02)" />
        </linearGradient>
        <filter id="kh-logo-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Hexagon Arkaplan (Modüler / Teknoloji) */}
      <path
        d="M32 4L56 18V46L32 60L8 46V18L32 4Z"
        fill="url(#kh-logo-bg)"
        stroke="var(--panel-border)"
        strokeWidth="1.5"
      />

      {/* Finans Trendi & EKG Çizgisi (Sağlık + Büyüme) */}
      <path
        d="M12 44 L22 44 L28 24 L36 48 L44 20 L52 20"
        stroke="url(#kh-logo-grad)"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter="url(#kh-logo-glow)"
      />

      {/* Tıbbi Haç (Doktor/Tanı) - Grafiğin merkezine entegre */}
      <g filter="url(#kh-logo-glow)">
        <path
          d="M32 28 V44 M24 36 H40"
          stroke="#B94FFF"
          strokeWidth="3.5"
          strokeLinecap="round"
          opacity="0.6"
        />
      </g>

      {/* Git Commit Düğümleri (GitHub / Kod) */}
      <circle cx="12" cy="44" r="3" fill="#B94FFF" />
      <circle cx="28" cy="24" r="3.5" fill="#7C3AED" />
      <circle cx="36" cy="48" r="3.5" fill="#B94FFF" />
      <circle cx="52" cy="20" r="4" fill="#00F2FE" />
      
      {/* Parlak İç Düğüm (Canlılık) */}
      <circle cx="52" cy="20" r="1.5" fill="#FFFFFF" />
    </svg>
  );
}

/**
 * Yükleme durumları için animasyonlu stetoskop / trend ikonu
 */
export function StethoscopePulse({ size = 24 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="pulse-glow"
    >
      <path
        d="M4 14 L8 14 L12 6 L16 18 L20 10"
        stroke="#B94FFF"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
