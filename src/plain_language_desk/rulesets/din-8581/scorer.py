#!/usr/bin/env python3
"""Deterministic scorer for the din-8581 bundle (DIN8581/1.0) — Einfache Sprache.

Encodes the mechanically checkable subset of DIN 8581-1 (2024-04-26,
"Einfache Sprache — Anwendung für das Deutsche — Teil 1: Sprachspezifische
Festlegungen") for German prose. The norm is copyrighted and its full text
is not reproduced; the rule categories follow the publicly documented
clauses (6.1 Satzlänge, 6.2 Satzstruktur, 7.1 Wortebene) and public
Einfache-Sprache practice. German scores German: this scorer expects German
text and its word lists are German. Same input, same score. Stdlib only,
deterministic, no network. Modality is never flagged.

CLI contract matches the vendored FAA scorer: `--file PATH [--json]`.
"""

import argparse
import json
import re
import sys

VERSION = "DIN8581/1.0"
RULE_CAP = 30

ABBREV = {"e.g", "i.e", "vs", "etc", "app", "no", "fig", "dr", "mr", "mrs", "ms",
          "jr", "sr", "st", "approx", "inc", "ltd", "cf", "al", "seq",
          "z. b", "b", "d. h", "h", "z", "d", "usw", "ggf", "evtl", "bzw",
          "vgl", "nr", "tel", "ca", "inkl", "exkl", "u", "a", "m", "n"}

IRREGULAR_PARTICIPLES = {
    "gemacht", "gegeben", "genommen", "gesehen", "geschrieben", "gesagt",
    "gefunden", "geworden", "gebracht", "gedacht", "gelesen", "geschickt",
    "gesendet", "gewesen", "gehabt", "getan", "gestanden", "geblieben",
    "geschlossen", "gewachsen", "verloren", "gelassen", "vorgenommen",
}

# Satzebene/Stil: the norm avoids passive and the "würde" periphrasis.
# Only the Vorgangspassiv auxiliaries (wird/werden/wurde/wurden) count for
# the ratio; "ist/… + Partizip" is Zustandspassiv — a state description,
# normal German, not the construction the norm targets.
AUX_RE = re.compile(r"\b(wird|werden|wurde|wurden)\b", re.I)
# Participle heuristic: ge/be/ver/er/... prefixes, foreign verbs in -iert,
# the irregular list, and any word with "ge" at least two characters before a
# t/en ending — that catches the separable-prefix participles
# (durchgeführt, umgesetzt, abgeschlossen). Candidates cost 0; only the
# sentence ratio deducts, so a false candidate is cheap.
PARTICIPLE_RE = re.compile(
    r"\b((?:ge|be|ver|er|ent|emp|zer)\w+(?:t|en)|\w+iert|\w*ge\w\w+(?:t|en)|"
    + "|".join(sorted(IRREGULAR_PARTICIPLES)) + r")\b", re.I)
ES_WIRD_RE = re.compile(r"^\s*es\s+(wird|werden)\b", re.I)
WUERDE_RE = re.compile(r"\bwürde[nsdt]?\b", re.I)
NEGATION_RE = re.compile(
    r"\b(nicht|kein|keine|keinen|keinem|keiner|keines|keine|nichts|nie|"
    r"ohne|niemand\w*)\b", re.I)

# 6.2 Satzstruktur: one thought per sentence; the semicolon is the classic
# buried-list marker in German prose, too.
SEMICOLON_DEDUCTION = 2

# Wortebene 7.1.2: known words. Mechanical proxies: abbreviations written out
# (the norm's own example style), number words as digits, and the common
# Amtsdeutsch/Fremdwort constructions with their plain replacements.
ABBREV_DE = [
    ("z. B.", "zum Beispiel"), ("z.B.", "zum Beispiel"), ("d. h.", "das heißt"),
    ("d.h.", "das heißt"), ("usw.", "und so weiter"), ("ggf.", "gegebenenfalls"),
    ("evtl.", "eventuell"), ("bzw.", "beziehungsweise"), ("u. a.", "unter anderem"),
    ("insb.", "insbesondere"), ("vgl.", "vergleiche"), ("ca.", "etwa"),
]


def phrase_re(p):
    # A trailing \b after a period never matches (non-word on both sides), so
    # only append it when the phrase ends in a word character.
    body = r"\s+".join(re.escape(w) for w in p.split())
    tail = r"\b" if p[-1].isalnum() else ""
    return re.compile(r"\b" + body + tail, re.I)


ABBREV_DE_RES = [(phrase_re(p), res) for p, res in ABBREV_DE]
NUMBER_WORD_RE = re.compile(
    r"\b(zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf)\b", re.I)

# Regex strings (inflected forms included) with the plain replacement.
HIDDEN_VERB_PATTERNS = [
    (r"eine\s+Entscheidung\s+treffen|eine\s+Entscheidung\s+trifft", "entscheiden"),
    (r"eine\s+Prüfung\s+(?:durchführen|durchgeführt)", "prüfen"),
    (r"eine\s+Überprüfung\s+(?:durchführen|durchgeführt)", "prüfen"),
    (r"eine\s+Untersuchung\s+(?:durchführen|durchgeführt)", "untersuchen"),
    (r"zur\s+Verfügung\s+(?:stellen|stellt|stellte|gestellt)", "bereitstellen"),
    (r"in\s+Anspruch\s+(?:nehmen|nimmt|nahm|genommen)", "nutzen"),
    (r"zur\s+Anwendung\s+(?:bringen|bringt|brachte|gebracht|kommen|kommt|kam)", "anwenden"),
    (r"zum\s+Einsatz\s+(?:kommen|kommt|kam)", "genutzt werden"),
    (r"in\s+Erfahrung\s+(?:bringen|bringt|brachte|gebracht)", "herausfinden"),
    (r"in\s+Verbindung\s+(?:setzen|setzt|gesetzt)", "kontaktieren"),
    (r"in\s+Verbindung\s+mit", "mit"),
    (r"im\s+Hinblick\s+auf", "für"),
    (r"im\s+Zuge\s+von", "bei"),
    (r"im\s+Rahmen\s+von", "bei"),
    (r"aufgrund\s+von", "wegen"),
    (r"zu\s+einem\s+späteren\s+Zeitpunkt", "später"),
    (r"zum\s+jetzigen\s+Zeitpunkt", "jetzt"),
    (r"zum\s+gegenwärtigen\s+Zeitpunkt", "jetzt"),
    (r"in\s+der\s+Lage\s+(?:sein|ist|sind|war|waren)", "können"),
    (r"die\s+Möglichkeit\s+(?:haben|hat|hatte)", "können"),
]
HIDDEN_RES = [(re.compile(r"\b" + p + r"\b", re.I), res) for p, res in HIDDEN_VERB_PATTERNS]
# Fremdwörter the norm's "bekannte Wörter" principle replaces.
FOREIGN_RE = re.compile(
    r"\b(Applikationen?|implementieren|Implementierungen?|modifizieren|"
    r"Modifikationen?|utilisieren|Utilisierung)\b", re.I)

GENERIC_HEADINGS = {
    "allgemeines", "übersicht", "einleitung", "verschiedenes", "sonstiges",
    "inhalt", "inhalte", "hintergrund", "details", "hinweise", "informationen",
    "zweck", "schluss", "bemerkungen", "anmerkungen", "weiteres",
}


def strip_machine(text):
    """Remove frontmatter, fences, inline code, comments, tables, links, emphasis."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = text.find("\n---", 4)
        if end != -1:
            text = text[end + 4:]
    out_lines, in_fence = [], False
    fence = re.compile(r"^\s*(```|~~~)")
    for line in text.splitlines():
        if fence.match(line):
            in_fence = not in_fence
            out_lines.append("")
            continue
        if in_fence:
            out_lines.append("")
            continue
        s = line.rstrip()
        if s.lstrip().startswith("|"):
            out_lines.append("")
            continue
        if re.match(r"^\s*\[[^\]]+\]:\s*\S+", s):
            out_lines.append("")
            continue
        s = re.sub(r"`[^`]*`", "", s)
        s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"<(https?://[^>]*)>", "", s)
        s = re.sub(r"https?://\S+", "", s)
        s = re.sub(r"<[^>\n]+>", "", s)
        s = s.replace("*", "")
        out_lines.append(s)
    return out_lines


def parse_lines(raw):
    """Yield (line_no, text, kind) where kind is heading|list|prose|skip."""
    stripped = strip_machine(raw)
    lines = []
    for i, s in enumerate(stripped, 1):
        t = s.strip()
        if not t or re.match(r"^-{3,}$", t):
            lines.append((i, "", "skip"))
        elif re.match(r"^#{1,6}\s+", t):
            lines.append((i, re.sub(r"^#{1,6}\s+", "", t), "heading"))
        elif re.match(r"^([-*+]|\d+[.)])\s+", t):
            lines.append((i, re.sub(r"^([-*+]|\d+[.)])\s+", "", t), "list"))
        else:
            lines.append((i, t, "prose"))
    return lines


def build_blocks(lines):
    """Group consecutive non-skip lines into blocks of (start_line, kind, joined_text)."""
    blocks, cur = [], None
    for i, text, kind in lines:
        if kind == "skip":
            if cur:
                blocks.append(cur)
                cur = None
            continue
        if cur and cur[1] == kind and kind == "prose":
            cur = (cur[0], kind, cur[2] + " " + text)
        else:
            if cur:
                blocks.append(cur)
            cur = (i, kind, text)
    if cur:
        blocks.append(cur)
    return blocks


def split_sentences(block_text, block_start):
    """Split a block into (start_line, sentence) pairs, guarding abbreviations."""
    sents, buf = [], []
    i, n = 0, len(block_text)
    while i < n:
        ch = block_text[i]
        buf.append(ch)
        if ch in ".!?":
            j = i + 1
            while j < n and block_text[j] in ".!?":
                buf.append(block_text[j])
                j += 1
            k = j
            while k < n and block_text[k].isspace():
                k += 1
            if k == j:
                i = j - 1
            else:
                prev_word = "".join(buf).strip().split()[-1] if buf else ""
                if prev_word.endswith(".") and prev_word.lower().rstrip(".") in ABBREV:
                    buf.extend(block_text[j:k])
                    i = k - 1
                else:
                    offset = i - len("".join(buf)) + 1
                    sents.append((offset, "".join(buf).strip()))
                    buf = []
                    i = k - 1
        i += 1
    tail = "".join(buf).strip()
    if tail:
        sents.append((i - len(tail), tail))
    return [(block_start + block_text[:off].count("\n"), s) for off, s in sents]


def words(text):
    # \w is Unicode in Python 3: German umlauts and ß count inside a word.
    return [w for w in re.findall(r"[\w'-]+", text)]


def score_file(path):
    """Score one German markdown file. Returns the report dict."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise RuntimeError(f"unreadable file {path}: {exc}") from exc
    lines = parse_lines(raw)
    blocks = build_blocks(lines)
    headings = [(i, t) for i, t, k in lines if k == "heading"]
    prose_lines = [(i, t) for i, t, k in lines if k in ("prose", "list")]

    sentences = []
    for start, kind, text in blocks:
        if kind in ("prose", "list"):
            sentences.extend(split_sentences(text, start))
    doc_words = sum(len(words(t)) for _, t in prose_lines)

    findings = []

    def add(rule, deduction, line, evidence):
        findings.append({"rule": rule, "deduction": deduction,
                         "line": line, "evidence": evidence[:160]})

    if not sentences:
        return {"file": path, "version": VERSION, "score": None, "exempt": True,
                "doc_words": doc_words, "findings": []}

    # DIN-R1 (Kl. 6.1 Satzlänge): max 25 words per sentence, 15 recommended.
    lens = [len(words(s)) for _, s in sentences]
    avg = sum(lens) / len(lens)
    if avg > 15:
        add("DIN-R1", 5, sentences[0][0], f"durchschnittliche Satzlänge {avg:.1f} Wörter (empfohlen 15)")
    for (line, s), n in zip(sentences, lens):
        if n > 25:
            add("DIN-R1", 2, line, f"Satz mit {n} Wörtern (Maximum 25): {s}")

    # DIN-R2 (Kl. 6.2 Satzstruktur): one thought per sentence — the
    # semicolon is the mechanical marker of a buried list.
    for line, s in sentences:
        n_semi = s.count(";")
        if n_semi:
            add("DIN-R2", SEMICOLON_DEDUCTION * n_semi, line,
                f"Semikolon x{n_semi} (ein Satz, ein Gedanke): {s}")

    # DIN-R3 (Kl. 6.2 Stil): avoid negation stacking.
    for line, s in sentences:
        hits = NEGATION_RE.findall(s)
        if len(hits) >= 2:
            add("DIN-R3", 1, line, f"{len(hits)} Verneinungen im Satz: {s}")

    # DIN-R4 (Satzebene): passive voice; "es wird" opens with no actor.
    passive = 0
    for line, s in sentences:
        if ES_WIRD_RE.match(s):
            add("DIN-R4", 1, line, f"'Es wird'-Einstieg ohne Handelnden: {s}")
        m = AUX_RE.search(s)
        if m:
            tail = s[m.end():]
            pm = PARTICIPLE_RE.search(tail)
            if pm and len(tail[:pm.start()].split()) <= 3:
                passive += 1
                add("DIN-R4", 0, line, f"Passiv-Kandidat: {s}")
    ratio = passive / len(sentences)
    if ratio > 0.25:
        add("DIN-R4", 20, sentences[0][0], f"Passiv-Anteil {ratio:.0%} über 25%")
    elif ratio > 0.15:
        add("DIN-R4", 10, sentences[0][0], f"Passiv-Anteil {ratio:.0%} über 15%")

    # DIN-R5 (Satzebene, Zeitformen): the "würde" periphrasis.
    for line, s in sentences:
        for m in WUERDE_RE.finditer(s):
            add("DIN-R5", 1, line, f"'würde'-Umschreibung -> Hauptverb: {s}")

    # DIN-R6 (Wortebene): write abbreviations out.
    for line, s in sentences:
        for pat, res in ABBREV_DE_RES:
            for m in pat.finditer(s):
                add("DIN-R6", 2, line, f"'{m.group(0)}' ausschreiben ('{res}'): {s}")

    # DIN-R7 (Wortebene, Zahlen): numbers as digits.
    for line, s in sentences:
        for m in NUMBER_WORD_RE.finditer(s):
            add("DIN-R7", 1, line, f"Zahlwort '{m.group(0)}' als Ziffer schreiben: {s}")

    # DIN-R8 (Wortebene 7.1.2): hidden verbs and foreign words.
    for line, s in sentences:
        for pat, res in HIDDEN_RES:
            for m in pat.finditer(s):
                add("DIN-R8", 2, line, f"'{m.group(0)}' -> '{res}': {s}")
        for m in FOREIGN_RE.finditer(s):
            add("DIN-R8", 2, line, f"Fremdwort '{m.group(0)}' -> bekanntes Wort: {s}")

    # DIN-R9 (Textebene, Textstruktur): short paragraphs, informative headings.
    for start, kind, text in blocks:
        if kind == "prose" and len(words(text)) > 120:
            add("DIN-R9", 2, start, f"Absatz mit {len(words(text))} Wörtern (Maximum 120)")
    if doc_words > 300 and not headings:
        add("DIN-R9", 10, 1, f"{doc_words} Wörter ohne Überschriften")
    for line, t in headings:
        core = re.sub(r"[^A-Za-zÜÖÄäöüß ]", "", t).strip().lower()
        if core in GENERIC_HEADINGS:
            add("DIN-R9", 2, line, f"generische Überschrift '{t}'")

    # deductions, capped per rule class
    per_rule = {}
    for f in findings:
        if f["deduction"]:
            per_rule[f["rule"]] = per_rule.get(f["rule"], 0) + f["deduction"]
    capped = {r: min(d, RULE_CAP) for r, d in per_rule.items()}
    score = max(0, 100 - sum(capped.values()))

    findings.sort(key=lambda f: (f["line"], f["rule"], f["evidence"]))
    return {"file": path, "version": VERSION, "score": score, "exempt": False,
            "doc_words": doc_words, "avg_sentence_words": round(avg, 1),
            "findings": findings}


def band(score):
    if score is None:
        return "exempt"
    if score >= 90:
        return "green"
    if score >= 80:
        return "pass"
    if score >= 65:
        return "concerns"
    return "fail"


def main(argv=None):
    ap = argparse.ArgumentParser(description="DIN 8581-1 Einfache-Sprache-Prüfer")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--file", dest="files", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    paths = args.files or args.paths
    if not paths:
        print("no files given", file=sys.stderr)
        return 2
    reports = []
    for p in paths:
        r = score_file(p)
        reports.append(r)
        if not args.json:
            b = band(r["score"])
            line = f"{p}: score {r['score']} ({b})"
            if r["score"] is not None:
                line += f", {r['doc_words']} Wörter, Ø Satz {r.get('avg_sentence_words', '?')}"
            print(line)
            for f in r["findings"]:
                print(f"  - {f['rule']} -{f['deduction']} Zeile {f['line']}: {f['evidence']}")
    if args.json:
        print(json.dumps({"files": reports}))
    subjects = len(reports)
    print(f"{subjects} Datei(en) geprüft", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
