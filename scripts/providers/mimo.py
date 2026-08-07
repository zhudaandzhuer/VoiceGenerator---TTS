"""Reusable standard-library adapter for Xiaomi MiMo chat-completions TTS."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"


class MimoRequestError(RuntimeError):
    """A sanitized MiMo transport or response error."""


def request_audio(
    *, api_key: str, base_url: str, model: str, context: str, text: str,
    audio_format: str, timeout: float, retries: int, voice: str | None = None,
) -> bytes:
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": context},
            {"role": "assistant", "content": text},
        ],
        "audio": {"format": audio_format},
    }
    if voice:
        payload["audio"]["voice"] = voice
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = f"{base_url.rstrip('/')}/chat/completions"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            audio_data = result["choices"][0]["message"]["audio"]["data"]
            decoded = base64.b64decode(audio_data, validate=True)
            if not decoded:
                raise ValueError("MiMo returned empty audio data")
            return decoded
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise MimoRequestError(f"MiMo HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= retries:
                raise MimoRequestError(
                    f"MiMo request failed after {attempt + 1} attempts: {exc}"
                ) from exc
            time.sleep(2**attempt)
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise MimoRequestError(f"Unexpected MiMo response: {exc}") from exc
    raise AssertionError("unreachable")
