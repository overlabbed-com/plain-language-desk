"""Thin wrapper around the vendored writing-standard scorer.

The scorer is a deterministic stdlib-only script. We shell out to it with
--json rather than importing it, so the CLI contract stays the only coupling:
a scorer version bump is caught by the parity test, not by an import break.

The scorer's strip_machine() already removes front matter, fenced code, inline
code, comments, tables, and links before scoring — the markdown-aware
segmentation the API promises is the scorer's own behavior.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

VENDOR_SCORER = Path(__file__).parent / "vendor" / "dsh-writing-score.py"
EXPECTED_VERSION = "WPS/1.1"
SCORER_TIMEOUT = float(os.environ.get("SCORER_TIMEOUT", "60"))
MAX_TEXT_CHARS = 200_000


def band(score: int | None) -> str:
    if score is None:
        return "exempt"
    if score >= 90:
        return "green"
    if score >= 80:
        return "pass"
    if score >= 65:
        return "concerns"
    return "fail"


async def score_text(text: str) -> dict[str, Any]:
    """Score one document and return the report the API exposes."""
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds the {MAX_TEXT_CHARS} character cap")

    fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
    try:
        fh.write(text)
        fh.close()
        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(VENDOR_SCORER),
            "--file",
            fh.name,
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=SCORER_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("scorer timed out")
        if proc.returncode != 0:
            raise RuntimeError(f"scorer failed rc={proc.returncode}: {err.decode()[:300]}")
        parsed = json.loads(out)
        files = parsed.get("files") or []
        if not files:
            raise RuntimeError("scorer returned no report")
        f = files[0]
        return {
            "path": f["file"],
            "score": f["score"],
            "band": band(f["score"]),
            "words": f["doc_words"],
            "avg_sentence_words": f["avg_sentence_words"],
            "findings": f["findings"],
            "version": f["version"],
        }
    finally:
        try:
            os.unlink(fh.name)
        except OSError:
            pass
