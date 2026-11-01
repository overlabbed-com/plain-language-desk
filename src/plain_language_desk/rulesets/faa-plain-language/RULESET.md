# FAA Plain-Language Ruleset

The standard this bundle encodes. Versioned with the bundle: a rule change is a
bundle version bump plus regenerated goldens and refreshed prompts, landed in
one commit.

## Sources

- FAA Order 1000.36A, *FAA Writing Standards* (effective 2023-12-21), which
  implements the Plain Writing Act of 2010. Cited as "Order §6.x".
- *Writing User-Friendly Documents*, the federal plain-language handbook
  adapted for the Federal Aviation Administration, February 2000.
  Cited as "Handbook §3.x".

## The contract

A reader must find what they need, understand what they find, and use it to
meet their need (Order §5). Write for the least technical reader who needs the
document. When a document has several audiences, pick one primary audience and
write to it (Order §6.a.1).

## Scope and exemptions

**Covered:** markdown and plain-text prose — planning documents, specs, plans,
reports, runbooks, PR bodies, READMEs, convention docs, and agent-facing
messages written as files.

**Exempt — machine-necessary formatting.** The standard never overrides the
structure a machine consumes: YAML, JSON, schemas, code blocks, frontmatter,
tables, and strict-format artifacts keep their required shapes. The scorer
strips all of these and scores only prose. A document that strips to fewer
than 50 words of prose is exempt from scoring.

## Deterministic rules (the scorer's canon)

The scorer applies these rules with fixed thresholds and word lists. Same
input, same score. Each rule cites its source.

| Rule | Requirement | Deduction | Source |
|------|-------------|-----------|--------|
| WS-01a | Average sentence length stays at or below 20 words | −5 | Order §6.a.4 |
| WS-01b | No sentence exceeds 35 words | −2 each | Order §6.a.4 |
| WS-01c | No sentence carries 3 or more semicolons; break it into a vertical list | −2 each | Order §6.a.4, §6.d.4 |
| WS-02 | No paragraph exceeds 150 words; one topic per paragraph | −2 each | Order §6.a.5, Handbook §3.o |
| WS-03 | Passive voice stays at or below 10 percent of sentences (over 25 percent doubles the deduction); no sentence opens with "There is/are" | −10, −10; −1 each | Order §6.a.3, Handbook §3.e |
| WS-04 | Never write "shall": use "must" for obligation, "may" for permission, "should" for recommendation, "may not" for prohibition, "will" for the future | −5 each | Order §6.a.7, Handbook §3.i |
| WS-05 | No wordy phrase or legal jargon; the scorer ships the substitution list from Order §6.d.1 and Handbook Appendices A and B | −2 each | Order §6.d.1; Handbook App. A, B |
| WS-06 | No hidden verb: write "review", not "carry out a review" | −2 each | Order §6.d.2 |
| WS-07 | No filler qualifier: very, really, totally, completely, definitely, extremely, absolutely, utterly | −1 each | Order §6.d.3 |
| WS-08 | Spell out an abbreviation at first use, then the acronym in parentheses; never introduce an acronym for a one-time term; a house whitelist covers shared technical vocabulary | −3 / −1 | Order §6.a.6, Handbook §3.l |
| WS-09 | A document over 600 words carries headings; no generic one-word heading (general, overview, introduction, misc, other, summary, background, details, notes, information, content, purpose, conclusion, training, transfer) | −10; −2 each | Order §6.c, Handbook §3.m |

The acronym whitelist lives in the scorer as data. Extend it only by a
deliberate edit to the scorer, noted here and versioned with the bundle.

## Scoring

Layer 1 starts at 100 and subtracts each finding's deduction, with a floor of
0 and a cap of 30 per rule class. Bands: 90 or more is green, 80–89 passes,
65–79 raises concerns, below 65 fails. **The bar is 80** (bundle config:
`ruleset.json` → `bar`; the `BAR` environment variable overrides it).

## The rewrite prompts

`rewrite-prompt-full.txt` and `rewrite-prompt-minimal.txt` are the rule set in
editor form, plus one hard constraint: change the prose, never the meaning.
`minimal` fixes only what the findings name; `full` restyles to the bar. When
a rule above changes, both prompts change in the same commit.

## Judgment rules (out of scope here)

Nine principles resist a regex but not judgment (direct address, organization,
present tense, and so on). The source standard scores them with a decision
model as an advisory J-score that never gates. This service scores the
deterministic layer only; the J-score machinery stays with the DSH flywheel
until a bundle needs it.
