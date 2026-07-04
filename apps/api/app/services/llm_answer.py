"""Optional LLM synthesis for memory answers, grounded in retrieved rows only.

This layer is intentionally best-effort and never blocks deterministic answers:
if Groq is disabled, misconfigured, or errors, callers should fall back to the
engine's deterministic phrasing.
"""

from __future__ import annotations

import json
from urllib import error, request

from app.core.config import settings
from app.schemas.memory import MemoryResult

_GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


def _rows_to_context(rows: list[MemoryResult]) -> str:
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        lines.append(
            (
                f"{idx}. note_id={row.note_id}; recorded_at={row.recorded_at}; "
                f"verification={row.verification_status}; fact={row.fact}"
            )
        )
    return "\n".join(lines)


def synthesize_answer_with_groq(query: str, rows: list[MemoryResult]) -> str | None:
    """Return a Groq-grounded answer, or None when unavailable/unusable."""
    if not settings.MEMORY_USE_GROQ_SYNTHESIS:
        return None
    if not settings.GROQ_API_KEY.strip() or not rows:
        return None

    prompt = (
        "You are a memory assistant for a patient-facing app. "
        "Answer ONLY using the provided memory rows. "
        "Do not invent facts. Keep tone calm and short. "
        "If evidence is weak, say that clearly. "
        "Mention caregiver confirmation status in plain language.\n\n"
        f"Question: {query}\n\n"
        "Retrieved memory rows:\n"
        f"{_rows_to_context(rows)}\n\n"
        "Return only the final answer sentence(s), no JSON."
    )

    payload = {
        "model": settings.GROQ_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Grounded memory QA assistant."},
            {"role": "user", "content": prompt},
        ],
    }

    req = request.Request(
        _GROQ_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
    except (error.URLError, TimeoutError, ValueError):
        return None

    try:
        body = json.loads(raw)
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None

    answer = (content or "").strip()
    return answer or None
