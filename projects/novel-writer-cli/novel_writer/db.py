from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def init_db(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS projects (
          project_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          blurb TEXT NOT NULL,
          created_at_utc TEXT NOT NULL,
          project_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chapters (
          project_id TEXT NOT NULL,
          chapter_idx INTEGER NOT NULL,
          chapter_title TEXT,
          chapter_json TEXT,
          chapter_text TEXT,
          chapter_summary TEXT,
          updated_at_utc TEXT NOT NULL,
          PRIMARY KEY (project_id, chapter_idx)
        );

        CREATE TABLE IF NOT EXISTS publishes (
          project_id TEXT NOT NULL,
          chapter_idx INTEGER NOT NULL,
          telegraph_path TEXT NOT NULL,
          telegraph_url TEXT NOT NULL,
          published_at_utc TEXT NOT NULL,
          PRIMARY KEY (project_id, chapter_idx)
        );
        """
    )
    con.commit()


def put_project(con: sqlite3.Connection, *, project_id: str, title: str, blurb: str, created_at_utc: str, project_obj: dict) -> None:
    cur = con.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO projects(project_id, title, blurb, created_at_utc, project_json) VALUES(?,?,?,?,?)",
        (project_id, title, blurb, created_at_utc, json.dumps(project_obj, ensure_ascii=False)),
    )
    con.commit()


def get_project(con: sqlite3.Connection, *, project_id: str) -> dict[str, Any]:
    cur = con.cursor()
    row = cur.execute("SELECT project_json FROM projects WHERE project_id=?", (project_id,)).fetchone()
    if not row:
        raise KeyError(f"project not found: {project_id}")
    return json.loads(row["project_json"])


def list_projects(con: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = con.cursor()
    rows = cur.execute("SELECT project_id, title, created_at_utc FROM projects ORDER BY created_at_utc DESC").fetchall()
    return [dict(r) for r in rows]


def put_chapter(
    con: sqlite3.Connection,
    *,
    project_id: str,
    chapter_idx: int,
    chapter_title: str,
    chapter_obj: dict[str, Any],
    chapter_text: str,
    chapter_summary: str,
    updated_at_utc: str,
) -> None:
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO chapters(
          project_id, chapter_idx, chapter_title, chapter_json, chapter_text, chapter_summary, updated_at_utc
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            project_id,
            int(chapter_idx),
            chapter_title,
            json.dumps(chapter_obj, ensure_ascii=False),
            chapter_text,
            chapter_summary,
            updated_at_utc,
        ),
    )
    con.commit()


def get_chapter(con: sqlite3.Connection, *, project_id: str, chapter_idx: int) -> Optional[dict[str, Any]]:
    cur = con.cursor()
    row = cur.execute(
        "SELECT chapter_idx, chapter_title, chapter_json, chapter_text, chapter_summary, updated_at_utc FROM chapters WHERE project_id=? AND chapter_idx=?",
        (project_id, int(chapter_idx)),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("chapter_json"):
        d["chapter_json"] = json.loads(d["chapter_json"])
    return d


def list_chapters(con: sqlite3.Connection, *, project_id: str) -> list[dict[str, Any]]:
    cur = con.cursor()
    rows = cur.execute(
        "SELECT chapter_idx, chapter_title, updated_at_utc FROM chapters WHERE project_id=? ORDER BY chapter_idx ASC",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def put_publish(
    con: sqlite3.Connection,
    *,
    project_id: str,
    chapter_idx: int,
    telegraph_path: str,
    telegraph_url: str,
    published_at_utc: str,
) -> None:
    cur = con.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO publishes(project_id, chapter_idx, telegraph_path, telegraph_url, published_at_utc) VALUES(?,?,?,?,?)",
        (project_id, int(chapter_idx), telegraph_path, telegraph_url, published_at_utc),
    )
    con.commit()


def get_publish(con: sqlite3.Connection, *, project_id: str, chapter_idx: int) -> Optional[dict[str, Any]]:
    cur = con.cursor()
    row = cur.execute(
        "SELECT chapter_idx, telegraph_path, telegraph_url, published_at_utc FROM publishes WHERE project_id=? AND chapter_idx=?",
        (project_id, int(chapter_idx)),
    ).fetchone()
    return dict(row) if row else None


def list_publishes(con: sqlite3.Connection, *, project_id: str) -> list[dict[str, Any]]:
    cur = con.cursor()
    rows = cur.execute(
        "SELECT chapter_idx, telegraph_url, published_at_utc FROM publishes WHERE project_id=? ORDER BY chapter_idx ASC",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]
