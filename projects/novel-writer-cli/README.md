# novel-writer-cli

A minimal, reproducible CLI tool (Python stdlib only) to generate a Chinese novel from a TOPIC (title + paragraph) using an OpenAI-compatible LLM API, then publish chapters to Telegraph.

## Features

- Chinese-only prompts (system + user prompts are defined in code).
- Fixed 8 chapters outline.
- Two-stage generation:
  - Outline stage (world bible / character cards / relations / 8-chapter outline) via `gemini-3-pro-preview`.
  - Chapter stage:
    - Scene planning (structured JSON) via `gemini-3-pro-preview`.
    - Scene writing (plain text only, per scene, concatenated) via `gemini-3-flash-preview`.
- No scheduler; CLI-only.
- SQLite state for resumability + `outputs/` artifacts for human inspection.
- Telegraph publishing:
  - Publish each chapter as a Telegraph page.
  - Publish/update a book index page linking to chapters.

## OpenClaw Skill

If you are running this inside the OpenClaw workspace, you can drive the CLI via the skill package:

- Skill usage doc: `skills/novel-auto-writer/SKILL.md`
- Wrapper (auto-loads `projects/novel-writer-cli/.env`):

```bash
bash skills/novel-auto-writer/scripts/novel.sh --help
bash skills/novel-auto-writer/scripts/novel.sh list-projects
bash skills/novel-auto-writer/scripts/novel.sh set-current --project <project_id>
bash skills/novel-auto-writer/scripts/novel.sh write-chapter --chapter 1
bash skills/novel-auto-writer/scripts/novel.sh publish-chapter --chapter 1
```

## Environment

Required:

- `OPENAI_BASE_URL` (example: `http://10.20.30.15:3002`)
- `OPENAI_API_KEY`
- `TELEGRAPH_ACCESS_TOKEN` (can be generated via `telegraph-init`)

Optional:

- `NOVEL_OUTLINE_MODEL` (default: `gemini-3-pro-preview`)
- `NOVEL_WRITER_MODEL` (default: `gemini-3-flash-preview`)
- `NOVEL_DB_PATH` (default: `./data/novels.db`)
- `NOVEL_OUTPUTS_DIR` (default: `./outputs`)

## Quickstart (local)

```bash
cd projects/novel-writer-cli
export OPENAI_BASE_URL='http://10.20.30.15:3002'
export OPENAI_API_KEY='...'
export TELEGRAPH_ACCESS_TOKEN='...'

python3 -m novel_writer --help

# create project + generate bible/characters/relations/outline
python3 -m novel_writer init --title 'xxx' --topic-file topic.md

# write chapter 1
python3 -m novel_writer write-chapter --project <project_id> --chapter 1

# (optional) generate Telegraph access token and write into ./.env
python3 -m novel_writer telegraph-init --short-name Unas --env-file ./.env

# publish chapter 1
python3 -m novel_writer publish-chapter --project <project_id> --chapter 1

# publish/update index page
python3 -m novel_writer publish-index --project <project_id>
```

## Docker

```bash
cd projects/novel-writer-cli
cp .env.example .env
# fill .env

docker compose run --rm novel python -m novel_writer --help
```
