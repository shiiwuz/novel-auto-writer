from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(s: str) -> str:
    s = s.strip().lower()
    # keep ascii letters/digits; turn other runs into '-'
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "project"


def project_id_from_title(title: str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return f"{slugify(title)[:40]}-{ts}"


def extract_first_json_object(text: str) -> Any:
    """Extract the first top-level JSON object from an LLM response.

    Avoid O(n^2) backtracking on large JSON by using a single-pass brace matcher.
    """
    # Common patterns: ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    if start == -1:
        raise ValueError("No '{' found in response")

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                return json.loads(chunk)
            continue

    raise ValueError("Failed to find a complete JSON object in response")


@dataclass(frozen=True)
class Env:
    openai_base_url: str
    openai_api_key: str
    novel_outline_model: str
    novel_writer_model: str
    telegraph_access_token: str
    db_path: Path
    outputs_dir: Path


def load_env() -> Env:
    base_url = (os.environ.get("OPENAI_BASE_URL") or os.environ.get("EMBEDDINGS_BASE_URL") or "").strip()
    api_key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("EMBEDDINGS_API_KEY") or "").strip()
    outline_model = (os.environ.get("NOVEL_OUTLINE_MODEL") or "gemini-3-pro-preview").strip()
    writer_model = (os.environ.get("NOVEL_WRITER_MODEL") or "gemini-3-flash-preview").strip()
    tg_token = (os.environ.get("TELEGRAPH_ACCESS_TOKEN") or "").strip()

    db_path = Path(os.environ.get("NOVEL_DB_PATH") or "./data/novels.db")
    outputs_dir = Path(os.environ.get("NOVEL_OUTPUTS_DIR") or "./outputs")

    if not base_url:
        raise SystemExit("Missing OPENAI_BASE_URL (or EMBEDDINGS_BASE_URL)")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY (or EMBEDDINGS_API_KEY)")

    return Env(
        openai_base_url=base_url.rstrip("/"),
        openai_api_key=api_key,
        novel_outline_model=outline_model,
        novel_writer_model=writer_model,
        telegraph_access_token=tg_token,
        db_path=db_path,
        outputs_dir=outputs_dir,
    )


def require_telegraph_token(env: Env) -> None:
    if not env.telegraph_access_token:
        raise SystemExit("Missing TELEGRAPH_ACCESS_TOKEN")
