"""HTML-превью с Open Graph для ботов WhatsApp/Telegram/соцсетей.

SPA не отдаёт meta-теги краулерам (они не выполняют JS). Эндпоинты ниже
отдают готовый HTML; nginx проксирует сюда запросы с User-Agent ботов.
"""

from __future__ import annotations

from html import escape

from fastapi import Request
from fastapi.responses import HTMLResponse


def public_origin(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def absolute_asset_url(origin: str, path: str) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{origin}{path}"


def render_og_html(
    *,
    title: str,
    description: str,
    canonical_url: str,
    image_url: str | None = None,
    site_name: str = "WaySklad",
) -> HTMLResponse:
    t = escape(title)
    d = escape(description)
    url = escape(canonical_url)
    site = escape(site_name)
    image_tags = ""
    if image_url:
        img = escape(image_url)
        image_tags = f"""
    <meta property="og:image" content="{img}" />
    <meta name="twitter:image" content="{img}" />
"""
    html = f"""<!DOCTYPE html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <title>{t}</title>
    <meta name="description" content="{d}" />
    <link rel="canonical" href="{url}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="{site}" />
    <meta property="og:title" content="{t}" />
    <meta property="og:description" content="{d}" />
    <meta property="og:url" content="{url}" />
    {image_tags}
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{t}" />
    <meta name="twitter:description" content="{d}" />
    <meta http-equiv="refresh" content="0;url={url}" />
  </head>
  <body>
    <p><a href="{url}">{t}</a></p>
  </body>
</html>
"""
    return HTMLResponse(content=html, headers={"Cache-Control": "public, max-age=60"})
