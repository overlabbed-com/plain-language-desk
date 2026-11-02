# DIN 8581-1 Einfache-Sprache Ruleset (German)

The standard this bundle encodes. Versioned with the bundle: a rule change is
a bundle version bump plus regenerated goldens and refreshed prompts, landed
in one commit.

**This is a German-language standard: score German prose with it.** The
scorer's rules, word lists, and findings are German; the rewrite prompts are
German.

## Source and scope

DIN 8581-1 (published 2024-04-26), *Einfache Sprache — Anwendung für das
Deutsche — Teil 1: Sprachspezifische Festlegungen*. It specifies the general
principles of ISO 24495-1 (the four reader outcomes: Relevanz,
Auffindbarkeit, Verständlichkeit, Nutzbarkeit) for the German language, with
concrete rules organized by Textebene, Satzebene, Wortebene, and Gestaltung.

**What it is not:** this is not Leichte Sprache (DIN SPEC 33429). Einfache
Sprache targets readers with limited reading competence or German as a
second language; Leichte Sprache targets cognitive accessibility and is far
more radical (hyphenated compounds, one statement per line, tested by the
target group). DIN states the norm's rules are not legally binding unless a
law or ordinance declares them so.

**Copyright boundary.** The norm's full text is copyrighted and is not
reproduced here. The rule categories follow the publicly documented clauses
(6.1 Satzlänge, 6.2 Satzstruktur, 7.1 Wortebene) and public Einfache-Sprache
practice. The numeric thresholds below are **this bundle's working proxies**
except where the clause itself fixes the number. For conformance work, buy
the norm from DIN Media.

**Honest limits.** No POS tagging and no dictionary: subordinate-clause
counting (6.2), synonym consistency (7.1.1), and word familiarity (7.1.2)
are judgment-layer and carried by the rewrite prompts. The passive-voice
detector is a participle heuristic — candidates are reported with zero
deduction, only the ratio deducts. Modality is never flagged: hedges
("könnte", "vielleicht") are content, not style.

## Deterministic rules (the scorer's canon)

| Rule | Clause | Requirement | Deduction |
|------|--------|-------------|-----------|
| DIN-R1 | 6.1 Satzlänge | No sentence over 25 words (the clause's maximum); average at or below 15 words (the clause's recommendation) | −2 each; −5 |
| DIN-R2 | 6.2 Satzstruktur | One thought per sentence; a semicolon buries a list | −2 each |
| DIN-R3 | Satzebene (Stil) | No negation stacking: at most one negation word per sentence | −1 per sentence with 2+ |
| DIN-R4 | Satzebene | Active voice; passive ratio at or below 15 percent (over 25 percent doubles the deduction); no "Es wird" opener without an actor | −10, −20; −1 each |
| DIN-R5 | Satzebene (Zeitformen) | No "würde" periphrasis; use the main verb | −1 each |
| DIN-R6 | Wortebene | Write abbreviations out ("z. B." → "zum Beispiel", "bzw.", "usw.", "ggf.", "d. h.", …) | −2 each |
| DIN-R7 | Wortebene | Write numbers one to twelve as digits | −1 each |
| DIN-R8 | 7.1.2 bekannte Wörter | No hidden verbs ("zur Verfügung stellen" → "bereitstellen"); no avoidable foreign words ("Applikation" → "Anwendung") | −2 each |
| DIN-R9 | Textebene (Textstruktur) | No prose paragraph over 120 words; a document over 300 words carries headings; no generic one-word heading (Allgemeines, Übersicht, Sonstiges, …) | −2 each; −10; −2 each |

The abbreviation, hidden-verb, foreign-word, and heading lists live in the
scorer as data. Extend them only by a deliberate edit, noted here and
versioned with the bundle.

**Out of mechanical scope (judgment, carried by the prompts):** Relevanz and
Nutzbarkeit as reader outcomes; synonym consistency (7.1.1 — "ein Begriff,
ein Wort"); word familiarity beyond the mechanical list; the Gestaltung
chapter (typography, font size, images) — presentation, not prose.

## Scoring

Starts at 100 and subtracts each finding's deduction, floor 0, cap 30 per
rule class. Bands: 90 or more green, 80–89 passes, 65–79 concerns, below 65
fails. **The bar is 80** (`ruleset.json` → `bar`; the `BAR` environment
variable overrides it).

## The rewrite prompts

`rewrite-prompt-full.txt` rewrites German prose to Einfache Sprache;
`rewrite-prompt-minimal.txt` fixes only what the findings name. Both carry
the hard constraints: keep every fact, number, and qualifier; never promote
a hedge to a fact; address the reader directly ("Sie"); prefer the known
word, one name per thing.
