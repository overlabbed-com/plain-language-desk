# ASD-STE100 Simplified Technical English Ruleset (structural categories)

The standard this bundle encodes. Versioned with the bundle: a rule change is
a bundle version bump plus regenerated goldens and refreshed prompts, landed
in one commit.

## Source and scope

ASD-STE100, *Simplified Technical English*, Issue 9 (January 2025) — the
controlled-language standard of the AeroSpace and Defense Industries
Association of Europe. 53 writing rules across 9 sections, backed by an
approved-word dictionary of about 900 words (one meaning, one part of speech
each) and about 1,200 words to avoid with suggested replacements.

**What this bundle encodes: the structural rule categories** — sentence
shape, voice, punctuation, verb form, paragraph discipline. Structural rules
are self-contained: they describe sentence form and can be applied and
verified from the description alone.

**What this bundle deliberately does not encode: the dictionary.** Issue 9
restricts reproduction: "no reproduction or publication of it, in whole or in
part, shall be made without the written authority of an officer of ASD"
(free reproduction is granted only to eight listed categories). This bundle
is in none of them, so no approved word list appears here. The dictionary's
underlying principle is applied as a direction of travel instead: pick the
plainest, most common word available and use it the same way every time.

**The honest limit.** Without the dictionary, lexical compliance (one word,
one meaning; approved verbs) cannot be verified — only encouraged. This
bundle does not claim to produce aerospace/defense-grade STE-compliant
documents; it produces text that obeys STE's structural discipline. For
certified STE authoring, obtain the standard from
asd-ste100.org and check word-by-word.

## The contract

Write so the reader cannot misparse the text. STE was built to stop
maintenance technicians misreading instructions; this bundle applies the
same discipline to any text where a wrong reading has a cost — procedures,
error messages, tool descriptions, instructions to agents. One word, one
meaning; one sentence, one instruction.

## Scope and exemptions

**Covered:** markdown and plain-text prose. **Exempt — machine-necessary
formatting:** code blocks, front matter, tables, and links keep their
required shapes and are stripped before scoring. A document that strips to
fewer than 50 words of prose is exempt.

**Never flagged — modality.** Hedges ("may", "could", "may have failed")
carry the author's confidence, and confidence is content. A shorter sentence
that upgrades a hedge to a fact is a different claim, not a simplification.
The scorer never flags modality; the rewrite prompts preserve it.

## Deterministic rules (the scorer's canon)

| Rule | Requirement | Deduction | STE basis |
|------|-------------|-----------|-----------|
| STE-01 | Average sentence length at or below 20 words; no sentence over 25 (descriptive cap; the prompt enforces the 20-word procedural cap) | −5; −2 each | Section 1 writing rules |
| STE-02 | No semicolons at all — the mark is banned outright, not only as a clause join; split into sentences | −2 each | Rule 8.1 |
| STE-03 | Active voice; passive only when the actor is genuinely unknown or irrelevant; no "There is/are" openers | ratio > 10% −10; −1 each | Section 3 |
| STE-04 | No phrasal verbs — a two-word verb has meanings its parts do not predict; use the single plain verb (start, not "spin up") | −2 each | Rule 9.3 |
| STE-05 | Verb, not noun — write "analyze", not "perform an analysis of" (approved-verb principle without the dictionary) | −2 each | Rule 3.7 direction |
| STE-06 | No vague quality-claim adjectives (seamless, robust, powerful, cutting-edge, effortless, …) — they name no measurable property, so no approved word can carry them | −2 each | Dictionary principle |
| STE-07 | One topic per paragraph, at most 6 sentences; sequences of 3+ steps belong in a vertical list | −2 each | Section 6 style |

The phrasal-verb and adjective lists live in the scorer as data. Extend them
only by a deliberate edit, noted here and versioned with the bundle.

## Scoring

Starts at 100 and subtracts each finding's deduction, floor 0, cap 30 per
rule class. Bands: 90 or more green, 80–89 passes, 65–79 concerns, below 65
fails. **The bar is 80** (`ruleset.json` → `bar`; the `BAR` environment
variable overrides it).

## The rewrite prompts

`rewrite-prompt-full.txt` rewrites to full structural strictness;
`rewrite-prompt-minimal.txt` fixes only what the findings name. Both carry
the hard constraints: preserve every fact, condition, and scope qualifier;
preserve the strength of every hedge; add no claim the source did not make;
never shorten past the point of clarity.
