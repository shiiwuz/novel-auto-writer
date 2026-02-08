from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


API_BASE = "https://api.telegra.ph"


def create_account(*, short_name: str, author_name: str | None = None, author_url: str | None = None, timeout_s: int = 60) -> dict[str, Any]:
    data: dict[str, str] = {"short_name": short_name}
    if author_name:
        data["author_name"] = author_name
    if author_url:
        data["author_url"] = author_url
    return _post_form(API_BASE + "/createAccount", data, timeout_s=timeout_s)


class TelegraphClient:
    def __init__(self, *, access_token: str, timeout_s: int = 60) -> None:
        self._access_token = access_token
        self._timeout_s = timeout_s

    def create_page(
        self,
        *,
        title: str,
        nodes: list[dict[str, Any]],
        author_name: Optional[str] = None,
        author_url: Optional[str] = None,
        return_content: bool = False,
    ) -> dict[str, Any]:
        data = {
            "access_token": self._access_token,
            "title": title,
            "content": json.dumps(nodes, ensure_ascii=False),
            "return_content": "true" if return_content else "false",
        }
        if author_name:
            data["author_name"] = author_name
        if author_url:
            data["author_url"] = author_url
        return _post_form(API_BASE + "/createPage", data, timeout_s=self._timeout_s)

    def edit_page(
        self,
        *,
        path: str,
        title: str,
        nodes: list[dict[str, Any]],
        author_name: Optional[str] = None,
        author_url: Optional[str] = None,
        return_content: bool = False,
    ) -> dict[str, Any]:
        data = {
            "access_token": self._access_token,
            "path": path,
            "title": title,
            "content": json.dumps(nodes, ensure_ascii=False),
            "return_content": "true" if return_content else "false",
        }
        if author_name:
            data["author_name"] = author_name
        if author_url:
            data["author_url"] = author_url
        return _post_form(API_BASE + "/editPage", data, timeout_s=self._timeout_s)


def _post_form(url: str, data: dict[str, str], *, timeout_s: int) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            resp_body = resp.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegraph HTTPError {e.code}: {msg}")

    obj = json.loads(resp_body)
    if not obj.get("ok"):
        raise RuntimeError(f"Telegraph API error: {obj}")
    return obj


def md_to_nodes(md: str) -> list[dict[str, Any]]:
    """Very small Markdown-to-Telegraph nodes.

    We keep it intentionally simple and predictable:
    - Blank line => new paragraph
    - '# ' => h3
    - '## ' => h4
    - Otherwise => p
    """
    lines = [ln.rstrip() for ln in md.replace("\r\n", "\n").split("\n")]

    nodes: list[dict[str, Any]] = []
    buf: list[str] = []

    def flush_paragraph() -> None:
        nonlocal buf
        text = " ".join([x.strip() for x in buf if x.strip()]).strip()
        buf = []
        if text:
            nodes.append({"tag": "p", "children": [text]})

    for ln in lines:
        if not ln.strip():
            flush_paragraph()
            continue
        if ln.startswith("# "):
            flush_paragraph()
            nodes.append({"tag": "h3", "children": [ln[2:].strip()]})
            continue
        if ln.startswith("## "):
            flush_paragraph()
            nodes.append({"tag": "h4", "children": [ln[3:].strip()]})
            continue
        buf.append(ln)

    flush_paragraph()
    return nodes


def index_nodes(book_title: str, intro: str, chapter_links: list[tuple[str, Optional[str]]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    nodes.append({"tag": "h3", "children": [book_title]})
    if intro.strip():
        nodes.extend(md_to_nodes(intro.strip()))
    items: list[Any] = []
    for ch_title, url in chapter_links:
        if url:
            items.append({"tag": "li", "children": [{"tag": "a", "attrs": {"href": url}, "children": [ch_title]}]})
        else:
            items.append({"tag": "li", "children": [ch_title + "（未发布）"]})
    nodes.append({"tag": "ul", "children": items})
    return nodes
