from pathlib import Path

import pytest

from plain_language_desk.scorer import band, score_text

GOLDEN_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "plain_language_desk"
    / "rulesets"
    / "faa-plain-language"
    / "golden"
)


def test_band_mapping_covers_every_band():
    assert band(95) == "green"
    assert band(90) == "green"
    assert band(85) == "pass"
    assert band(80) == "pass"
    assert band(70) == "concerns"
    assert band(50) == "fail"
    assert band(None) == "exempt"


async def test_score_text_on_clean_fixture_is_green():
    report = await score_text((GOLDEN_DIR / "clean.md").read_text())
    assert report["score"] == 95
    assert report["band"] == "green"


async def test_score_text_on_bad_fixture_fails_with_findings():
    report = await score_text((GOLDEN_DIR / "bad.md").read_text())
    assert report["score"] == 29
    assert report["band"] == "fail"
    assert len(report["findings"]) >= 10


async def test_score_report_shape():
    text = "Short active sentence. You can read it in one pass."
    report = await score_text(text)
    assert set(report) == {"path", "score", "band", "words", "avg_sentence_words", "findings", "version"}
    assert report["version"] == "WPS/1.1"


async def test_score_text_skips_code_and_frontmatter():
    """The segmentation promise: fenced code and front matter never cost points."""
    base = "Short active sentence. You can read it in one pass."
    fenced = f"---\ntitle: x\ndraft: true\n---\n{base}\n\n```python\ndef total_serenity_nightmares():\n    return 'it shall be noted that the utilization of the aforementioned provisions is required to be initiated prior to the commencement of the verification undertaking by the addressees without exception'\n```\n"
    base_report = await score_text(base)
    fenced_report = await score_text(fenced)
    # The temp-file path differs by construction; the score content must not.
    base_report.pop("path")
    fenced_report.pop("path")
    assert fenced_report == base_report


async def test_score_text_rejects_empty():
    with pytest.raises(ValueError):
        await score_text("   ")


async def test_score_text_rejects_oversize():
    with pytest.raises(ValueError):
        await score_text("x" * 200_001)
