#!/usr/bin/env python3
"""Deterministic scorer for the iso-24495 bundle (ISO24495/1.0).

Encodes the mechanically checkable subset of ISO 24495-1:2023 plain language
as fixed rules with fixed deductions. ISO 24495-1 defines plain language by
reader outcome (relevant, findable, understandable, usable), not by numeric
thresholds — the thresholds here are this bundle's working proxies, and the
RULESET.md documents which principles stay judgment-layer. Same input, same
score. Stdlib only, deterministic, no network.

CLI contract matches the vendored FAA scorer: `--file PATH [--json]`.
"""

import argparse
import json
import re
import sys

VERSION = "ISO24495/1.0"
RULE_CAP = 30

ABBREV = {"e.g", "i.e", "vs", "etc", "app", "no", "fig", "dr", "mr", "mrs", "ms",
          "jr", "sr", "st", "approx", "inc", "ltd", "cf", "al", "seq"}

IRREGULAR_PARTICIPLES = {
    "done", "made", "given", "taken", "seen", "known", "written", "shown",
    "held", "kept", "sent", "set", "put", "run", "begun", "chosen", "driven",
    "eaten", "fallen", "forgotten", "gotten", "hidden", "broken", "spoken",
    "stolen", "thrown", "worn", "built", "bought", "brought", "caught",
    "taught", "thought", "found", "felt", "dealt", "meant", "met", "paid",
    "said", "told", "sold", "spent", "left", "lost", "read", "led", "won",
    "gone", "come", "become", "born", "sworn", "torn", "drawn", "withdrawn",
    "grown", "blown", "flown", "sewn", "mistaken", "proven", "sung", "sunk",
    "drunk", "struck", "stuck", "understood", "undergone", "overcome",
    "forsaken", "shaken", "cut", "hit", "let", "shut",
}

# Bureaucratic flab and Latinisms the handbook tradition names; the reader
# outcome (understandable) is the ISO principle each deduction serves.
WORDY_PHRASES = [
    "in order to", "in order that", "prior to", "subsequent to",
    "in the event that", "due to the fact that", "at the present time",
    "at a later date", "for the purpose of", "as a means of",
    "in accordance with", "pertaining to", "so as to",
    "with respect to", "with reference to", "with the exception of",
    "in regard to", "in lieu of", "until such time as",
    "a number of", "the use of", "time period", "point in time",
    "in a timely manner", "close proximity", "it is important to note that",
    "it should be noted that", "please be advised", "take action",
    "make modifications", "successfully complete", "and/or",
    "utilize", "utilization", "facilitate", "commence", "initiate",
    "ascertain", "endeavor", "disseminate", "furnish", "procure",
    "pursuant", "aforementioned", "aforesaid", "heretofore", "hereby",
    "herein", "hereinafter", "therein", "thereof", "whereas", "witnesseth",
    "necessitate", "expedite", "expeditious", "state-of-the-art",
]
WORDY_PATTERNS = [
    (p, re.compile(r"\b" + r"\s+".join(re.escape(w) for w in p.split()) + r"\b", re.I))
    for p in WORDY_PHRASES
] + [("on a <x> basis", re.compile(r"\bon a \w+ basis\b", re.I))]

HIDDEN_VERB_RE = re.compile(
    r"\b(carry(?:ing)? out|conducts?|conducted|performs?|performed|makes?|made|"
    r"undertakes?|undertook|provides?|provided)\s+(an?\s+)?"
    r"(reviews?|assessments?|calculations?|determinations?|evaluations?|"
    r"examinations?|analyses|analysis|verifications?|validations?|"
    r"inspections?|investigations?|monitoring|implementations?|"
    r"considerations?|revisions?|corrections?|measurements?|"
    r"audits?|testing|checks?|comparisons?|decisions?)\b", re.I)

QUALIFIER_RE = re.compile(
    r"\b(very|really|totally|completely|definitely|extremely|absolutely|utterly|"
    r"quite|rather|somewhat|basically|actually|literally)\b", re.I)

PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\b(?:\s+not)?(?:\s+\w+ly)?\s+"
    r"(\w+ed|" + "|".join(sorted(IRREGULAR_PARTICIPLES)) + r")\b", re.I)

THERE_RE = re.compile(r"^\s*there\s+(is|are|was|were)\b", re.I)

ACRO_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}s?\b")
# Small shared-technical-vocabulary whitelist for a general audience: these are
# the abbreviations a non-specialist reader meets as words. Extend only by a
# deliberate edit, noted in RULESET.md and versioned with the bundle.
ACRO_WHITELIST = {
    "HTTP", "HTTPS", "URL", "URI", "API", "JSON", "XML", "CSV", "PDF",
    "ID", "OK", "AI", "UI", "UX", "IP", "DNS", "SQL",
}
ROMAN = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}
GENERIC_HEADINGS = {
    "general", "overview", "introduction", "misc", "other", "summary",
    "background", "details", "notes", "information", "content", "purpose",
    "conclusion", "appendix",
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
    return [w for w in re.findall(r"[A-Za-z0-9'/-]+", text)]


def score_file(path):
    """Score one markdown file. Returns the report dict. Raises on unreadable input."""
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

    # ISO-R1 (understandable) sentence length
    lens = [len(words(s)) for _, s in sentences]
    avg = sum(lens) / len(lens)
    if avg > 20:
        add("ISO-R1", 5, sentences[0][0], f"average sentence length {avg:.1f} words (limit 20)")
    for (line, s), n in zip(sentences, lens):
        if n > 40:
            add("ISO-R1", 2, line, f"sentence of {n} words: {s}")

    # ISO-R2 (understandable) voice
    passive = 0
    for line, s in sentences:
        if THERE_RE.match(s):
            add("ISO-R2", 1, line, f"'There is/are' opener: {s}")
        m = PASSIVE_RE.search(s)
        if m:
            passive += 1
            add("ISO-R2", 0, line, f"passive candidate: {s}")
    ratio = passive / len(sentences)
    if ratio > 0.25:
        add("ISO-R2", 20, sentences[0][0], f"passive ratio {ratio:.0%} over 25%")
    elif ratio > 0.15:
        add("ISO-R2", 10, sentences[0][0], f"passive ratio {ratio:.0%} over 15%")

    # ISO-R3 (understandable) wordy phrases and hidden verbs
    for line, s in sentences:
        for name, pat in WORDY_PATTERNS:
            for m in pat.finditer(s):
                add("ISO-R3", 2, line, f"'{m.group(0)}' -> use the plain form: {s}")
        for m in HIDDEN_VERB_RE.finditer(s):
            add("ISO-R3", 2, line, f"hidden verb '{m.group(0)}': {s}")

    # ISO-R4 (findable) paragraph length — list blocks exempt
    for start, kind, text in blocks:
        if kind == "prose" and len(words(text)) > 150:
            add("ISO-R4", 2, start, f"paragraph of {len(words(text))} words (limit 150)")

    # ISO-R5 (findable) headings
    if doc_words > 400 and not headings:
        add("ISO-R5", 10, 1, f"{doc_words} words with no headings")
    for line, t in headings:
        core = re.sub(r"[^A-Za-z ]", "", t).strip().lower()
        if core in GENERIC_HEADINGS:
            add("ISO-R5", 2, line, f"generic heading '{t}'")

    # ISO-R6 (understandable) filler qualifiers
    for line, s in sentences:
        for m in QUALIFIER_RE.finditer(s):
            add("ISO-R6", 1, line, f"filler qualifier '{m.group(0)}': {s}")

    # ISO-R7 (understandable) acronym discipline
    prose_all = " ".join(t for _, t in prose_lines)
    lower_words = set(re.findall(r"[a-z]+", prose_all))
    counts = {}
    first_pos = {}
    for m in ACRO_RE.finditer(prose_all):
        acro = m.group(0)
        counts[acro] = counts.get(acro, 0) + 1
        first_pos.setdefault(acro, m.start())
    for acro, count in sorted(counts.items()):
        if acro in ACRO_WHITELIST or acro in ROMAN:
            continue
        if acro.endswith("s") and acro[:-1] in ACRO_WHITELIST:
            continue
        if re.fullmatch(r"[A-Z]\d", acro):
            continue
        base = re.match(r"[A-Z]+", acro).group(0)
        if base in ACRO_WHITELIST:
            continue
        if acro.lower() in lower_words:
            continue
        defined = f"({acro})" in prose_all
        if defined:
            def_pos = prose_all.find(f"({acro})")
            if first_pos[acro] < def_pos:
                add("ISO-R7", 3, 1, f"'{acro}' used before its spelled-out first use")
        elif count == 1:
            add("ISO-R7", 1, 1, f"'{acro}' introduced for a one-time term; write it out")
        else:
            add("ISO-R7", 3, 1, f"'{acro}' used {count}x with no spelled-out first use '(ACRO)'")

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
    ap = argparse.ArgumentParser(description="ISO 24495-1 plain-language scorer")
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
                line += f", {r['doc_words']} words, avg sentence {r.get('avg_sentence_words', '?')}"
            print(line)
            for f in r["findings"]:
                print(f"  - {f['rule']} -{f['deduction']} line {f['line']}: {f['evidence']}")
    if args.json:
        print(json.dumps({"files": reports}))
    subjects = len(reports)
    print(f"{subjects} file(s) scored", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
