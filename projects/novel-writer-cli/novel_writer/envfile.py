from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class EnvEditResult:
    path: Path
    changed: bool
    message: str


def _parse_env_value(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "=" not in s:
        return None
    k, v = s.split("=", 1)
    return k.strip(), v.strip()


def get_env_var(path: Path, key: str) -> Optional[str]:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        kv = _parse_env_value(line)
        if not kv:
            continue
        k, v = kv
        if k == key:
            return v
    return None


def set_env_var(path: Path, key: str, value: str) -> EnvEditResult:
    """Set or replace a KEY=VALUE line.

    Preserves other lines and comments. Does not quote/escape.
    """
    lines: list[str]
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []

    changed = False
    found = False
    new_lines: list[str] = []
    for line in lines:
        kv = _parse_env_value(line)
        if kv and kv[0] == key:
            found = True
            new_line = f"{key}={value}"
            if line != new_line:
                changed = True
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if not found:
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.append(f"{key}={value}")
        changed = True

    if changed:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return EnvEditResult(path=path, changed=changed, message=("updated" if changed else "no change"))
