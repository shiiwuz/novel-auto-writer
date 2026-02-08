from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import utils
from .db import (
    connect,
    get_chapter,
    get_project,
    get_publish,
    init_db,
    list_chapters,
    list_projects,
    list_publishes,
    put_chapter,
    put_project,
    put_publish,
)
from .llm import OpenAICompatClient
from .orchestrator import generate_chapter, generate_project_plan, get_prev_context_from_db
from .telegraph import TelegraphClient, create_account, index_nodes, md_to_nodes
from .envfile import get_env_var, set_env_var
from .utils import now_utc_iso, project_id_from_title, read_text, write_json, write_text


def cmd_init(args: argparse.Namespace) -> int:
    env = utils.load_env()
    con = connect(env.db_path)
    init_db(con)

    title = args.title.strip()
    if args.topic_file:
        blurb = read_text(Path(args.topic_file)).strip()
    else:
        blurb = args.blurb.strip()

    project_id = args.project_id or project_id_from_title(title)

    client = OpenAICompatClient(base_url=env.openai_base_url, api_key=env.openai_api_key)
    plan = generate_project_plan(env=env, client=client, project_id=project_id, title=title, blurb=blurb)

    put_project(con, project_id=project_id, title=title, blurb=blurb, created_at_utc=now_utc_iso(), project_obj=plan)

    # Write a small manifest for convenience.
    out_dir = env.outputs_dir / project_id
    write_json(out_dir / "manifest.json", {"project_id": project_id, "title": title})

    print(project_id)
    return 0


def _current_project_path(env: utils.Env) -> Path:
    # Persist "current project" next to the DB for convenience.
    return env.db_path.parent / "current_project.txt"


def _get_default_project_id(env: utils.Env) -> str | None:
    p = _current_project_path(env)
    if not p.exists():
        return None
    pid = read_text(p).strip()
    return pid or None


def _require_project_id(env: utils.Env, arg_project: str | None) -> str:
    pid = (arg_project or "").strip() or _get_default_project_id(env) or ""
    if not pid:
        raise SystemExit("Missing --project and no current project set. Use set-current or pass --project.")
    return pid


def cmd_set_current(args: argparse.Namespace) -> int:
    env = utils.load_env()
    con = connect(env.db_path)
    init_db(con)

    # Validate the project exists.
    _ = get_project(con, project_id=args.project)

    write_text(_current_project_path(env), args.project.strip() + "\n")
    print(args.project.strip())
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    env = utils.load_env()
    pid = _get_default_project_id(env)
    if not pid:
        print("(none)")
        return 1

    con = connect(env.db_path)
    init_db(con)
    proj = get_project(con, project_id=pid)
    title = proj.get("topic", {}).get("title") or proj.get("topic", {}).get("title") or ""
    print(f"{pid}\t{title}")
    return 0


def cmd_list_projects(args: argparse.Namespace) -> int:
    env = utils.load_env()
    con = connect(env.db_path)
    init_db(con)
    rows = list_projects(con)
    for r in rows:
        print(f"{r['project_id']}\t{r['created_at_utc']}\t{r['title']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    env = utils.load_env()
    con = connect(env.db_path)
    init_db(con)

    pid = _require_project_id(env, getattr(args, "project", None))
    proj = get_project(con, project_id=pid)
    print(f"project\t{pid}\t{proj.get('topic', {}).get('title', '')}")

    chs = list_chapters(con, project_id=pid)
    pubs = {p["chapter_idx"]: p for p in list_publishes(con, project_id=pid)}

    for ch in range(1, 9):
        row = next((x for x in chs if int(x["chapter_idx"]) == ch), None)
        have = "Y" if row else "N"
        pub = pubs.get(ch)
        pub_s = pub["telegraph_url"] if pub else "-"
        title = row["chapter_title"] if row and row.get("chapter_title") else "-"
        print(f"ch{ch}\t{have}\t{title}\t{pub_s}")

    idx_pub = pubs.get(0)
    if idx_pub:
        print(f"index\t{idx_pub['telegraph_url']}")
    return 0


def cmd_write_chapter(args: argparse.Namespace) -> int:
    env = utils.load_env()
    con = connect(env.db_path)
    init_db(con)

    pid = _require_project_id(env, getattr(args, "project", None))

    project_obj = get_project(con, project_id=pid)

    chapter_idx = int(args.chapter)
    if not (1 <= chapter_idx <= 8):
        raise SystemExit("--chapter must be in 1..8")

    prev_summary, prev_last_para = get_prev_context_from_db(con, project_id=pid, chapter_idx=chapter_idx)

    client = OpenAICompatClient(base_url=env.openai_base_url, api_key=env.openai_api_key)
    ch_obj = generate_chapter(
        env=env,
        client=client,
        project_id=pid,
        project_obj=project_obj,
        chapter_idx=chapter_idx,
        prev_chapter_summary=prev_summary,
        prev_last_paragraph=prev_last_para,
    )

    put_chapter(
        con,
        project_id=pid,
        chapter_idx=chapter_idx,
        chapter_title=str(ch_obj.get("title") or ""),
        chapter_obj=ch_obj,
        chapter_text=str(ch_obj.get("chapter_text") or ""),
        chapter_summary=str(ch_obj.get("chapter_summary") or ""),
        updated_at_utc=now_utc_iso(),
    )

    print(f"ok\t{pid}\tch{chapter_idx}")
    return 0


def _telegraph_author() -> tuple[str | None, str | None]:
    name = os.environ.get("TELEGRAPH_AUTHOR_NAME")
    url = os.environ.get("TELEGRAPH_AUTHOR_URL")
    return (name.strip() if name else None, url.strip() if url else None)


def cmd_telegraph_init(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file)

    existing = get_env_var(env_path, "TELEGRAPH_ACCESS_TOKEN")
    if existing and existing.strip() and not args.force:
        msg = (
            f"WARNING: {env_path} already has TELEGRAPH_ACCESS_TOKEN. "
            "Refusing to overwrite without confirmation."
        )
        if sys.stdin.isatty():
            print(msg)
            confirm = input("Type REPLACE to overwrite TELEGRAPH_ACCESS_TOKEN: ").strip()
            if confirm != "REPLACE":
                print("aborted")
                return 2
        else:
            print(msg)
            print("Re-run with --force to overwrite.")
            return 2

    resp = create_account(
        short_name=args.short_name,
        author_name=args.author_name,
        author_url=args.author_url,
    )
    result = resp.get("result") or {}
    token = result.get("access_token")
    auth_url = result.get("auth_url")
    if not token:
        raise SystemExit(f"Failed to get access_token from Telegraph response: {resp}")

    set_env_var(env_path, "TELEGRAPH_ACCESS_TOKEN", str(token))
    if args.author_name:
        set_env_var(env_path, "TELEGRAPH_AUTHOR_NAME", args.author_name)
    if args.author_url:
        set_env_var(env_path, "TELEGRAPH_AUTHOR_URL", args.author_url)

    # Do not print the token; print only the management URL.
    print(f"ok\tenv={env_path}")
    if auth_url:
        print(f"auth_url\t{auth_url}")
    return 0


def cmd_publish_chapter(args: argparse.Namespace) -> int:
    env = utils.load_env()
    utils.require_telegraph_token(env)

    con = connect(env.db_path)
    init_db(con)

    pid = _require_project_id(env, getattr(args, "project", None))

    chapter_idx = int(args.chapter)
    row = get_chapter(con, project_id=pid, chapter_idx=chapter_idx)
    if not row:
        raise SystemExit("Chapter not found in DB. Run write-chapter first.")

    title = row.get("chapter_title") or f"第{chapter_idx}章"
    md = row.get("chapter_text") or ""

    nodes = md_to_nodes(md)
    tg = TelegraphClient(access_token=env.telegraph_access_token)

    author_name, author_url = _telegraph_author()

    existing = get_publish(con, project_id=pid, chapter_idx=chapter_idx)
    if existing:
        resp = tg.edit_page(
            path=existing["telegraph_path"],
            title=title,
            nodes=nodes,
            author_name=author_name,
            author_url=author_url,
        )
        path = resp["result"]["path"]
        url = resp["result"]["url"]
    else:
        resp = tg.create_page(title=title, nodes=nodes, author_name=author_name, author_url=author_url)
        path = resp["result"]["path"]
        url = resp["result"]["url"]

    put_publish(con, project_id=pid, chapter_idx=chapter_idx, telegraph_path=path, telegraph_url=url, published_at_utc=now_utc_iso())

    print(url)
    return 0


def cmd_publish_index(args: argparse.Namespace) -> int:
    env = utils.load_env()
    utils.require_telegraph_token(env)

    con = connect(env.db_path)
    init_db(con)

    pid = _require_project_id(env, getattr(args, "project", None))

    proj = get_project(con, project_id=pid)
    book_title = proj.get("topic", {}).get("title") or pid

    pubs = {p["chapter_idx"]: p for p in list_publishes(con, project_id=pid)}
    outline = proj.get("outline") or []

    chapter_links: list[tuple[str, str | None]] = []
    for ch in outline:
        idx = int(ch.get("chapter"))
        ch_title = f"第{idx}章：{ch.get('title', '')}".strip("：")
        url = pubs.get(idx, {}).get("telegraph_url") if pubs.get(idx) else None
        chapter_links.append((ch_title, url))

    intro = (
        (proj.get("story_bible", {}) or {}).get("core_premise")
        or (proj.get("topic", {}) or {}).get("blurb")
        or ""
    )
    nodes = index_nodes(book_title=book_title, intro=intro, chapter_links=chapter_links)

    tg = TelegraphClient(access_token=env.telegraph_access_token)
    author_name, author_url = _telegraph_author()

    existing = pubs.get(0)
    if existing:
        resp = tg.edit_page(
            path=existing["telegraph_path"],
            title=book_title,
            nodes=nodes,
            author_name=author_name,
            author_url=author_url,
        )
        path = resp["result"]["path"]
        url = resp["result"]["url"]
    else:
        resp = tg.create_page(title=book_title, nodes=nodes, author_name=author_name, author_url=author_url)
        path = resp["result"]["path"]
        url = resp["result"]["url"]

    put_publish(con, project_id=pid, chapter_idx=0, telegraph_path=path, telegraph_url=url, published_at_utc=now_utc_iso())
    print(url)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="novel-writer")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="create project and generate plan (bible/characters/relations/outline)")
    sp.add_argument("--title", required=True)
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--topic-file", help="path to a UTF-8 text file containing the TOPIC paragraph")
    g.add_argument("--blurb", help="TOPIC paragraph")
    sp.add_argument("--project-id", help="optional custom project id")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("list-projects", help="list projects")
    sp.set_defaults(func=cmd_list_projects)

    sp = sub.add_parser("set-current", help="set the current project (used when --project is omitted)")
    sp.add_argument("--project", required=True)
    sp.set_defaults(func=cmd_set_current)

    sp = sub.add_parser("current", help="print the current project id")
    sp.set_defaults(func=cmd_current)

    sp = sub.add_parser("status", help="show generation/publish status")
    sp.add_argument("--project", help="project id (optional if current project is set)")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("write-chapter", help="generate a chapter draft and save to DB")
    sp.add_argument("--project", help="project id (optional if current project is set)")
    sp.add_argument("--chapter", type=int, required=True)
    sp.set_defaults(func=cmd_write_chapter)

    sp = sub.add_parser("publish-chapter", help="publish (create/edit) a chapter to Telegraph")
    sp.add_argument("--project", help="project id (optional if current project is set)")
    sp.add_argument("--chapter", type=int, required=True)
    sp.set_defaults(func=cmd_publish_chapter)

    sp = sub.add_parser("publish-index", help="publish/update a book index page linking to chapters")
    sp.add_argument("--project", help="project id (optional if current project is set)")
    sp.set_defaults(func=cmd_publish_index)

    sp = sub.add_parser("telegraph-init", help="create a Telegraph account and write TELEGRAPH_ACCESS_TOKEN into a .env file")
    sp.add_argument("--short-name", required=True, help="Telegraph short_name (required by createAccount)")
    sp.add_argument("--author-name", help="optional author_name")
    sp.add_argument("--author-url", help="optional author_url")
    sp.add_argument("--env-file", default="./.env", help="path to the env file to edit (default: ./.env)")
    sp.add_argument("--force", action="store_true", help="overwrite existing TELEGRAPH_ACCESS_TOKEN without prompting")
    sp.set_defaults(func=cmd_telegraph_init)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
