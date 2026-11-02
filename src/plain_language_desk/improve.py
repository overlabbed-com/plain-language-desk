"""The improve loop: score, rewrite with the findings as feedback, re-score.

Monotonic by construction: the response carries the best-scoring version seen,
never a worse one. The loop stops as soon as the text clears the bar, when a
rewrite is a no-op, or when a round stops improving — and never exceeds
max_rounds model calls. The engine only rewrites; it never grants the score.
"""

import json
import os
import re
from typing import Any, Protocol

from .scorer import band, score_text

NO_KEY_SENTINELS = ("", "unused", "not-needed")
MAX_FINDINGS_IN_PROMPT = 40

# Reasoning models that fold their thinking into the content field
# (gpt-oss on Bedrock, GLM without the disable-thinking kwarg) would
# otherwise feed their analysis channel to the scorer as prose.
REASONING_TAG_RE = re.compile(
    r"<(?:reasoning|think|thinking|thought)>.*?</(?:reasoning|think|thinking|thought)>\s*",
    re.DOTALL,
)


def strip_reasoning(content: str) -> str:
    return REASONING_TAG_RE.sub("", content)


def build_rewrite_user_prompt(text: str, report: dict, audience: str) -> str:
    findings = report.get("findings") or []
    lines = []
    for f in findings[:MAX_FINDINGS_IN_PROMPT]:
        lines.append(f"- {f['rule']} (-{f['deduction']}) line {f['line']}: {f['evidence']}")
    if len(findings) > MAX_FINDINGS_IN_PROMPT:
        lines.append(f"- ... and {len(findings) - MAX_FINDINGS_IN_PROMPT} more findings")
    findings_block = "\n".join(lines) if lines else "- none reported"
    who = audience.strip() or "the least technical reader who needs this document"
    return (
        f"Audience: {who}\n\n"
        f"Current score: {report.get('score')} ({report.get('band')}). "
        f"Findings to fix:\n{findings_block}\n\n"
        f"Rewrite this document now:\n\n{text}"
    )


def _rule_names(findings: list[dict]) -> list[str]:
    seen: list[str] = []
    for f in findings or []:
        rule = f.get("rule", "")
        if rule and rule not in seen:
            seen.append(rule)
    return seen


class Completer(Protocol):
    async def complete(self, system: str, user: str) -> str: ...


class OpenAICompatClient:
    """OpenAI-compatible chat-completions client — one wire protocol, any engine.

    Point INFERENCE_BASE_URL at the homelab Envoy gateway, a local vLLM or
    Ollama, or a cloud endpoint. INFERENCE_EXTRA_JSON (optional, raw JSON) is
    merged into the request body top-level, for engines that need
    engine-specific kwargs (e.g. the gateway's GLM enable_thinking rule).
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
        max_retries: int = 2,
        extra_body: dict[str, Any] | None = None,
    ):
        if not base_url:
            raise RuntimeError("INFERENCE_BASE_URL is not configured")
        if not model:
            raise RuntimeError("INFERENCE_MODEL is not configured")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_body = extra_body or {}

    @classmethod
    def from_env(cls) -> "OpenAICompatClient":
        extra_raw = os.environ.get("INFERENCE_EXTRA_JSON", "").strip()
        return cls(
            base_url=os.environ.get("INFERENCE_BASE_URL", "").strip(),
            model=os.environ.get("INFERENCE_MODEL", "").strip(),
            api_key=os.environ.get("INFERENCE_API_KEY", ""),
            timeout=float(os.environ.get("INFERENCE_TIMEOUT", "120")),
            max_retries=int(os.environ.get("INFERENCE_MAX_RETRIES", "2")),
            extra_body=json.loads(extra_raw) if extra_raw else {},
        )

    async def complete(self, system: str, user: str) -> str:
        import httpx

        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        body.update(self.extra_body)
        headers = {}
        if self.api_key.strip() not in NO_KEY_SENTINELS:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Exception | None = None
        for attempt in range(1 + self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as hc:
                    resp = await hc.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    choices = data.get("choices") or []
                    if not choices:
                        raise RuntimeError("model returned no choices")
                    content = (choices[0].get("message") or {}).get("content") or ""
                    content = strip_reasoning(content)
                    if not content.strip():
                        raise RuntimeError("model returned empty content")
                    return content
            except (httpx.HTTPError, RuntimeError) as exc:
                last_error = exc
        raise RuntimeError(f"model call failed after retries: {last_error}")


async def improve_text(
    text: str,
    audience: str,
    max_rounds: int,
    mode: str,
    client: Completer,
    system_prompt: str,
    bar: int,
    ruleset_ref: str,
) -> dict[str, Any]:
    original = await score_text(text)
    best_score = original["score"]
    best_text = text
    best_report = original
    findings_applied: list[str] = []
    rounds = 0

    while (best_score is None or best_score < bar) and rounds < max_rounds:
        rounds += 1
        rewritten = await client.complete(
            system_prompt,
            build_rewrite_user_prompt(best_text, best_report, audience),
        )
        rewritten = rewritten.strip()
        if not rewritten or rewritten == best_text.strip():
            break
        report = await score_text(rewritten)
        if report["score"] is not None and (best_score is None or report["score"] > best_score):
            findings_applied = _rule_names(best_report["findings"])
            best_score = report["score"]
            best_text = rewritten
            best_report = report

    return {
        "original_score": original["score"],
        "final_score": best_score,
        "band": band(best_score),
        "text": best_text,
        "rounds": rounds,
        "findings_applied": findings_applied,
        "findings_remaining": best_report["findings"],
        "bar": bar,
        "ruleset": ruleset_ref,
        "mode": mode,
        "scorer_version": original["version"],
    }
