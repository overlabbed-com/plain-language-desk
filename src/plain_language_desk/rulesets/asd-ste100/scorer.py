#!/usr/bin/env python3
"""Deterministic scorer for the asd-ste100 bundle (STE/1.0).

Encodes the STRUCTURAL rule categories of ASD-STE100 Issue 9 as fixed rules
with fixed deductions. ASD-STE100's ~900-word approved dictionary is
deliberately NOT encoded — the standard restricts reproduction (Issue 9
grants free reproduction only to eight listed categories), and without the
dictionary the lexical rules are a direction of travel, not a checkable
standard. RULESET.md documents the boundary. Same input, same score.
Stdlib only, deterministic, no network.

Modality is never flagged: hedges ("may have failed") are content, not style.

CLI contract matches the vendored FAA scorer: `--file PATH [--json]`.
"""

import argparse
import json
import re
import sys

VERSION = "STE/1.0"
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

# Rule 9.3: no phrasal verbs — a two-word verb has meanings its parts do not
# predict. Starter list of the common ones; extend by a deliberate edit,
# noted in RULESET.md and versioned with the bundle.
PHRASAL_VERBS = [
    "carry out", "carried out", "carries out", "carrying out",
    "carry on", "carried on", "carry on with",
    "spin up", "spun up", "spin down", "tear down", "tore down",
    "take off", "takes off", "took off", "put off", "puts off",
    "set up", "sets up", "set up for", "give up", "gives up", "gave up",
    "turn on", "turn off", "turns on", "turns off", "turn on to",
    "look at", "looks at", "looked at", "look into", "look for",
    "go through", "goes through", "went through", "bring in", "brings in",
    "point out", "points out", "pointed out", "find out", "finds out",
    "found out", "work out", "works out", "worked out", "check out",
    "checks out", "clean up", "cleans up", "fill in", "fills in",
    "fill out", "fills out", "hook up", "hooks up", "knock out",
    "knocks out", "print out", "prints out", "show up", "shows up",
    "sort out", "sorts out", "throw away", "throws away", "tie in",
    "ties in", "trade off", "trades off", "make up", "makes up",
    "made up", "break down", "breaks down", "broke down", "bring up",
    "brings up", "brought up", "call out", "calls out", "call up",
    "shut down", "shuts down", "start up", "starts up", "warm up",
    "warms up", "wipe out", "wipes out", "hook into", "dial in",
]
PHRASAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in PHRASAL_VERBS) + r")\b", re.I)

HIDDEN_VERB_RE = re.compile(
    r"\b(carry(?:ing)? out|conducts?|conducted|performs?|performed|makes?|made|"
    r"undertakes?|undertook|provides?|provided)\s+(an?\s+)?"
    r"(reviews?|assessments?|calculations?|determinations?|evaluations?|"
    r"examinations?|analyses|analysis|verifications?|validations?|"
    r"inspections?|investigations?|monitoring|implementations?|"
    r"considerations?|revisions?|corrections?|measurements?|"
    r"audits?|testing|checks?|comparisons?)\b", re.I)

# STE permits only approved words; quality-claim adjectives can never be
# approved because they name no measurable property. Mechanical subset.
VAGUE_ADJECTIVE_RE = re.compile(
    r"\b(seamless|seamlessly|robust|robustness|powerful|powerfully|cutting-edge|"
    r"effortless|effortlessly|blazing(?:-fast)?|game-changing|best-in-class|"
    r"state-of-the-art|revolutionary|world-class|industry-leading|"
    r"next-generation|innovative|intuitive|stunning|amazing|awesome|"
    r"fantastic|incredible|magical|elite|premier|superior)\b", re.I)

PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\b(?:\s+not)?(?:\s+\w+ly)?\s+"
    r"(\w+ed|" + "|".join(sorted(IRREGULAR_PARTICIPLES)) + r")\b", re.I)

THERE_RE = re.compile(r"^\s*there\s+(is|are|was|were)\b", re.I)


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

    # STE-01 sentence length (Issue 9, section 1 writing rules): descriptive
    # sentences cap at 25 words, procedural at 20. The scorer applies the
    # descriptive cap mechanically; the rewrite prompt enforces the
    # procedural cap because telling procedure from description is judgment.
    lens = [len(words(s)) for _, s in sentences]
    avg = sum(lens) / len(lens)
    if avg > 20:
        add("STE-01", 5, sentences[0][0], f"average sentence length {avg:.1f} words (limit 20)")
    for (line, s), n in zip(sentences, lens):
        if n > 25:
            add("STE-01", 2, line, f"sentence of {n} words (limit 25): {s}")

    # STE-02 Rule 8.1: no semicolons at all — the mark is banned outright.
    for line, s in sentences:
        n_semi = s.count(";")
        if n_semi:
            add("STE-02", 2 * n_semi, line, f"semicolon x{n_semi} (banned; split into sentences): {s}")

    # STE-03 active voice (passive allowed only when the actor does not exist).
    passive = 0
    for line, s in sentences:
        if THERE_RE.match(s):
            add("STE-03", 1, line, f"'There is/are' opener (actor missing): {s}")
        m = PASSIVE_RE.search(s)
        if m:
            passive += 1
            add("STE-03", 0, line, f"passive candidate: {s}")
    ratio = passive / len(sentences)
    if ratio > 0.10:
        add("STE-03", 10, sentences[0][0], f"passive ratio {ratio:.0%} over 10%")

    # STE-04 Rule 9.3: no phrasal verbs.
    for line, s in sentences:
        for m in PHRASAL_RE.finditer(s):
            add("STE-04", 2, line, f"phrasal verb '{m.group(0)}' -> use the single plain verb: {s}")

    # STE-05 Rule 3.7 direction: verb, not noun (nominalizations).
    for line, s in sentences:
        for m in HIDDEN_VERB_RE.finditer(s):
            add("STE-05", 2, line, f"nominalization '{m.group(0)}': {s}")

    # STE-06 vague quality-claim adjectives.
    for line, s in sentences:
        for m in VAGUE_ADJECTIVE_RE.finditer(s):
            add("STE-06", 2, line, f"vague adjective '{m.group(0)}' -> state the measurement: {s}")

    # STE-07 one topic per paragraph, at most 6 sentences (list blocks exempt).
    for start, kind, text in blocks:
        if kind == "prose":
            n_sents = len(split_sentences(text, start))
            if n_sents > 6:
                add("STE-07", 2, start, f"paragraph of {n_sents} sentences (limit 6)")

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
    ap = argparse.ArgumentParser(description="ASD-STE100 structural-rules scorer")
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
