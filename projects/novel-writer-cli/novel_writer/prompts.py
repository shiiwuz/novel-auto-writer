from __future__ import annotations

# All prompts are Chinese by user request.
# Keep prompts in code for reproducibility.

SYSTEM_ARCHITECT = """你是一名职业小说策划（总编剧+设定统筹），擅长把一个简短 TOPIC 扩展成可持续连载的长篇小说工程。

硬性规则：
- 写作语言：中文。
- 只输出一个 JSON 对象，不要输出任何多余文本（不要解释、不要 markdown、不要代码块）。
- JSON 必须可被严格解析：双引号、无尾逗号。
- 章节数固定 8 章。
- 要求结构化、可直接给下游写作模型使用。
- 避免空泛套话；给出可落地的细节（时代、地理、组织、技术/超自然规则、关键物件、隐秘设定）。
- contrast_catalog 至少给出 15 条（现代元素 vs 2015 元素），每条要能直接落到具体场景里。

你需要产出的 JSON schema（字段不可缺）：
{
  "topic": {"title": string, "blurb": string, "genre": string, "tone": string, "themes": [string], "target_length": {"chapters": 8, "per_chapter_chars": int}},
  "style_guide": {"narration": string, "pov": string, "tense": string, "taboos": [string], "signature_devices": [string]},

  "vibe_coding_context": {
    "definition": string,
    "workflow": [string],
    "why_it_feels_like_magic_in_2015": [string],
    "hidden_costs": [string],
    "security_and_accountability_risks": [string],
    "chapter_usage_guidance": [string]
  },

  "contrast_catalog": [
    {"id": string, "modern": string, "year2015": string, "scene_payoff": string}
  ],

  "story_bible": {
    "core_premise": string,
    "world": {"era": string, "locations": [string], "society": string, "rules": [string], "tech_or_magic": string},
    "main_conflict": string,
    "mysteries": [string],
    "key_objects": [string],
    "timeline": [string]
  },
  "characters": [
    {"id": string, "name": string, "role": string, "public_face": string, "private_drive": string, "skills": [string], "weakness": string, "secrets": [string], "voice": string, "arc": string}
  ],
  "relations": {
    "edges": [
      {"a": string, "b": string, "type": string, "tension": string, "history": string, "future_pressure": string}
    ],
    "notes": string
  },
  "outline": [
    {"chapter": 1, "title": string, "logline": string, "chapter_goal": string, "reversal": string, "cliffhanger": string, "must_reveal": [string]}
  ],
  "continuity_rules": [string]
}
"""


SYSTEM_SCENE_PLANNER = """你是一名职业小说分镜策划，负责把本章目标拆成可写的场景清单。

硬性规则：
- 写作语言：中文。
- 只输出一个 JSON 对象，不要输出任何多余文本。
- JSON 必须可被严格解析。
- scenes 数量必须 == 12（固定12个，避免输出过长被截断）。
- 每个 scene 必须明确：场景标题、地点/时间、视角、目标、冲突、转折，并标注至少 1 条现代vs2015反差点（用 contrast_id 引用）。
- 控制长度：每个字段尽量短；must_include 最多 2 条；contrast_ids 最多 2 个。
- 节奏：每个 scene 的 turn 必须是可直接切到下一镜头的动作/决定（不要哲理/长独白）。

输出 JSON schema：
{
  "chapter": int,
  "title": string,
  "scenes": [
    {"idx": int, "scene_title": string, "setting": string, "pov": string, "goal": string, "conflict": string, "turn": string, "contrast_ids": [string], "must_include": [string]}
  ]
}
"""


SYSTEM_SCENE_WRITER = """你是一名职业小说作者，风格快节奏、信息密度高。

硬性规则：
- 写作语言：中文。
- 只输出正文内容本身：不要 JSON、不要 markdown、不要标题、不要解释。
- 不要出现“作为AI/模型/助手”等自我指代。
- 禁止复述/回顾上一段或上一场景发生了什么（不要写“他想起/回忆/刚才/此时才意识到…”）。
- 禁止大段环境描写与抒情；环境描写最多 1 句，必须服务动作。
- 本次只写一个场景的正文：
  - 固定 2 个自然段（不要更多）。
  - 每段尽量 160-260 个中文字符，句子短，动词多。
  - 以动作+对话推进，带出反差点与冲突。
  - 末尾必须留一个明确的小钩子（下一场景必须接得上）。

写作目标：紧凑、快、像镜头剪辑。
"""


SYSTEM_SUMMARIZER = """你是一名连载小说编辑，负责给章节写简洁但信息密度高的摘要与下一章钩子。

硬性规则：
- 写作语言：中文。
- 只输出一个 JSON 对象，不要输出任何多余文本。
- JSON 必须可被严格解析。
- 输出必须以 '{' 开头、以 '}' 结尾（中间不要出现代码块/解释）。

输出 JSON schema：
{
  "chapter_summary": string,
  "continuity_notes": [string],
  "next_chapter_hook": string
}
"""


def user_prompt_for_architect(*, title: str, blurb: str) -> str:
    return (
        "请基于以下 TOPIC 进行小说工程化策划（固定 8 章）。\n\n"
        f"TOPIC 标题：{title}\n"
        f"TOPIC 描述：{blurb}\n"
    )


def _project_min(project: dict) -> dict:
    topic = project.get("topic") or {}
    vibe = project.get("vibe_coding_context") or {}
    bible = project.get("story_bible") or {}
    chars = project.get("characters") or []
    rel = project.get("relations") or {}
    contrasts = project.get("contrast_catalog") or []

    topic_min = {
        "title": topic.get("title"),
        "blurb": topic.get("blurb"),
        "genre": topic.get("genre"),
        "tone": topic.get("tone"),
        "themes": topic.get("themes"),
    }

    vibe_min = {
        "definition": vibe.get("definition"),
        "workflow": (vibe.get("workflow") or [])[:5],
        "why_it_feels_like_magic_in_2015": (vibe.get("why_it_feels_like_magic_in_2015") or [])[:6],
        "hidden_costs": (vibe.get("hidden_costs") or [])[:6],
        "security_and_accountability_risks": (vibe.get("security_and_accountability_risks") or [])[:6],
        "chapter_usage_guidance": (vibe.get("chapter_usage_guidance") or [])[:6],
    }

    bible_min = {
        "core_premise": bible.get("core_premise"),
        "world": bible.get("world"),
        "main_conflict": bible.get("main_conflict"),
        "mysteries": (bible.get("mysteries") or [])[:6],
        "key_objects": (bible.get("key_objects") or [])[:8],
    }

    chars_min = [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "role": c.get("role"),
            "public_face": c.get("public_face"),
            "private_drive": c.get("private_drive"),
            "weakness": c.get("weakness"),
            "secrets": (c.get("secrets") or [])[:4],
            "voice": c.get("voice"),
        }
        for c in chars
    ]

    rel_min = {
        "edges": [
            {
                "a": e.get("a"),
                "b": e.get("b"),
                "type": e.get("type"),
                "tension": e.get("tension"),
                "future_pressure": e.get("future_pressure"),
            }
            for e in (rel.get("edges") or [])
        ]
    }

    contrasts_min = contrasts[:15]

    return {
        "topic": topic_min,
        "vibe_coding_context": vibe_min,
        "contrast_catalog": contrasts_min,
        "story_bible": bible_min,
        "characters": chars_min,
        "relations": rel_min,
    }


def user_prompt_for_scene_plan(*, project: dict, chapter: dict, outline_short: list[dict], prev_chapter_summary: str) -> str:
    return (
        "请为本章生成分镜场景清单（scenes==12）。只输出 JSON。\n\n"
        "[project]" + "\n" + json_dumps_compact(_project_min(project)) + "\n\n"
        "[outline_short]" + "\n" + json_dumps_compact(outline_short) + "\n\n"
        "[chapter_requirements]" + "\n" + json_dumps_compact(chapter) + "\n\n"
        "[prev_chapter_summary]" + "\n" + (prev_chapter_summary or "(无)")
    )


def user_prompt_for_scene_write(
    *,
    project: dict,
    chapter: dict,
    scene: dict,
    prev_tail: str,
) -> str:
    return (
        "请写这个场景的正文内容。只输出正文，不要标题/JSON/markdown。\n\n"
        "[project]" + "\n" + json_dumps_compact(_project_min(project)) + "\n\n"
        "[chapter_requirements]" + "\n" + json_dumps_compact(chapter) + "\n\n"
        "[scene_card]" + "\n" + json_dumps_compact(scene) + "\n\n"
        "[continuity_tail_for_reference_only]" + "\n" + (prev_tail or "(无)") + "\n\n"
        "要求：不要复述 continuity_tail；直接从动作/对话开始；紧凑快节奏；末尾留钩子。"
    )


def user_prompt_for_summary(*, chapter_text: str) -> str:
    return (
        "请基于以下章节正文写摘要与下一章钩子。只输出 JSON。\n\n"
        + chapter_text
    )


def json_dumps_compact(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
