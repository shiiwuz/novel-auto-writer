FROM python:3.12-slim

WORKDIR /app

# No third-party deps; stdlib only.
COPY novel_writer/ /app/novel_writer/

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "novel_writer"]
