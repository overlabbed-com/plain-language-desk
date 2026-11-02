"""The standard is data: load a ruleset bundle (rules doc, prompts, goldens, config).

The FAA bundle ships inside the package. RULESET_PATH points the service at a
different bundle — a work-tuned standard is a new bundle, not a fork. Every
response reports the bundle ref (id@version) that scored the text.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

_BUNDLES_DIR = Path(__file__).resolve().parent / "rulesets"
DEFAULT_BUNDLE = "faa-plain-language"
VALID_MODES = ("minimal", "full")


class Ruleset:
    """One loaded bundle: config, the two rewrite prompts, and its identity."""

    def __init__(self, path: Path):
        self.path = path
        cfg_path = path / "ruleset.json"
        if not cfg_path.exists():
            raise FileNotFoundError(f"ruleset bundle has no ruleset.json: {path}")
        cfg = json.loads(cfg_path.read_text())
        self.id = cfg["id"]
        self.version = cfg["version"]
        # BAR env overrides the bundle's bar; the bundle value is the default.
        self.bar = int(os.environ.get("BAR", cfg["bar"]))
        self.scorer = cfg.get("scorer", "WPS/1.1")
        # A bundle may carry its own deterministic scorer with the same CLI
        # contract as the vendored FAA one; without one the FAA scorer applies.
        scorer = path / "scorer.py"
        self.scorer_path = scorer if scorer.exists() else None
        self.full_prompt = (path / "rewrite-prompt-full.txt").read_text()
        self.minimal_prompt = (path / "rewrite-prompt-minimal.txt").read_text()

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def prompt(self, mode: str) -> str:
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
        return self.minimal_prompt if mode == "minimal" else self.full_prompt


def ruleset_path() -> Path:
    override = os.environ.get("RULESET_PATH", "").strip()
    if not override:
        return _BUNDLES_DIR / DEFAULT_BUNDLE
    candidate = Path(override).expanduser()
    # A bare name (no path separator) names a bundle shipped in the package.
    if not candidate.exists() and "/" not in override and "\\" not in override:
        shipped = _BUNDLES_DIR / override
        if shipped.is_dir():
            return shipped
    return candidate.resolve()


@lru_cache(maxsize=8)
def _load(path_str: str) -> Ruleset:
    return Ruleset(Path(path_str))


def current() -> Ruleset:
    """Load the active bundle (RULESET_PATH or the shipped FAA default)."""
    return _load(str(ruleset_path()))
