# ISO 24495-1 Plain-Language Ruleset

The standard this bundle encodes. Versioned with the bundle: a rule change is
a bundle version bump plus regenerated goldens and refreshed prompts, landed
in one commit.

## Source and scope

ISO 24495-1:2023, *Plain language — Part 1: Governing principles and
guidelines* (ISO/TC 37, published June 2023). Cited as "ISO §".

ISO defines plain language by **reader outcome**, not by word lists: a
document is plain when its intended readers can get what they need
(**relevant**), find it (**findable**), understand it on first reading
(**understandable**), and act on it (**usable**). The standard states it
applies to most, if not all, written languages.

**Copyright boundary.** The standard's full text is a licensed ISO document
and is not reproduced here. This bundle encodes the four publicly documented
principles and applies them through this project's own mechanical proxies.
The numeric thresholds below are **working proxies, not clauses of the
standard** — ISO fixes no word counts. For certified conformance work, buy
and consult the standard itself (iso.org/standard/78907.html).

## The contract

Write for the document's intended reader and purpose. Every rule below serves
one of the four outcomes; the rule table names the outcome each rule serves.

## Scope and exemptions

**Covered:** markdown and plain-text prose for human readers — reports,
emails, documentation, UI text, announcements, policies, explanations.

**Exempt — machine-necessary formatting.** YAML, JSON, code blocks, front
matter, tables, and links keep their required shapes; the scorer strips all
of these and scores only prose. A document that strips to fewer than 50 words
of prose is exempt from scoring.

**Out of mechanical scope (judgment, carried by the rewrite prompts):**

- **Relevant** — whether the text contains what this reader needs for this
  purpose. Cutting is a rewrite decision, not a regex.
- **Usable** — whether the reader can act: concrete instructions, explicit
  actors and deadlines. The prompts enforce it; only its scannability
  preconditions (paragraph and heading discipline) are mechanical.

## Deterministic rules (the scorer's canon)

| Rule | Outcome | Requirement | Deduction |
|------|---------|-------------|-----------|
| ISO-R1 | understandable | Average sentence length at or below 20 words; no sentence over 40 | −5; −2 each |
| ISO-R2 | understandable | Passive voice at or below 15 percent of sentences (over 25 percent doubles the deduction); no sentence opens with "There is/are" | −10, −20; −1 each |
| ISO-R3 | understandable | No wordy phrase, legalism, or Latinism; no hidden verb ("carry out a review" → "review") | −2 each |
| ISO-R4 | findable | No prose paragraph over 150 words; one topic per paragraph | −2 each |
| ISO-R5 | findable | A document over 400 words carries headings; no generic one-word heading | −10; −2 each |
| ISO-R6 | understandable | No filler qualifier (very, really, totally, completely, definitely, extremely, absolutely, utterly, quite, rather, somewhat, basically, actually, literally) | −1 each |
| ISO-R7 | understandable | Spell out an abbreviation at first use; a small whitelist covers abbreviations a general reader meets as words (HTTP, URL, API, JSON, PDF, ID, …) | −3 / −1 |

The word lists and the acronym whitelist live in the scorer as data. Extend
them only by a deliberate edit, noted here and versioned with the bundle.

## Scoring

Starts at 100 and subtracts each finding's deduction, floor 0, cap 30 per
rule class. Bands: 90 or more green, 80–89 passes, 65–79 concerns, below 65
fails. **The bar is 80** (`ruleset.json` → `bar`; the `BAR` environment
variable overrides it).

## The rewrite prompts

`rewrite-prompt-full.txt` rewrites to the four outcomes; `rewrite-prompt-
minimal.txt` fixes only what the findings name. Both carry the hard
constraints: change the prose, never the meaning; keep every fact, number,
and qualifier; never promote a hedge to a fact ("may have failed" stays
"may have failed").
