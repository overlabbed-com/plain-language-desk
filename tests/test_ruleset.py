"""The ruleset bundle: identity, overrides, and prompt selection."""

import json
from pathlib import Path

import pytest

from plain_language_desk.ruleset import Ruleset, current, ruleset_path

BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "plain_language_desk"
    / "rulesets"
    / "faa-plain-language"
)


def test_default_bundle_loads_with_expected_identity():
    rs = current()
    assert rs.id == "faa-plain-language"
    assert rs.version == "1.0.0"
    assert rs.ref == "faa-plain-language@1.0.0"
    assert rs.bar == 80
    assert rs.scorer == "WPS/1.1"


def test_bundle_carries_the_standard_and_goldens():
    assert (BUNDLE / "RULESET.md").exists()
    ruleset_text = (BUNDLE / "RULESET.md").read_text().lower()
    assert "faa order 1000.36a" in ruleset_text
    assert "ws-04" in ruleset_text and "shall" in ruleset_text
    assert "the bar is 80" in ruleset_text
    for name in ("clean.md", "mid.md", "bad.md"):
        assert (BUNDLE / "golden" / name).exists()


def test_bar_env_overrides_the_bundle(monkeypatch):
    monkeypatch.setenv("BAR", "90")
    rs = Ruleset(BUNDLE)
    assert rs.bar == 90


def test_ruleset_path_env_points_at_another_bundle(monkeypatch, tmp_path):
    alt = tmp_path / "work-plain-language"
    alt.mkdir()
    cfg = json.loads((BUNDLE / "ruleset.json").read_text())
    cfg["id"] = "work-plain-language"
    cfg["version"] = "0.1.0"
    (alt / "ruleset.json").write_text(json.dumps(cfg))
    for name in ("rewrite-prompt-full.txt", "rewrite-prompt-minimal.txt"):
        (alt / name).write_text((BUNDLE / name).read_text())

    monkeypatch.setenv("RULESET_PATH", str(alt))
    rs = current()
    assert rs.id == "work-plain-language"
    assert rs.ref == "work-plain-language@0.1.0"


def test_missing_bundle_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("RULESET_PATH", str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError):
        current()
