"""GET /api/badge/:owner/:repo.svg — README'ye eklenebilen SVG rozeti.

MVP: Cache veya hesap geçmişi yok → "unscored" rozeti döndürür.
Sonraki sürüm: cached_demos veya kullanıcı geçmişinden gerçek skor okunur
(developer.md §16.4).
"""

from __future__ import annotations

from fastapi import APIRouter, Response


router = APIRouter(prefix="/api", tags=["badge"])


# Skor → renk paleti (developer.md §16.4)
def _color(score: int) -> str:
    if score >= 90:
        return "#4c1"
    if score >= 70:
        return "#97CA00"
    if score >= 50:
        return "#dfb317"
    if score >= 30:
        return "#fe7d37"
    return "#e05d44"


def render_badge_svg(label: str, value: str, value_color: str) -> str:
    """shields.io tarzı 2-bölmeli SVG (label + value)."""
    label_w = max(64, 8 * len(label) + 12)
    value_w = max(64, 8 * len(value) + 12)
    total_w = label_w + value_w
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img">
  <linearGradient id="grad" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="{total_w}" height="20" fill="#555"/>
  <rect rx="3" x="{label_w}" width="{value_w}" height="20" fill="{value_color}"/>
  <path fill="{value_color}" d="M{label_w} 0h4v20h-4z"/>
  <rect rx="3" width="{total_w}" height="20" fill="url(#grad)"/>
  <g fill="#fff" text-anchor="middle"
     font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_w / 2}" y="14">{label}</text>
    <text x="{label_w + value_w / 2}" y="14">{value}</text>
  </g>
</svg>"""


def _build_score_badge(score: int) -> str:
    return render_badge_svg("kodhekim", f"{score}/100", _color(score))


def _build_unscored_badge() -> str:
    return render_badge_svg("kodhekim", "unscored", "#9f9f9f")


@router.get("/badge/{owner}/{repo}.svg")
async def badge(owner: str, repo: str, score: int | None = None) -> Response:
    """SVG badge döndür.

    `?score=78` query param verilirse o skoru renklendir; yoksa "unscored".
    (MVP'de skor cache'i yok — query parametresi geçmek mümkün.)
    """
    if score is not None and 0 <= score <= 100:
        svg = _build_score_badge(score)
    else:
        svg = _build_unscored_badge()

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600",
            # Markdown'da ![]() embed için CORS gerekmez ama yine de açık
            "Access-Control-Allow-Origin": "*",
        },
    )
