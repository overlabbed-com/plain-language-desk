"""The improve loop against scripted fake models — no network, deterministic."""

import pytest

from plain_language_desk.improve import improve_text
from plain_language_desk.ruleset import current as current_ruleset
from plain_language_desk.scorer import score_text

RS = current_ruleset()
BAR = RS.bar


class FakeCompleter:
    """Returns scripted rewrites in order; records the prompts it received."""

    def __init__(self, rewrites):
        self.rewrites = list(rewrites)
        self.prompts = []

    async def complete(self, system, user):
        self.prompts.append((system, user))
        return self.rewrites.pop(0)


async def _improve(text, rewrites, max_rounds=3, mode="full", audience=""):
    client = FakeCompleter(rewrites)
    result = await improve_text(
        text, audience, max_rounds, mode, client, RS.prompt(mode), RS.bar, RS.ref
    )
    return result, client


BAD = (
    "It shall be noted that the utilization of the aforementioned system is required "
    "to be initiated prior to the commencement of the undertaking of the verification "
    "of the aforementioned provisions, and it is essential that this be accomplished "
    "in a timely manner by the addressees without any exception whatsoever."
)
DECENT = (
    "You must start the system check before the verification run. The addressees "
    "receive the checklist today. Each step names its owner, and the checklist keeps "
    "the original order so you can follow it without a hunt. The team shall utilize "
    "the checklist because it is very totally useful."
)
MID = (
    "It shall be noted that the aforementioned provisions are required to be verified "
    "by the addressees prior to the commencement of the undertaking of the work."
)
WORSE = (
    "It shall be noted that the aforementioned provisions are required to be verified "
    "by the addressees prior to the commencement of the undertaking of the work, and "
    "it is essential that the verification of the aforementioned provisions be "
    "accomplished in a timely manner."
)


async def test_improve_stops_at_green_without_spending_rounds():
    clean = "Short active sentence. You can read it in one pass."
    result, client = await _improve(clean, [])
    assert result["original_score"] >= BAR
    assert result["final_score"] == result["original_score"]
    assert result["rounds"] == 0
    assert client.prompts == []
    assert result["findings_applied"] == []


async def test_improve_rewrites_until_the_bar():
    original = await score_text(BAD)
    assert original["score"] < 80

    result, _ = await _improve(BAD, [DECENT])
    assert result["rounds"] == 1
    assert result["text"] == DECENT
    assert result["final_score"] == 89
    assert result["final_score"] >= result["original_score"]
    assert result["band"] == "pass"
    assert "WS-04" in result["findings_applied"]


async def test_improve_pick_is_monotonic_over_a_later_worse_rewrite():
    # Round 1 scores 62, round 2 scores 54 (worse — must be rejected), round 3 scores 89.
    result, _ = await _improve(BAD, [MID, WORSE, DECENT])
    assert result["rounds"] == 3
    assert result["text"] == DECENT
    assert result["final_score"] == 89
    assert result["final_score"] > 62


async def test_improve_respects_the_round_cap():
    result, client = await _improve(BAD, [MID, MID, MID, MID], max_rounds=2)
    assert result["rounds"] == 2
    assert len(client.prompts) == 2


async def test_improve_breaks_on_a_noop_rewrite():
    result, _ = await _improve(BAD, [BAD.strip()])
    assert result["rounds"] == 1
    assert result["text"] == BAD.strip()
    assert result["final_score"] == result["original_score"]
    # The rewrite was a no-op, so no findings were applied.
    assert result["findings_applied"] == []


async def test_improve_feeds_findings_back_to_the_model():
    result, client = await _improve(BAD, [DECENT], mode="full", audience="ship engineers")
    system, user = client.prompts[0]
    assert "plain-language editor" in system
    assert "shall" in user or "WS-04" in user
    assert "ship engineers" in user


def test_minimal_and_full_prompts_differ():
    assert RS.prompt("minimal") != RS.prompt("full")
    assert "smallest changes" in RS.prompt("minimal")
    assert "Rewrite the user's document" in RS.prompt("full")


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        RS.prompt("aggressive")
