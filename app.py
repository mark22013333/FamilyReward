"""WSGI 進入點。

保持很薄：實際的初始化都在 family_reward/app_factory.py。

用途：
* `flask --app app db upgrade` 等 Flask CLI 指令
* Waitress：`waitress-serve --call app:create_wsgi_app`
"""

from __future__ import annotations

from family_reward import create_app

app = create_app()


def create_wsgi_app():  # noqa: ANN201
    """給 waitress-serve --call 使用。"""
    return create_app()


if __name__ == "__main__":
    # 開發時的方便入口。正式環境請使用 start.bat（Waitress）。
    settings = app.settings  # type: ignore[attr-defined]
    app.run(host=settings.server.host, port=settings.server.port, debug=settings.app.debug)
