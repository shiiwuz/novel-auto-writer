# novel-auto-writer (OpenClaw skill + local CLI)

This repository contains:

- `projects/novel-writer-cli/`: a minimal, reproducible CLI tool (Python stdlib only) that generates an 8-chapter Chinese novel from a topic, and publishes chapters to Telegraph.
- `skills/novel-auto-writer/`: an OpenClaw skill that documents the workflow and provides a wrapper script to run the CLI with the correct `.env`.

## Quickstart

1) Prepare env

- Copy `projects/novel-writer-cli/.env.example` to `projects/novel-writer-cli/.env`
- Fill:
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - (optional) `NOVEL_OUTLINE_MODEL`, `NOVEL_WRITER_MODEL`

2) Generate Telegraph token (once)

```bash
bash skills/novel-auto-writer/scripts/novel.sh telegraph-init --short-name <short> --env-file projects/novel-writer-cli/.env
```

3) Create a project

```bash
bash skills/novel-auto-writer/scripts/novel.sh init \
  --title "Your Title" \
  --blurb "Your topic paragraph"
```

4) Set current project (optional but convenient)

```bash
bash skills/novel-auto-writer/scripts/novel.sh set-current --project <project_id>
```

5) Write + publish chapter

```bash
bash skills/novel-auto-writer/scripts/novel.sh write-chapter --chapter 1
bash skills/novel-auto-writer/scripts/novel.sh publish-chapter --chapter 1
```

The `publish-chapter` command prints the Telegraph URL.
