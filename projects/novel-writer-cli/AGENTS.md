# AGENTS.md - novel-writer-cli

This repo is a CLI-only, reproducible pipeline to generate a Chinese novel from a TOPIC (title + paragraph) using an OpenAI-compatible LLM API, then publish chapters to Telegraph.

## Product Contract

- Input: `TOPIC = 标题 + 一段话`.
- Output artifacts (must be saved under `outputs/<project_id>/`):
  - `project_plan.json`: `topic` + `style_guide` + `story_bible` + `characters` + `relations` + `outline` + `continuity_rules`.
  - `chapters/00X/chapter.json`: structured chapter output.
  - `chapters/00X/chapter.md`: final chapter text.
- Fixed chapter count: **8**.
- Language: **Chinese** for all prompts and generated content.
- No scheduler. Only CLI commands.
- No second-pass editor. Writer must produce the final chapter in one run.

## Technical Architecture

**Core modules**

- `novel_writer/llm.py`: OpenAI-compatible client (`POST /v1/chat/completions`).
  - Must send browser-ish `User-Agent`.
  - Must support timeouts and readable error surfacing.
- `novel_writer/prompts.py`: all system prompts and prompt builders (Chinese-only).
  - `SYSTEM_ARCHITECT`: planning stage.
  - `SYSTEM_WRITER`: chapter writing stage.
- `novel_writer/orchestrator.py`: pipeline glue.
  - `init` (architect) -> `project_plan.json`.
  - `write-chapter` (writer) -> chapter artifacts.
  - Must feed context each generation: story bible + topic + outline + chapter requirements + prev summary + prev tail paragraph.
- `novel_writer/db.py`: SQLite persistence for resumability.
  - Tracks projects, chapter drafts, publish URLs.
- `novel_writer/telegraph.py`: Telegraph publishing.
  - Uses `TELEGRAPH_ACCESS_TOKEN`.
  - Creates/edits per-chapter pages; creates/edits a book index page.

**Persistence & Idempotency**

- DB path: `NOVEL_DB_PATH` (default `./data/novels.db`).
- Publishing is idempotent:
  - If a chapter already has a `telegraph_path`, use `editPage`.
  - Else use `createPage`.
  - Index page is stored as `chapter_idx = 0` in the `publishes` table.

## LLM Model Policy

- Outline/planning model (default): `gemini-3-pro-preview` (`NOVEL_OUTLINE_MODEL`).
- Chapter writer model (default): `gemini-3-flash-preview` (`NOVEL_WRITER_MODEL`).
- API is **OpenAI-compatible** and uses:
  - `OPENAI_BASE_URL` (fallback to `EMBEDDINGS_BASE_URL`)
  - `OPENAI_API_KEY` (fallback to `EMBEDDINGS_API_KEY`)

## Prompt & Output Contracts (Hard Requirements)

### Architect stage (`SYSTEM_ARCHITECT`)

- Must output **ONLY** a single JSON object, strictly parseable.
- Must include:
  - `story_bible` (world rules, timeline, mysteries, key objects)
  - `characters` (structured character cards)
  - `relations.edges` (relationship graph)
  - `outline` length must be **exactly 8**; each chapter includes `title` + `logline` + `chapter_goal` + `reversal` + `cliffhanger` + `must_reveal`.

### Writer stage

- Writer outputs **only plain Chinese story content** (no JSON, no markdown, no headings).
- Writing is done per-scene (multiple LLM calls) and concatenated into `chapter_text`.
- Must not contain any self-referential assistant language.

### Scene planner stage (`SYSTEM_SCENE_PLANNER`)

- Must output **ONLY** a single JSON object, strictly parseable.
- Must include `scenes` with length **>= 12**.

### JSON parsing

- The code uses a best-effort JSON extractor (`extract_first_json_object`).
- Prompts must still demand strict JSON-only output to reduce extraction failures.

## CLI UX (Commands)

- `init --title ... (--topic-file ... | --blurb ...) [--project-id ...]`
  - Generates the project plan using the architect model.
- `write-chapter --project <id> --chapter 1..8`
  - Generates chapter draft and saves to DB + outputs.
- `publish-chapter --project <id> --chapter 1..8`
  - Publishes/updates chapter page to Telegraph.
- `publish-index --project <id>`
  - Publishes/updates index page linking all chapters.
- `telegraph-init --short-name ... [--env-file ./.env] [--force]`
  - Creates a Telegraph account and writes `TELEGRAPH_ACCESS_TOKEN` into the env file.
- `status --project <id>`
  - Shows chapter generated/published state.

## Telegraph Policy

- Use **only** `TELEGRAPH_ACCESS_TOKEN` for authentication.
- Optional author metadata:
  - `TELEGRAPH_AUTHOR_NAME`
  - `TELEGRAPH_AUTHOR_URL`
- Markdown conversion is intentionally minimal and predictable (no complex formatting).

## Coding Standards / Constraints

- Prefer Python stdlib only (no heavy deps). Keep the container lightweight.
- Keep prompts, schemas, and generation contracts in code for reproducibility.
- Keep secrets out of git:
  - Project `.gitignore` includes `.env`, `/data/`, `/outputs/`.
- ASCII-only code/comments unless existing file already uses Unicode (prompts are Chinese by design).
- Fail fast with actionable errors when required env vars are missing.

## Testing / Smoke Checks

Minimal smoke checks expected to work:

- `python3 -m novel_writer --help`
- `python3 -m novel_writer init ...`
- `python3 -m novel_writer write-chapter --project ... --chapter 1`
- `python3 -m novel_writer publish-chapter ...` (requires valid Telegraph token)
- `python3 -m novel_writer publish-index ...` (requires valid Telegraph token)
