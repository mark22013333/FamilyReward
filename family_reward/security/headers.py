"""安全性 HTTP Header。

自行用 after_request 實作，不為了幾個 Header 引入額外套件。
"""

from __future__ import annotations

from flask import Flask, Response

# FullCalendar 由 CDN 載入，因此 script/style 需要允許該來源。
# 樣式與少量行內 script 使用 'unsafe-inline'（本專案不接受使用者輸入的 HTML，
# 且 Jinja 自動跳脫保持啟用，風險可控）。
CSP_DIRECTIVES = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'",
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' https://cdn.jsdelivr.net data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def _apply_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CSP_DIRECTIVES)
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        return response
