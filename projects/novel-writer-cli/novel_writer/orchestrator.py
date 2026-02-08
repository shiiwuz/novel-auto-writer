from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .db import get_chapter, get_project
from .llm import OpenAICompatClient
from .prompts import (
    SYSTEM_ARCHITECT,
    SYSTEM_SCENE_PLANNER,
    SYSTEM_SCENE_WRITER,
    SYSTEM_SUMMARIZER,
    user_prompt_for_architect,
    user_prompt_for_scene_plan,
    user_prompt_for_scene_write,
    user_prompt_for_summary,
)
from .utils import Env, extract_first_json_object, now_utc_iso, write_json, write_text


def generate_project_plan(
    *,
    env: Env,
    client: OpenAICompatClient,
    project_id: str,
    title: str,
    blurb: str,
) -> dict[str, Any]:
    user = user_prompt_for_architect(title=title, blurb=blurb)
    resp = client.chat_completions(model=env.novel_outline_model, system=SYSTEM_ARCHITECT, user=user, temperature=0.2)
    text = client.get_text(resp)
    obj = extract_first_json_object(text)

    # Basic sanity checks.
    if not isinstance(obj, dict):
        raise RuntimeError("Architect output is not a JSON object")
    if "outline" not in obj or not isinstance(obj.get("outline"), list) or len(obj.get("outline")) != 8:
        raise RuntimeError("Architect output must contain outline with exactly 8 chapters")

    out_dir = env.outputs_dir / project_id
    write_json(out_dir / "project_plan.json", obj)
    return obj


def generate_chapter(
    *,
    env: Env,
    client: OpenAICompatClient,
    project_id: str,
    project_obj: dict[str, Any],
    chapter_idx: int,
    prev_chapter_summary: str,
    prev_last_paragraph: str,
) -> dict[str, Any]:
    outline = project_obj.get("outline") or []
    chapter_meta = None
    for ch in outline:
        if int(ch.get("chapter")) == int(chapter_idx):
            chapter_meta = ch
            break
    if not chapter_meta:
        raise RuntimeError(f"Chapter {chapter_idx} not found in outline")

    outline_short = [
        {"chapter": o.get("chapter"), "title": o.get("title"), "logline": o.get("logline")} for o in outline
    ]

    out_dir = env.outputs_dir / project_id / "chapters" / f"{int(chapter_idx):03d}"

    # 1) Plan scenes (structured JSON) using the outline model.
    plan_user = user_prompt_for_scene_plan(
        project=project_obj,
        chapter=chapter_meta,
        outline_short=outline_short,
        prev_chapter_summary=prev_chapter_summary,
    )
    # Scene plan can still be long; retry on truncation.
    plan_obj: dict[str, Any] | None = None
    plan_attempts = [
        {"temperature": 0.2, "max_tokens": 3500},
        {"temperature": 0.2, "max_tokens": 4200},
    ]
    last_plan_err: Exception | None = None
    for attempt_i, a in enumerate(plan_attempts, start=1):
        plan_resp = client.chat_completions(
            model=env.novel_outline_model,
            system=SYSTEM_SCENE_PLANNER,
            user=plan_user,
            temperature=float(a["temperature"]),
            max_tokens=int(a["max_tokens"]),
            extra={"max_completion_tokens": int(a["max_tokens"])},
        )
        plan_text = client.get_text(plan_resp)
        try:
            parsed = extract_first_json_object(plan_text)
            if not isinstance(parsed, dict):
                raise ValueError("Scene plan output is not a JSON object")
            sc = parsed.get("scenes")
            if not isinstance(sc, list) or len(sc) != 12:
                raise ValueError("Scene plan must contain scenes with length == 12")
            plan_obj = parsed
            last_plan_err = None
            break
        except Exception as e:
            last_plan_err = e
            write_text(out_dir / f"scene_plan_attempt_{attempt_i}_raw.txt", plan_text)
            continue

    if plan_obj is None:
        raise RuntimeError(f"Scene plan parse failed after retries: {last_plan_err}")

    scenes = plan_obj.get("scenes") or []
    write_json(out_dir / "scene_plan.json", plan_obj)

    # 2) Write each scene as plain text via the writer model, then concatenate.
    scene_texts: list[str] = []
    prev_tail = prev_last_paragraph

    for i, scene in enumerate(scenes, start=1):
        scene_user = user_prompt_for_scene_write(
            project=project_obj,
            chapter=chapter_meta,
            scene=scene,
            prev_tail=prev_tail,
        )
        # Let the model have enough budget to avoid truncation; prompt still enforces tight output.
        resp = client.chat_completions(
            model=env.novel_writer_model,
            system=SYSTEM_SCENE_WRITER,
            user=scene_user,
            temperature=0.6,
            max_tokens=5000,
            extra={"max_completion_tokens": 5000},
        )
        scene_text = client.get_text(resp).strip()

        # Keep output tight even if the model rambles.
        scene_text = "\n\n".join([p.strip() for p in scene_text.split("\n\n") if p.strip()][:2]).strip()

        # Persist raw scene output for debugging/repro.
        write_text(out_dir / f"scene_{i:02d}.txt", scene_text + "\n")

        # Update tail for continuity (short tail; for reference only).
        prev_tail = scene_text[-220:] if len(scene_text) > 220 else scene_text
        scene_texts.append(scene_text)

    chapter_text = "\n\n".join([t for t in scene_texts if t]).strip() + "\n"

    # Persist chapter text even if summarization fails.
    write_text(out_dir / "chapter.md", chapter_text)

    # 3) Summarize (structured JSON). Retry and fall back to writer model if needed.
    sum_user = user_prompt_for_summary(chapter_text=chapter_text)

    def summarize_with(model: str) -> dict[str, Any] | None:
        attempts = [
            {"temperature": 0.2, "max_tokens": 900},
            {"temperature": 0.2, "max_tokens": 1200},
        ]
        last_err: Exception | None = None
        for attempt_i, a in enumerate(attempts, start=1):
            resp = client.chat_completions(
                model=model,
                system=SYSTEM_SUMMARIZER,
                user=sum_user,
                temperature=float(a["temperature"]),
                max_tokens=int(a["max_tokens"]),
                extra={"max_completion_tokens": int(a["max_tokens"])},
            )
            text = client.get_text(resp)
            try:
                parsed = extract_first_json_object(text)
                if not isinstance(parsed, dict):
                    raise ValueError("Summary output is not a JSON object")
                return parsed
            except Exception as e:
                last_err = e
                write_text(out_dir / f"summary_{model}_attempt_{attempt_i}_raw.txt", text)
                continue
        return None

    sum_obj = summarize_with(env.novel_outline_model)
    if sum_obj is None:
        sum_obj = summarize_with(env.novel_writer_model)

    if sum_obj is None:
        # Final fallback: keep the pipeline moving.
        sum_obj = {
            "chapter_summary": "",
            "continuity_notes": [],
            "next_chapter_hook": "",
        }

    result: dict[str, Any] = {
        "chapter": int(chapter_idx),
        "title": str(plan_obj.get("title") or chapter_meta.get("title") or f"第{chapter_idx}章"),
        "scene_plan": plan_obj,
        "chapter_text": chapter_text,
        "chapter_summary": str(sum_obj.get("chapter_summary") or ""),
        "continuity_notes": sum_obj.get("continuity_notes") or [],
        "next_chapter_hook": str(sum_obj.get("next_chapter_hook") or ""),
    }

    write_json(out_dir / "chapter.json", result)

    return result


def get_prev_context_from_db(con, *, project_id: str, chapter_idx: int) -> tuple[str, str]:
    if chapter_idx <= 1:
        return "", ""
    prev = get_chapter(con, project_id=project_id, chapter_idx=chapter_idx - 1)
    if not prev:
        return "", ""

    summary = (prev.get("chapter_summary") or "").strip()
    text = (prev.get("chapter_text") or "").strip()

    # last paragraph: take tail chunk, then split by blank lines.
    tail = text[-1500:] if len(text) > 1500 else text
    parts = [p.strip() for p in tail.split("\n\n") if p.strip()]
    last_para = parts[-1] if parts else tail
    return summary, last_para
