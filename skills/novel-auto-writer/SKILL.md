---
name: novel-auto-writer
description: Automate Chinese novel creation with background research + multi-chapter drafting and Telegraph publishing, using the local `projects/novel-writer-cli` pipeline. Use when the user gives a story idea and wants you to (1) research and enrich background, then create a new novel project (topic/bible/characters/relations/8-chapter outline), (2) generate a specific chapter and publish/update it on Telegraph and return the URL, or (3) do basic novel operations like listing projects, switching the current project, checking status, and publishing the index page.
---

# Novel Auto Writer (OpenClaw Skill)

This skill is a thin operational wrapper + workflow guide around the local CLI project:

- Code: `projects/novel-writer-cli/`
- CLI entrypoint: `python3 -m novel_writer ...`
- Outputs: `projects/novel-writer-cli/outputs/<project_id>/...`
- DB: `projects/novel-writer-cli/data/novels.db`
- Env (models/keys/token): `projects/novel-writer-cli/.env` (gitignored)

Use the wrapper script so the CLI always runs with the right env:

```bash
bash skills/novel-auto-writer/scripts/novel.sh --help
```

## Example User Requests (to trigger this skill)

- "我有个点子：... 你帮我上网补充背景，然后开一个新小说项目。"
- "把当前项目写到第 3 章并发布到 telegraph，给我链接。"
- "列出我有哪些小说 / 切换到 vibe-10y / 看状态。"
- "重新生成第一章并覆盖发布。"

## Workflows

### 1) Creative ideation (idea -> web research -> project init)

Goal: user gives a seed idea; you browse to enrich background; then run `init` and present the plan summary.

Do:

1) Confirm minimum inputs (keep it light):
   - One-sentence seed idea (user provides)
   - Desired genre/tone (if not provided, pick one and state it)
   - Any taboos (optional)

2) Web research (fast, practical):
   - Use the browser tool to search 3-6 credible sources for:
     - setting realism (city/industry/culture/time-specific details)
     - technology constraints (e.g., 2015 tooling, mobile, startup climate)
     - any domain-specific hook (security, financing, office life, etc.)
   - Capture 5-10 concrete details you can actually write scenes around.
   - Keep citations as raw URLs in your notes/response.

3) Turn research into an enriched TOPIC blurb:
   - 1 paragraph, 200-500 Chinese characters.
   - Include: time/place, protagonist situation, core conflict, and 2-3 signature props/details.

4) Create the project:

```bash
bash skills/novel-auto-writer/scripts/novel.sh init \
  --title "<title>" \
  --blurb "<enriched blurb>" \
  --project-id "<optional_project_id>"

# set as current for follow-up actions
bash skills/novel-auto-writer/scripts/novel.sh set-current --project <project_id>
```

5) Show the plan summary (topic/bible/characters/outline):

```bash
python3 skills/novel-auto-writer/scripts/plan_summary.py --project <project_id>
```

What to return to the user:
- `project_id`
- 3-6 bullets: core premise + main conflict + 2 key mysteries/objects
- a short character roster (3-6 main roles)
- chapter 1-2 loglines
- your research citations (URLs)

### 2) Write + publish (chapter N -> Telegraph URL)

Prereq: Telegraph token is set in `projects/novel-writer-cli/.env` (`TELEGRAPH_ACCESS_TOKEN=...`). If missing, generate it once:

```bash
bash skills/novel-auto-writer/scripts/novel.sh telegraph-init --short-name <short> --env-file projects/novel-writer-cli/.env
```

Goal: user says "write chapter 3" (or "write and publish chapter 3").

Generate chapter:

```bash
bash skills/novel-auto-writer/scripts/novel.sh write-chapter --chapter 3
```

Publish/update to Telegraph:

```bash
bash skills/novel-auto-writer/scripts/novel.sh publish-chapter --chapter 3
```

Optional: update the book index page (TOC):

```bash
bash skills/novel-auto-writer/scripts/novel.sh publish-index
```

What to return to the user:
- Telegraph URL printed by `publish-chapter`
- Optionally the index URL (if you updated it)

### 3) Basic operations (list/switch/status)

List projects:

```bash
bash skills/novel-auto-writer/scripts/novel.sh list-projects
```

Switch current project:

```bash
bash skills/novel-auto-writer/scripts/novel.sh set-current --project <project_id>
```

Show current project:

```bash
bash skills/novel-auto-writer/scripts/novel.sh current
```

Show status (chapters generated/published):

```bash
bash skills/novel-auto-writer/scripts/novel.sh status
```

## Notes / Guardrails

- Do not print or log `TELEGRAPH_ACCESS_TOKEN`.
- If the user asks to "re-generate chapter 1": just rerun `write-chapter --chapter 1` then `publish-chapter --chapter 1`.
- If a step fails, check raw artifacts:
  - scene plan retries: `outputs/<project>/chapters/<idx>/scene_plan_attempt_*_raw.txt`
  - per-scene text: `outputs/<project>/chapters/<idx>/scene_*.txt`
  - summary retries: `outputs/<project>/chapters/<idx>/summary_*_attempt_*_raw.txt`
