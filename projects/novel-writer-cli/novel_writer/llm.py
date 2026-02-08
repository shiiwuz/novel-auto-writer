from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional


class OpenAICompatClient:
    def __init__(self, *, base_url: str, api_key: str, timeout_s: int = 120) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s

    def chat_completions(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = self._base_url + "/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        # Some gateways reject setting both max_tokens and max_completion_tokens.
        if extra and "max_completion_tokens" in extra:
            if max_tokens is not None:
                payload["max_completion_tokens"] = int(extra["max_completion_tokens"])
            # Do not set max_tokens when max_completion_tokens is present.
            extra = {k: v for k, v in extra.items() if k != "max_completion_tokens"}
        else:
            if max_tokens is not None:
                payload["max_tokens"] = int(max_tokens)

        if extra:
            payload.update(extra)

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            # Some deployments/WAFs reject default Python UA.
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                resp_body = resp.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTPError {e.code}: {msg}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"LLM URLError: {e}")

        obj = json.loads(resp_body)
        return obj

    @staticmethod
    def get_text(obj: dict[str, Any]) -> str:
        try:
            return str(obj["choices"][0]["message"]["content"])
        except Exception:
            return json.dumps(obj, ensure_ascii=False)
