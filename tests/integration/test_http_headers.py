"""HTTP 回應標頭的相容性測試。

背景：HTTP header 只能是 latin-1。曾經因為把中文的 app 名稱
放進 Waitress 的 ident（Server header），導致每個請求都拋
UnicodeEncodeError 而整站無法使用。這裡防止同樣的問題再發生。
"""

from __future__ import annotations

import pytest


def _all_header_values(response):  # noqa: ANN001, ANN202
    return [(key, value) for key, value in response.headers.items()]


@pytest.mark.parametrize(
    "path",
    ["/", "/health", "/login/admin", "/this-page-does-not-exist"],
)
def test_headers_are_latin1_encodable(client, child, path):
    """所有回應標頭都必須能以 latin-1 編碼，否則 WSGI server 會炸。"""
    response = client.get(path)

    for key, value in _all_header_values(response):
        try:
            key.encode("latin-1")
            value.encode("latin-1")
        except UnicodeEncodeError:  # pragma: no cover - 失敗時才會走到
            pytest.fail(f"{path} 的標頭 {key}: {value!r} 不是 latin-1 可編碼的內容")


def test_launcher_server_ident_is_ascii():
    """Waitress 的 ident 會寫進 Server header，必須是純 ASCII。"""
    import inspect

    import launcher

    source = inspect.getsource(launcher.serve)
    assert 'ident="FamilyReward"' in source, "Waitress ident 必須是 ASCII 字串"


def test_html_body_is_utf8(client, child):
    """畫面內容仍然是 UTF-8 中文，不得亂碼。"""
    response = client.get("/")

    assert "charset=utf-8" in response.headers["Content-Type"].lower()
    assert "今天是誰要開始冒險呢" in response.get_data(as_text=True)
