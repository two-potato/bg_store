from __future__ import annotations

from urllib.parse import quote

from django import template


register = template.Library()


_PALETTES = (
    ("#1f6fe8", "#29b6ff", "#f5fbff"),
    ("#6f3df4", "#1f6fe8", "#f6f1ff"),
    ("#0f9f7f", "#28c7a1", "#f1fffb"),
    ("#ec5d2a", "#ff9a3c", "#fff7f2"),
    ("#0f172a", "#2b4fff", "#f8faff"),
    ("#b91c5c", "#ff4fa1", "#fff4fa"),
)


def _brand_name(value) -> str:
    if hasattr(value, "name"):
        return str(getattr(value, "name") or "").strip()
    return str(value or "").strip()


def _brand_initials(value) -> str:
    name = _brand_name(value)
    if not name:
        return "S"
    parts = [part for part in name.replace("&", " ").replace("/", " ").split() if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    token = parts[0] if parts else name
    return token[:2].upper()


def _palette_for_name(name: str) -> tuple[str, str, str]:
    if not name:
        return _PALETTES[0]
    checksum = sum(ord(char) for char in name)
    return _PALETTES[checksum % len(_PALETTES)]


@register.filter(name="brand_initials")
def brand_initials(value) -> str:
    return _brand_initials(value)


@register.filter(name="brand_logo_data_uri")
def brand_logo_data_uri(value) -> str:
    name = _brand_name(value)
    initials = _brand_initials(name)
    primary, accent, surface = _palette_for_name(name)
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" fill="none">
      <defs>
        <linearGradient id="g" x1="64" y1="64" x2="448" y2="448" gradientUnits="userSpaceOnUse">
          <stop stop-color="{primary}"/>
          <stop offset="1" stop-color="{accent}"/>
        </linearGradient>
      </defs>
      <rect width="512" height="512" rx="120" fill="{surface}"/>
      <rect x="48" y="48" width="416" height="416" rx="104" fill="url(#g)"/>
      <circle cx="398" cy="116" r="44" fill="white" fill-opacity="0.16"/>
      <circle cx="118" cy="392" r="58" fill="white" fill-opacity="0.10"/>
      <path d="M128 160C128 142.327 142.327 128 160 128H260C334.006 128 394 187.994 394 262C394 336.006 334.006 396 260 396H160C142.327 396 128 381.673 128 364V160Z" fill="white" fill-opacity="0.12"/>
      <text x="256" y="292" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="148" font-weight="800" fill="white">{initials}</text>
    </svg>
    """.strip()
    return f"data:image/svg+xml;charset=UTF-8,{quote(svg)}"
